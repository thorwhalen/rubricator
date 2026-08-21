# Prompts

Prompts are **content**, not strings embedded in a loop (ADR-0003). Both runtimes serve the same
files: the MCP server exposes them as prompts/resources, and the deployed agent loads them.

Expected set, one file each, versioned:

| Prompt | Stage | Job |
|---|---|---|
| `frame` | 1 | Establish subject, decision, decider; surface ambiguity instead of resolving it silently |
| `enumerate-alternatives` | 2 | Extract candidates from context; flag omissions and near-duplicates |
| `propose-criteria` | 3 | Criteria with definitions, polarity, level of measurement, veto status; flag overlaps |
| `score-cell` | 5 | **The default** (ADR-0011). One cell: score, confidence, one-line justification, evidence spans |
| `score-column` | 5 | One criterion across all alternatives. **Not the default** — it survives only as arm 2 of the ADR-0008 evaluation harness, awaiting validation (ADR-0011) |
| `review` | 6 | Self-critique: thin evidence, overlapping criteria, what would most change the picture |
| `audit-existing` | — | Given an analysis someone else made, find its weaknesses |

The settled surface is **ten** prompts, not the seven above: `run-analysis`, `confirm-frame`
(the ADR-0005 step-4 gate) and `resume` (ADR-0017) join the table when they are written.

Each prompt file carries a version and a changelog entry. When a prompt changes, the evaluation
suite (ADR-0008) runs — that is the whole reason it exists.

**Every prompt must state the honesty rule** from ADR-0006 in its own words: prefer a qualified
`unknown` to a plausible guess, cite spans not documents, and never present inference as source.
