"""The tool surface: one list, and every surface dispatches from it.

This module is **data**. It names the verbs that are exposed, and nothing else.
The CLI, the MCP connector and anything later all read this list, because
authoring two lists separately is exactly how two surfaces come to disagree
while a comment claims they cannot -- a failure this ecosystem has an in-house
post-mortem for, whose verdict was that "by construction" was not a mechanism.

**The core imports no MCP.** Verbs are plain functions taking JSON-able
arguments and returning JSON-able dicts (:mod:`rubricator.tools.analysis`). The
only thing they need that is not JSON-able is the store, and :func:`bind` is
where that is supplied -- once, from the composition root, for every surface at
the same time.

>>> from rubricator.compose import build_runtime
>>> verbs = bind(build_runtime(blobs={}))
>>> sorted(verbs)[:3]
['analysis_open', 'check_citations', 'criteria_set']
>>> verbs['analysis_open'](analysis_id='a1', question='which?')
{'analysisId': 'a1', 'created': True}
"""

from __future__ import annotations

import inspect
import typing
from functools import partial
from typing import Any, Callable, Mapping, Optional

from rubricator.compose import Runtime

__all__ = ["TOOL_REFS", "NEEDS_CLOCK", "bind"]

#: The exposed verbs, as string references into the tool layer.
#:
#: Strings rather than imported callables so that this list can be read -- by a
#: doc generator, by a manifest check, by a human -- without importing anything,
#: and so that ``py2mcp`` can build a server from it without the core ever
#: importing MCP.
TOOL_REFS: tuple[str, ...] = (
    "rubricator.tools.analysis:analysis_open",
    "rubricator.tools.analysis:frame_set",
    "rubricator.tools.analysis:criteria_set",
    "rubricator.tools.analysis:measures_write",
    "rubricator.tools.analysis:measures_mark_missing",
    "rubricator.tools.analysis:report_completeness",
    "rubricator.tools.citations:check_citations",
    "rubricator.tools.traversal:plan_traversal",
)

#: Verbs that need a moment, and take it as ``at``.
#:
#: Listed here rather than discovered by signature inspection, because "this verb
#: needs the clock" is a fact about the surface contract and should be readable
#: without running anything. A verb that grows an ``at`` argument and is not
#: added here will be called without one and fail loudly, which is the right
#: direction: the alternative is a surface silently passing ``None``.
NEEDS_CLOCK: frozenset[str] = frozenset({"measures_write", "measures_mark_missing"})

#: Verbs that take the store as their first argument.
_NEEDS_STORE: frozenset[str] = frozenset({
    "analysis_open", "frame_set", "criteria_set",
    "measures_write", "measures_mark_missing", "report_completeness",
})


def _resolve(ref: str) -> tuple[str, Callable[..., Any]]:
    module_name, _, attr = ref.partition(":")
    module = __import__(module_name, fromlist=[attr])
    return attr, getattr(module, attr)


def bind(runtime: Runtime) -> Mapping[str, Callable[..., Any]]:
    """The verbs, with the store and the clock supplied.

    The result is a plain mapping of name to callable, each taking only JSON-able
    keyword arguments -- which is what every surface needs and what none of them
    should have to assemble for itself.

    The clock is bound here rather than defaulted inside a verb, which is the
    whole point of :mod:`rubricator.clock`: a tool that reaches for the time
    cannot be replayed, and the determinism test denies it the import.

    **The bound callables are real functions with a corrected signature**, not
    ``functools.partial`` objects. That is not cosmetic: an MCP host builds a
    tool's JSON schema by inspecting the signature, and a partial's signature
    still lists the parameter that was bound -- so the connector would advertise
    ``store`` as something a caller must supply, and a caller that tried would be
    handing a Mapping across a JSON boundary.
    """
    verbs: dict[str, Callable[..., Any]] = {}
    for ref in TOOL_REFS:
        name, fn = _resolve(ref)
        bound_names: set[str] = set()
        bound: Callable[..., Any] = fn
        if name in _NEEDS_STORE:
            bound = partial(bound, runtime.store)
            bound_names.add(_first_parameter(fn))
        if name in NEEDS_CLOCK:
            bound = _with_default_moment(bound, runtime.now)
            bound_names.add("at")
        verbs[name] = _as_function(bound, fn, bound_names)
    return verbs


def _first_parameter(fn: Callable[..., Any]) -> str:
    return next(iter(inspect.signature(fn).parameters))


def _as_function(
    bound: Callable[..., Any], original: Callable[..., Any], hide: set[str]
) -> Callable[..., Any]:
    """A real function over ``bound``, advertising a corrected signature.

    Two things have to be right for an MCP host to build a usable tool schema,
    and both are easy to miss:

    1. **The signature must not list what has already been supplied.** A
       ``functools.partial`` still reports the parameter it bound, so the
       connector would advertise ``store`` as a caller's responsibility -- and a
       caller that obliged would be handing a Mapping across a JSON boundary.
    2. **The annotations must be resolved, not strings.** These modules use
       ``from __future__ import annotations``, so every annotation is a string
       that only the *defining* module's globals can evaluate. A closure defined
       here carries this module's globals instead, and the host's
       ``get_type_hints`` call fails on the first name it cannot find. So the
       hints are resolved against the original and copied over concretely.

    ``at`` is not removed but made optional: a caller replaying or backfilling
    should still be able to state the moment it is reconstructing. What it must
    not have to do is invent one for the ordinary case.
    """
    signature = inspect.signature(original)
    hints = typing.get_type_hints(original)

    parameters = []
    annotations: dict[str, Any] = {}
    for pname, parameter in signature.parameters.items():
        if pname in hide and pname != "at":
            continue
        if pname == "at" and pname in hide:
            parameter = parameter.replace(default=None, annotation=Optional[str])
            annotations[pname] = Optional[str]
        elif pname in hints:
            annotations[pname] = hints[pname]
        parameters.append(parameter)
    if "return" in hints:
        annotations["return"] = hints["return"]

    def call(**kwargs: Any) -> Any:
        # A caller that passed `at=None` explicitly means "use the default",
        # which is what dropping the key achieves.
        if kwargs.get("at") is None:
            kwargs.pop("at", None)
        return bound(**kwargs)

    call.__name__ = getattr(original, "__name__", "call")
    call.__qualname__ = call.__name__
    call.__doc__ = getattr(original, "__doc__", None)
    call.__module__ = getattr(original, "__module__", __name__)
    call.__annotations__ = annotations
    call.__signature__ = signature.replace(parameters=parameters)  # type: ignore[attr-defined]
    return call


def _with_default_moment(fn: Callable[..., Any], now: Callable[[], str]) -> Callable[..., Any]:
    """Supply ``at`` when the caller did not.

    A caller that *does* pass one wins, so a replay or a backfill can state the
    moment it is reconstructing. What is not possible is the verb finding a clock
    on its own.
    """

    def call(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("at", now())
        return fn(*args, **kwargs)

    return call
