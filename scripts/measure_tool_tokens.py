"""Measure the token cost of the tool definitions, and print what to record.

ADR-0009 and ADR-0026 require the cost of the tool definitions to be
**measured** with the provider's token counter, not estimated from bytes. This
script sends the exact definitions a client sends -- name, description, input
schema -- to that counter and prints the ``MEASURED`` block for
``rubricator/surface/frozen.py``. A test pins the byte size of the live
definitions to the recorded one, so when the definitions change this script
has to be run again and its output pasted in.

Run it from a shell holding ``ANTHROPIC_API_KEY``::

    python scripts/measure_tool_tokens.py

This is the one place in the repository that touches a provider SDK directly.
ADR-0019 routes all **LLM access** through the local ``aix`` facade; counting
tokens is not inference, the facade has no counter, and the script ships no
part of the package. The exception is stated here so nobody has to rediscover
it, and it is filed against the facade.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date

from rubricator.surface.frozen import FROZEN_TOOLS, advertised, definitions, definitions_bytes

#: The model the count is taken against. A token count is model-specific, and
#: the recorded block names it so the number can be reproduced.
MODEL = os.environ.get("RUBRICATOR_COUNT_MODEL", "claude-sonnet-5-5")


def _count(tools: list[dict]) -> int:
    import anthropic

    client = anthropic.Anthropic()
    result = client.messages.count_tokens(
        model=MODEL,
        tools=tools,
        messages=[{"role": "user", "content": "."}],
    )
    return int(result.input_tokens)


def main() -> int:
    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY is not set; nothing measured.", file=sys.stderr)
        return 2
    # The one-character message costs a few tokens of its own; measured once with
    # no tools and subtracted, so the figure is the definitions alone.
    baseline = _count([])
    live, whole = advertised(), FROZEN_TOOLS
    block = {
        "measuredAt": date.today().isoformat(),
        "model": MODEL,
        "advertised": {
            "tools": len(live),
            "tokens": _count(definitions(live)) - baseline,
            "bytes": definitions_bytes(live),
        },
        "wholeSurface": {
            "tools": len(whole),
            "tokens": _count(definitions(whole)) - baseline,
            "bytes": definitions_bytes(whole),
        },
    }
    print("MEASURED: Mapping[str, Any] = " + json.dumps(block, indent=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
