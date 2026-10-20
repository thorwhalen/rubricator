# enumerate-alternatives adherence runs

Five invented questions: three named alternatives (e1), look-alike labels (e2), a supplied source that mentions an alternative the user did not name (e3), nothing named (e4) and a request for candidates (e5). A subject following the `enumerate-alternatives` prompt sees only the question (and, in e3, the source) and writes the prompt's JSON block; `scripts/enumerate_alternatives_adherence.py` runs the block's `alternatives` through the real `alternatives_set` verb and grades it, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/enumerate_alternatives_scenarios.py docs/evaluation/enumerate-alternatives/scenarios.json
    python scripts/enumerate_alternatives_adherence.py docs/evaluation/enumerate-alternatives/scenarios.json docs/evaluation/enumerate-alternatives/2026-10-20/out-*.json

`scenarios.json` is generated from the hand-authored expectations in the script, and `tests/test_enumerate_alternatives_prompt.py` fails if the file drifts.

## 2026-10-20 — v1 ([#70](https://github.com/thorwhalen/rubricator/issues/70))

| arm | parses | feeds alternatives_set | keeps the stated | no unlicensed rows | duplicates kept and flagged | source candidate proposed with span | inference marked |
|---|---|---|---|---|---|---|---|
| **v1, Sonnet** | 5/5 | 5/5 | 3/3 | 5/5 | 1/1 | 1/1 | 5/5 |

- **Stored output is the blocks only.** The five replies were each a few lines of prose and the JSON block; the file keeps the blocks (copied from the replies) and drops the prose, which nothing grades.
- **Not established:** one run, one model, no baseline arm (no prompt), five scenarios the prompt author wrote and graded. The subjects had no tools, so nothing here exercises `corpus_search` or the real hand-off to `alternatives_set`; the source in e3 was handed over in the message. Whether the prompt changes behaviour against a bare model is the changelog's hypothesis and is untested.
- **The source slot is still missing.** An alternative has no field for where it came from, so the marks live in `description` (`Stated:` / `Source:` / `Own inference:`), and `alternatives_set` cannot yet flag an unsourced row itself (see its docstring, #55).
