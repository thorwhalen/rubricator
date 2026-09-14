"""Serving the prompt bundle: two verbs, on the same registry as everything else.

ADR-0003 says prompts ship as *content the runtime can serve*. These are the
verbs that serve it, and they are on :mod:`rubricator.surface` beside the
analysis verbs for the same reason those are: a surface that assembles its own
list is a surface that will disagree with the other one.

**Deterministic, like every other verb here.** Reading a file off disk and
returning its text needs no model, no clock and no network, which is what makes
"the connector hands Claude the same guidance the deployed agent uses" a fact
about one artifact rather than two that resemble each other.

**Why these are tools today and not native MCP prompts.** A Claude client
surfaces MCP ``prompts/*`` as slash commands, which is the better presentation
and is what ADR-0003's amendment is written against. The adapter this package
builds its connector with wires ``list_tools`` and ``call_tool`` only, with no
seam for ``prompts/*`` -- the gap that put the MCP-host question through ADR-0009
in the first place. Exposing the bundle as two deterministic verbs means the
content is servable from both surfaces *now*, over the registry that already
exists, and the upgrade to native prompts is a change in how these are
registered rather than a change to where prompts live or what they say.
"""

from __future__ import annotations

from typing import Any

from rubricator.prompts import prompts as _bundle

__all__ = ["prompts_list", "prompts_get"]


def prompts_list() -> dict[str, Any]:
    """Every prompt the runtime can serve, without their bodies.

    Bodies are excluded on purpose: a caller listing the bundle to choose one
    does not want several thousand words of instructions in the reply, and a
    listing that is cheap gets called.

    >>> [p['id'] for p in prompts_list()['prompts']]
    ['score-cell']
    """
    return {
        "prompts": [
            {
                "id": p.id,
                "title": p.title,
                "version": p.version,
                "stage": p.stage,
                "updated": p.updated,
                "missingCodes": list(p.missing_codes),
            }
            for p in sorted(_bundle().values(), key=lambda p: (p.stage or 0, p.id))
        ]
    }


def prompts_get(*, prompt_id: str) -> dict[str, Any]:
    """One prompt, with the text a model should be given.

    ``version`` travels with the body rather than being looked up separately,
    because a run's provenance has to record which wording produced it -- an
    evaluation number attached to "the score-cell prompt" with no version is a
    number nobody can reproduce (ADR-0008).

    >>> got = prompts_get(prompt_id='score-cell')
    >>> got['version'], got['body'].startswith('# Score one cell')
    (1, True)
    """
    bundle = _bundle()
    prompt = bundle.get(prompt_id)
    if prompt is None:
        known = ", ".join(sorted(bundle)) or "none -- the bundle is empty"
        raise KeyError(f'no prompt "{prompt_id}". This runtime serves: {known}')
    return {
        "id": prompt.id,
        "title": prompt.title,
        "version": prompt.version,
        "stage": prompt.stage,
        "updated": prompt.updated,
        "missingCodes": list(prompt.missing_codes),
        "body": prompt.body,
    }
