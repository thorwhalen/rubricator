"""The JSON Schema subset a tool signature may use (ADR-0013), as a checker.

Providers reach near-total schema compliance in constrained mode by supporting
a conservative subset of JSON Schema, and that subset is a constraint on **our
tool signatures**, not on some later serialisation layer. ADR-0013 lists it as
a seven-point checklist a reviewer holds a diff against. This module is that
checklist as a function, so the conformance test holds it against every
declared ``inputSchema`` and ``outputSchema`` on the frozen surface instead of
a reviewer holding it against one diff.

What is allowed is an **allowlist**, not a denylist: a keyword this module has
never heard of is a violation, because "a provider might support it" is the
assumption the checklist exists to forbid. The seven points, in order:

1. no ``minimum`` / ``maximum`` / ``exclusiveMinimum`` / ``exclusiveMaximum`` /
   ``multipleOf`` -- a bounded numeric is an ``enum``;
2. no ``minLength`` / ``maxLength``;
3. ``additionalProperties: false`` on every object, not merely absent;
4. every ``$ref`` internal (``#/...``);
5. no recursion through ``$ref``;
6. ``minItems`` is 0 or 1;
7. every ``enum`` over scalars.

Everything else the surface needs is on the allowlist: the seven types,
``const``, ``anyOf``, ``allOf``, ``required``, ``default``, ``format``, and
``title`` / ``description`` for the reader.

>>> subset_violations({"type": "integer", "minimum": 1, "maximum": 5})
['$: "minimum" is not in the ADR-0013 subset; a bounded numeric is an enum', \
'$: "maximum" is not in the ADR-0013 subset; a bounded numeric is an enum']
>>> subset_violations({"type": "object", "properties": {"a": {"type": "string"}}})
['$: an object must declare additionalProperties: false']
>>> subset_violations({"type": "integer", "enum": [1, 2, 3, 4, 5]})
[]
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["subset_violations", "ALLOWED_KEYWORDS", "TYPES", "FORMATS"]

#: The seven JSON types.
TYPES: frozenset[str] = frozenset(
    {"string", "number", "integer", "boolean", "object", "array", "null"}
)

#: Every keyword a schema on the surface may use. Anything else is a violation.
ALLOWED_KEYWORDS: frozenset[str] = frozenset({
    "type", "properties", "required", "additionalProperties", "items",
    "enum", "const", "anyOf", "allOf", "$ref", "$defs", "default", "format",
    "title", "description", "minItems",
})

#: Keywords the checklist names explicitly, with the reason a reader needs.
_NAMED_REASONS: Mapping[str, str] = {
    "minimum": "a bounded numeric is an enum",
    "maximum": "a bounded numeric is an enum",
    "exclusiveMinimum": "a bounded numeric is an enum",
    "exclusiveMaximum": "a bounded numeric is an enum",
    "multipleOf": "a bounded numeric is an enum",
    "minLength": "string-length constraints are unavailable; check length in the validator",
    "maxLength": "string-length constraints are unavailable; check length in the validator",
    "pattern": "pattern is not on the allowlist; validate the format in the validator",
    "oneOf": "use anyOf; oneOf is not on the allowlist",
    "not": "negation is not on the allowlist",
    "prefixItems": "tuple shapes are not on the allowlist; use an object with named fields",
    "maxItems": "array-length constraints are unavailable; check the count in the validator",
    "patternProperties": "dynamic keys cannot be closed; use a list of {key, value}",
    "propertyNames": "dynamic keys cannot be closed; use a list of {key, value}",
}

_SCALARS = (str, int, float, bool, type(None))

#: The string formats the providers document as supported in constrained mode.
FORMATS: frozenset[str] = frozenset({"date-time", "date", "time", "duration", "email", "uri", "uuid", "ipv4", "ipv6"})


def subset_violations(schema: Mapping[str, Any]) -> list[str]:
    """Every way ``schema`` leaves the ADR-0013 subset, as ``path: reason`` lines.

    Empty means conformant. The walk follows internal ``$ref`` to find
    recursion, and reports each violation once at the path where it occurs.
    """
    violations: list[str] = []
    _walk(schema, schema, "$", (), violations)
    return violations


def _walk(
    node: Any,
    root: Mapping[str, Any],
    path: str,
    ref_stack: tuple[str, ...],
    out: list[str],
) -> None:
    if not isinstance(node, Mapping):
        out.append(f"{path}: a schema must be an object, not {type(node).__name__}")
        return

    for key in node:
        if key in ALLOWED_KEYWORDS:
            continue
        reason = _NAMED_REASONS.get(key, "it is not on the allowlist")
        out.append(f'{path}: "{key}" is not in the ADR-0013 subset; {reason}')

    ref = node.get("$ref")
    if ref is not None:
        if not isinstance(ref, str) or not ref.startswith("#/"):
            out.append(f"{path}: $ref {ref!r} is not internal; only #/... references are allowed")
        elif ref in ref_stack:
            out.append(f"{path}: $ref {ref!r} is recursive; a tool schema is a tree")
        else:
            target = _resolve(root, ref)
            if target is None:
                out.append(f"{path}: $ref {ref!r} resolves to nothing")
            else:
                _walk(target, root, f"{path}->{ref}", (*ref_stack, ref), out)

    declared = node.get("type")
    if declared is not None and (not isinstance(declared, str) or declared not in TYPES):
        out.append(f"{path}: type {declared!r} is not one of the seven JSON types (use anyOf)")

    is_object = declared == "object" or any(
        k in node for k in ("properties", "required", "additionalProperties")
    )
    if is_object:
        extra = node.get("additionalProperties")
        if extra is not False:
            out.append(f"{path}: an object must declare additionalProperties: false")
            if isinstance(extra, Mapping):
                _walk(extra, root, f"{path}.additionalProperties", ref_stack, out)
        properties = node.get("properties", {})
        if not isinstance(properties, Mapping):
            out.append(f"{path}: properties must be an object")
            properties = {}
        for name, child in properties.items():
            _walk(child, root, f"{path}.{name}", ref_stack, out)
        for name in node.get("required", ()):
            if name not in properties:
                out.append(f"{path}: required names {name!r}, which is not a property")

    if "const" in node and not isinstance(node["const"], _SCALARS):
        out.append(f"{path}: const must be a scalar")

    fmt = node.get("format")
    if fmt is not None and fmt not in FORMATS:
        out.append(f"{path}: format {fmt!r} is not one the providers support; validate it in the validator")

    if "items" in node:
        if isinstance(node["items"], Mapping):
            _walk(node["items"], root, f"{path}[]", ref_stack, out)
        else:
            out.append(f"{path}: items must be one schema, not a list (no tuple shapes)")

    min_items = node.get("minItems")
    if min_items is not None and (isinstance(min_items, bool) or min_items not in (0, 1)):
        out.append(f"{path}: minItems must be 0 or 1, not {min_items!r}")

    enum = node.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not enum:
            out.append(f"{path}: enum must be a non-empty list")
        elif not all(isinstance(v, _SCALARS) for v in enum):
            out.append(f"{path}: enum must be over scalars")

    for combinator in ("anyOf", "allOf"):
        for i, child in enumerate(node.get(combinator, ())):
            _walk(child, root, f"{path}.{combinator}[{i}]", ref_stack, out)

    for name, child in node.get("$defs", {}).items():
        _walk(child, root, f"{path}.$defs.{name}", ref_stack, out)


def _resolve(root: Mapping[str, Any], ref: str) -> Any:
    node: Any = root
    for raw in ref[2:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")  # JSON-pointer escapes
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node
