# frame adherence runs

Five invented questions: four deliberately thin or ambiguous (a coffee grinder, "we" and a reading room, a bare database question, a ranking for a board) and one that states its decider, decision and bounds. A subject following the `frame` prompt sees only the question and writes the prompt's JSON block; `scripts/frame_adherence.py` runs the block through the real `frame_set` verb and grades it, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/frame_scenarios.py docs/evaluation/frame/scenarios.json
    python scripts/frame_adherence.py docs/evaluation/frame/scenarios.json docs/evaluation/frame/2026-10-20/out-*.json

`scenarios.json` is generated from the hand-authored expectations in the script (there is no tool output to read them off), and `tests/test_frame_prompt.py` fails if the file drifts.

## 2026-10-20 — v1 ([#69](https://github.com/thorwhalen/rubricator/issues/69))

| arm | parses | feeds frame_set | names the ambiguities | no invented decider | no placeholder | no false none |
|---|---|---|---|---|---|---|
| **v1, Sonnet** | 5/5 | 5/5 | 4/4 | 5/5 | 5/5 | 4/4 |

- **Grader fixed after the run.** The first grade scored f4 down on two counts that were the grader's: the subject named the food bank board as decider while saying in the same field that the message does not say whether the board decides (the scenario now allows a board decider, `deciderMayBe`), and it asked what the ranking is "judged on", which the topic pattern missed. The table is the re-grade of the same output.
- **Not established:** one run, one model, no baseline arm (no prompt), five scenarios the prompt author wrote; nothing grades the quality of the ambiguity wording, only that each open point the author found was named. Whether the prompt changes behaviour against a bare model is the changelog's hypothesis and is untested here.
