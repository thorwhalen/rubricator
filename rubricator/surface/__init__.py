"""The tool surface: one registry, one frozen contract, and every surface dispatches from it.

Two modules of **data** and one of mechanism:

- :mod:`rubricator.surface.frozen` is the frozen surface of ADR-0026 -- every
  tool's name, ``inputSchema``, ``outputSchema``, contract and cut rank, whether
  it is implemented yet or not;
- :mod:`rubricator.surface.subset` is the ADR-0013 schema subset as a checker;
- this module binds the implemented verbs to a runtime and **validates every
  call against the frozen contract**, in both directions.

:data:`TOOL_REFS` names the verbs that are exposed, as strings, and nothing
else. The CLI, the MCP connector and anything later all read this list,
because authoring two lists separately is exactly how two surfaces come to
disagree while a comment claims they cannot -- a failure this ecosystem has an
in-house post-mortem for, whose verdict was that "by construction" was not a
mechanism.

**The core imports no MCP.** Verbs are plain functions taking JSON-able
arguments and returning JSON-able dicts. The only things they need that are
not JSON-able -- the store, the clock, the id minter -- are supplied by
:func:`bind`, once, from the composition root, for every surface at once.

>>> from rubricator.compose import build_runtime
>>> from rubricator.ids import sequential_ids
>>> verbs = bind(build_runtime(blobs={}, new_id=sequential_ids("a")))
>>> sorted(verbs)[:3]
['aggregate_assertions', 'alternatives_set', 'analysis_open']
>>> verbs['analysis_open'](question='which?')['analysisId']
'a-1'
>>> verbs['analysis_open'](analysis_id='a-1')['created']
False
>>> verbs['frame_set'](analysis_id='a-1', ambiguities=[], colour='blue')
Traceback (most recent call last):
    ...
ValueError: refused: frame_set: at $: Additional properties are not allowed ('colour' was unexpected). Allowed here: ambiguities, analysis_id, context, decider, decision
"""

from __future__ import annotations

import inspect
import re
import typing
from functools import partial
from typing import Any, Callable, Mapping, Optional

from rubricator.compose import Runtime
from rubricator.surface.frozen import FROZEN_TOOLS, ToolSpec, advertised, describe, frozen
from rubricator.surface.subset import subset_violations

__all__ = [
    "TOOL_REFS", "NEEDS_CLOCK", "NEEDS_ID", "bind", "ContractViolation",
    "FROZEN_TOOLS", "ToolSpec", "advertised", "describe", "frozen", "subset_violations",
]

#: The exposed verbs, as string references into the tool layer.
#:
#: Strings rather than imported callables so that this list can be read -- by a
#: doc generator, by a manifest check, by a human -- without importing anything,
#: and so that ``py2mcp`` can build a server from it without the core ever
#: importing MCP. Every name here has a row in :data:`FROZEN_TOOLS`, and a test
#: holds the two together.
TOOL_REFS: tuple[str, ...] = (
    "rubricator.tools.analysis:analysis_open",
    "rubricator.tools.analysis:frame_set",
    "rubricator.tools.analysis:alternatives_set",
    "rubricator.tools.analysis:criteria_set",
    "rubricator.tools.analysis:measures_write",
    "rubricator.tools.analysis:measures_mark_missing",
    "rubricator.tools.analysis:report_completeness",
    "rubricator.tools.aggregate:aggregate_assertions",
    "rubricator.tools.citations:check_citations",
    "rubricator.tools.traversal:plan_traversal",
    "rubricator.tools.prompts:prompts_list",
    "rubricator.tools.prompts:prompts_get",
)

#: Verbs that need a moment, and take it as ``at``.
#:
#: Listed here rather than discovered by signature inspection, because "this verb
#: needs the clock" is a fact about the surface contract and should be readable
#: without running anything. A verb that grows an ``at`` argument and is not
#: added here will be called without one and fail loudly, which is the right
#: direction: the alternative is a surface silently passing ``None``.
NEEDS_CLOCK: frozenset[str] = frozenset({"measures_write", "measures_mark_missing"})

#: Verbs that mint an ``analysis_id`` when the caller gives none (ADR-0017).
NEEDS_ID: frozenset[str] = frozenset({"analysis_open"})

#: Verbs that take the store as their first argument.
_NEEDS_STORE: frozenset[str] = frozenset({
    "analysis_open", "frame_set", "alternatives_set", "criteria_set",
    "measures_write", "measures_mark_missing", "report_completeness", "aggregate_assertions",
})


#: Refusals that must run *before* the schema check, because the schema can only
#: say "not one of" where the contract owes the caller a reason. Each takes the
#: store and the raw arguments and raises ``ValueError`` or returns ``None``.
#: ``aggregate_assertions``'s frozen enum already excludes a mean; ADR-0011 owes
#: the caller the level of measurement that makes it illegal (#97).
_PRECHECKS: Mapping[str, str] = {
    "aggregate_assertions": "rubricator.tools.aggregate:refuse_a_mean",
}


class ContractViolation(RuntimeError):
    """A verb returned something its frozen ``outputSchema`` does not admit.

    A server bug, not a caller's: the caller did everything right and the
    result still does not match the envelope the surface advertised. Raised
    rather than passed through, because MCP says a server MUST return
    structured results conforming to its declared ``outputSchema``.
    """


def _resolve(ref: str) -> tuple[str, Callable[..., Any]]:
    module_name, _, attr = ref.partition(":")
    module = __import__(module_name, fromlist=[attr])
    return attr, getattr(module, attr)


def bind(runtime: Runtime, *, validate: bool = True) -> Mapping[str, Callable[..., Any]]:
    """The verbs, with the store, the clock and the id minter supplied.

    The result is a plain mapping of name to callable, each taking only JSON-able
    keyword arguments -- which is what every surface needs and what none of them
    should have to assemble for itself.

    **Every bound verb validates its call against the frozen contract.** The
    arguments are checked against the row's ``inputSchema`` before the verb runs
    -- so an extra key, a wrong type or a missing field is refused at the
    boundary with its JSON path, in the CLI exactly as over MCP -- and the result
    is checked against the ``outputSchema`` before it is returned, so the
    envelope the surface advertises is the envelope it keeps.
    ``validate=False`` is for a Python caller that has already validated, never
    for a surface.

    The clock and the id minter are bound here rather than defaulted inside a
    verb, which is the whole point of :mod:`rubricator.clock` and
    :mod:`rubricator.ids`: a tool that reaches for the time or for randomness
    cannot be replayed, and the determinism test denies it the import.

    **The bound callables are real functions with a corrected signature**, not
    ``functools.partial`` objects. An MCP host builds a tool's JSON schema by
    inspecting the signature, and a partial's signature still lists the
    parameter that was bound -- so the connector would advertise ``store`` as
    something a caller must supply.
    """
    rows = frozen()
    verbs: dict[str, Callable[..., Any]] = {}
    for ref in TOOL_REFS:
        name, fn = _resolve(ref)
        spec = rows[name]
        bound_names: set[str] = set()
        bound: Callable[..., Any] = fn
        if name in _NEEDS_STORE:
            bound = partial(bound, runtime.store)
            bound_names.add(_first_parameter(fn))
        defaulted: dict[str, Callable[[], str]] = {}
        if name in NEEDS_CLOCK:
            defaulted["at"] = runtime.now
        if name in NEEDS_ID:
            defaulted["analysis_id"] = runtime.new_id
        if defaulted:
            bound = _with_defaults(bound, defaulted)
        precheck = None
        if name in _PRECHECKS:
            precheck = partial(_resolve(_PRECHECKS[name])[1], runtime.store)
        verbs[name] = _as_function(
            bound, fn, bound_names, set(defaulted), spec, validate, precheck=precheck
        )
    return verbs


def _first_parameter(fn: Callable[..., Any]) -> str:
    return next(iter(inspect.signature(fn).parameters))


def _as_function(
    bound: Callable[..., Any],
    original: Callable[..., Any],
    hide: set[str],
    defaulted: set[str],
    spec: ToolSpec,
    validate: bool,
    *,
    precheck: Callable[[Mapping[str, Any]], None] | None = None,
) -> Callable[..., Any]:
    """A real function over ``bound``, advertising a corrected signature.

    Two things have to be right for an MCP host to build a usable tool schema,
    and both are easy to miss:

    1. **The signature must not list what has already been supplied.** A
       ``functools.partial`` still reports the parameter it bound.
    2. **The annotations must be resolved, not strings.** These modules use
       ``from __future__ import annotations``, so every annotation is a string
       that only the *defining* module's globals can evaluate. A closure defined
       here carries this module's globals instead, and the host's
       ``get_type_hints`` call fails on the first name it cannot find. So the
       hints are resolved against the original and copied over concretely.

    A defaulted parameter (``at``, ``analysis_id``) is not removed but made
    optional: a caller replaying or backfilling should still be able to state
    the moment or the id it is reconstructing. What it must not have to do is
    invent one for the ordinary case.
    """
    signature = inspect.signature(original)
    hints = typing.get_type_hints(original)

    parameters = []
    annotations: dict[str, Any] = {}
    for pname, parameter in signature.parameters.items():
        if pname in hide:
            continue
        if pname in defaulted:
            parameter = parameter.replace(default=None, annotation=Optional[str])
            annotations[pname] = Optional[str]
        elif pname in hints:
            annotations[pname] = hints[pname]
        parameters.append(parameter)
    if "return" in hints:
        annotations["return"] = hints["return"]

    input_check = _validator(spec.input_schema) if validate else None
    output_check = _validator(spec.output_schema) if validate else None

    optional = set(spec.input_schema["properties"]) - set(spec.input_schema["required"])

    def call(**kwargs: Any) -> Any:
        # A None for an optional parameter means "not given": an MCP host fills
        # a verb's Python defaults before calling, and `at=None` or
        # `analysis_id=None` passed explicitly means "use the runtime's". No
        # input schema on the surface admits null, so dropping the key is the
        # one reading that agrees with both the row and the caller.
        for key in optional:
            if key in kwargs and kwargs[key] is None:
                kwargs.pop(key)
        if precheck is not None:
            precheck(kwargs)
        if input_check is not None:
            _refuse_invalid(spec.name, input_check, kwargs)
        result = bound(**kwargs)
        if output_check is not None:
            problems = sorted(output_check.iter_errors(result), key=lambda e: list(e.path))
            if problems:
                raise ContractViolation(
                    f"{spec.name} returned a result its outputSchema does not admit: "
                    + "; ".join(f"at {_path(e)}: {e.message}" for e in problems)
                )
        return result

    call.__name__ = getattr(original, "__name__", "call")
    call.__qualname__ = call.__name__
    call.__doc__ = describe(spec)
    call.__module__ = getattr(original, "__module__", __name__)
    call.__annotations__ = annotations
    call.__signature__ = signature.replace(parameters=parameters)  # type: ignore[attr-defined]
    return call


def _with_defaults(
    fn: Callable[..., Any], suppliers: Mapping[str, Callable[[], str]]
) -> Callable[..., Any]:
    """Supply each defaulted argument when the caller did not.

    A caller that *does* pass one wins, so a replay or a backfill can state the
    moment or the id it is reconstructing. What is not possible is the verb
    finding a clock or a random source on its own.
    """

    def call(*args: Any, **kwargs: Any) -> Any:
        for key, supply in suppliers.items():
            if key not in kwargs:
                kwargs[key] = supply()
        return fn(*args, **kwargs)

    return call


#: RFC 3339 `date-time`: date, "T", time, optional fraction, Z or an offset.
_RFC3339 = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})[Tt](?P<time>\d{2}:\d{2}:\d{2})(?P<frac>\.\d+)?"
    r"(?P<zone>[Zz]|[+-]\d{2}:\d{2})\Z"
)


def _fromisoformat_friendly(m: "re.Match[str]") -> str:
    """The matched moment in the one spelling every supported Python parses."""
    # Exactly six digits: 3.10's parser accepts only 3 or 6, 3.12 accepts 1-6.
    digits = (m.group("frac") or ".")[1:7]
    frac = f".{digits.ljust(6, '0')}" if digits else ""
    zone = m.group("zone")
    return f"{m.group('date')}T{m.group('time')}{frac}{'+00:00' if zone in 'Zz' else zone}"


def _validator(schema: Mapping[str, Any]):
    from jsonschema import Draft202012Validator, FormatChecker

    checker = FormatChecker(formats=())

    @checker.checks("date-time", raises=ValueError)
    def _is_rfc3339(value: Any) -> bool:
        # Checked here, in the surface, so the tool layer stays clock-free: a
        # moment a caller states must at least be a moment. A fixed grammar
        # first, because `fromisoformat` accepts different things on 3.10 and
        # 3.12 and the CI matrix runs both; then a parse, for the calendar.
        from datetime import datetime

        if not isinstance(value, str):
            return True
        if not _RFC3339.match(value):
            raise ValueError(f"{value!r} is not an RFC 3339 date-time such as 2026-08-22T12:00:00Z")
        datetime.fromisoformat(_RFC3339.sub(_fromisoformat_friendly, value))
        return True

    return Draft202012Validator(dict(schema), format_checker=checker)


def _path(error: Any) -> str:
    return "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)


def _refuse_invalid(name: str, validator: Any, arguments: Mapping[str, Any]) -> None:
    """Raise the first problem with its path and what is allowed there."""
    error = next(iter(sorted(validator.iter_errors(arguments), key=lambda e: list(e.path))), None)
    if error is None:
        return
    message = f"refused: {name}: at {_path(error)}: {error.message}"
    properties = error.schema.get("properties") if isinstance(error.schema, Mapping) else None
    if error.validator == "additionalProperties" and properties:
        message += f". Allowed here: {', '.join(sorted(properties))}"
    raise ValueError(message)
