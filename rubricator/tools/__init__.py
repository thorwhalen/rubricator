"""The MCP tool surface: deterministic tools, and only deterministic tools.

Every function here satisfies, and is tested for, the contract in ADR-0003:

1. no model call -- not a completion, not a rerank;
2. no embedding call, because an embedding *is* a model call, and retrieval that
   depends on one cannot run in the connector;
3. same input twice gives byte-identical output -- no wall clock, no unseeded
   randomness, no set-iteration order leaking into a result;
4. no hidden network.

Where a step genuinely needs judgement it is not a tool. It is a *prompt* the
caller's model runs, plus a deterministic tool that validates what came back.
"""

from rubricator.tools.citations import (
    CitationCheck,
    check_citation,
    check_citations,
    normalise_for_match,
)
from rubricator.tools.traversal import TraversalPlan, plan_traversal

__all__ = [
    "CitationCheck",
    "check_citation",
    "check_citations",
    "normalise_for_match",
    "TraversalPlan",
    "plan_traversal",
]
