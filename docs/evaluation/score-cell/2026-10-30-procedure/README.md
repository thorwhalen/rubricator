# score-cell v6, procedure scenarios (#279)

`out-proc-v6-<model>.json`: the twelve scenarios of `../procedure.json`, answered by one subagent per model (haiku, sonnet) given `score-cell.md` version 6, `../2026-10-14-procedure/tool-context.md` and the packet (`python scripts/score_cell_procedure.py --packet OUT.json`), and nothing else. Graded with `python scripts/score_cell_procedure.py out-proc-v6-<model>.json`: both 12/12 on valid, true, left out and no independence.

`p12-round-refused` became `p12-same-sweep-other-prior`: a round is keyed by (number, prior), so a sweep keeps its number whatever it does with the prior (ADR-0018 amendment of 2026-10-30). One run per model.
