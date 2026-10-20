# review adherence runs

Five analyses on an invented domain (three fictional bicycle docks, one small town deciding), each built by driving the real verbs to a scored state and recording what the `review` prompt's one read returns: `report_weaknesses` with a budget of 5. A subject following the prompt sees only that result and writes its reply; `scripts/review_adherence.py` grades the block the prompt asks for, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/review_scenarios.py docs/evaluation/review/scenarios.json
    python scripts/review_adherence.py docs/evaluation/review/scenarios.json docs/evaluation/review/2026-10-20/out-*.json

`scenarios.json` is generated, and `tests/test_review_prompt.py` fails if the tools stop returning it. Each scenario's point is asserted by hand in the generator; the expectations are read off the tool's result.

| id | the state | what a faithful review says |
|---|---|---|
| r1 | two docks incomparable, four cells one level from a dominance, one of them cited only by an unlocatable forum quote | re-score the four; the thinly cited pivotal cell first |
| r2 | weather sealing scored 1 and 5 by two scorers on two docks; the one pivotal cell is on it | nothing to re-score; redefine weather sealing; the picture turns on that criterion |
| r3 | one dock two levels ahead everywhere; the three columns correlate at 1.0 | no cell is pivotal; the correlation is a diagnostic, not redundancy |
| r4 | a floor on theft resistance (one dock under it, one never tested) and a confidence measure with two cells at its lowest level | the vetoed and untested floors; one pivotal cell |
| r5 | every cell cited by a span, one dock dominant | nothing weak |

## 2026-10-20 — v1 ([#74](https://github.com/thorwhalen/rubricator/issues/74))

| arm | kept apart | complete | rescore right | redefine right | most right | vetoes right | no redundancy reading | no suggested score |
|---|---|---|---|---|---|---|---|---|
| **v1, Sonnet** | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| **v1, Haiku** | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| form only, Sonnet | 5/5 | 5/5 | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 |

- **Kept apart, read first: 5/5 in every arm.** No reply sent a cell of a criterion to redefine back for re-scoring.
- **The form-only baseline** (`baseline.md`: the block and nothing else; its correlations line does not say "none of them a redundancy finding") misses one: in r4 it added the two low-confidence cells to the re-score line beside the tool's plan. On these five scenarios it does **not** show the changelog's hypothesis. `report_weaknesses` already keeps redefine out of rescore, and every correlation row carries its own note, so the tool's output does most of what the prompt asks; no arm read a correlation as redundancy or suggested a score.
- **Grader fixed after the run.** The first grade scored "no redundancy reading" 4/5 for Haiku and for the baseline, on "reflects judge carry-over rather than redundancy" and "say nothing about redundancy": both the opposite of the failure. The check now treats "rather than", "instead of" and "nothing" as negation (tested), and the table is the re-grade of the same outputs.
- **Not established:** one run per arm, all five scenarios in one context; the scenarios are the prompt author's; nothing grades the paragraph's quality, what evidence it names for the pivotal cell, or whether it keeps source, summary and inference apart. Five scenarios are an adherence check, not a benchmark.
