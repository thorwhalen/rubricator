# run-analysis adherence runs

Eight decision points of one run on an invented domain (three fictional compost tumblers, one community garden deciding), each built by driving the real verbs to a state and recording what the orchestrating session has seen there: the conversation so far and the results of the calls it just made. A subject following the `run-analysis` prompt writes its next reply; `scripts/run_analysis_adherence.py` grades the Stage / Scope / Next block that reply ends with, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/run_analysis_scenarios.py docs/evaluation/run-analysis/scenarios.json
    python scripts/run_analysis_adherence.py docs/evaluation/run-analysis/scenarios.json docs/evaluation/run-analysis/2026-10-20/out-*.json

`scenarios.json` is generated, and `tests/test_run_analysis_prompt.py` fails if the tools stop returning it. Each scenario's state is asserted in the generator; the expectations are stated there by hand.

| id | the point in the run | the next step a faithful reply names |
|---|---|---|
| a1 | a question and three brochures; nothing called yet | `frame` (or `alternatives` / `criteria`): never scoring |
| a2 | criteria written; the user asked for "the matrix quickly", which is not an instruction to skip | `confirm` |
| a3 | the user said to skip the check; the analysis was opened with the skip | `score`, all four criteria |
| a4 | confirmed, with "score only durability and upkeep cost for now, leave the other two for later" | `score` the two; the other two marked `deferred` with `measures_mark_missing` |
| a5 | the two scoped columns written, the other two deferred (the tool's summary says "score or mark the outstanding cells") | `review`, the set-aside two still set aside |
| a6 | every cell scored | `review`, not `stop` |
| a7 | confirmed and partly scored, then a criterion added: `frame_confirm` asks again | `confirm` |
| a8 | `report_weaknesses` returned | the review block, then `stop` |

## 2026-10-20 — v1 ([#77](https://github.com/thorwhalen/rubricator/issues/77))

| arm | gate held | complete | next right | scope right | deferred on record | closes with review |
|---|---|---|---|---|---|---|
| **v1, Sonnet** | 3/3 | 8/8 | 8/8 | 5/5 | 1/1 | 3/3 |
| **v1, Haiku** | 3/3 | 8/8 | 8/8 | 5/5 | 1/1 | 3/3 |
| form only, Sonnet | 3/3 | 8/8 | 8/8 | 5/5 | 1/1 | 3/3 |

- **Gate held, read first: 3/3 in every arm.** No reply scored before a confirmation, on a hurry, or after a criterion was added.
- **The form-only baseline** (`baseline.md`: the six stage names and the block, nothing else) also scores full marks. On these eight points the changelog's hypothesis is **not shown**: `frame_confirm`'s instructions, `measures_write`'s refusal and the summaries' own "next" carry the gate and the order, and the block's `Scope ... set aside` line on its own prompts a reply to record the deferred criteria. What the prompt adds that the baseline does not is not graded here: the honesty clause, handing each stage to its prompt, the note quoting the user on a deferred mark, and not taking up set-aside cells unasked after the review.
- **Fixture fixed after the first Haiku run.** In a3 the first fixture showed `analysis_open`'s result ("no alternatives and no criteria yet") and not the alternatives written after it; Haiku read it literally and asked for the alternatives (next right 7/8, `out-v1-haiku-first.json`). a3 now carries the frame view read after `alternatives_set`; the Haiku row is the re-run on the fixed fixtures. The Sonnet and baseline arms saw the first fixture and named `score` there.
- **Not established:** one run per arm, all eight scenarios in one context; the scenarios are the prompt author's; each is a single turn, not a whole run, so nothing here shows the prompt carries a model through six stages without drifting; nothing grades the prose.
