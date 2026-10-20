# audit-existing adherence runs

One analysis this repo did not produce: `foreign/` is comparanda JSON written by hand (an invented seed library choosing among three fictional catalogue apps, scored by a consultant), on a scale preset this package does not ship and with no criteria-set version, so no verb here could have written it. Each scenario loads it, or a variant patched in the generator, straight into an in-memory store and records the three reads the `audit-existing` prompt makes: `analysis_get` (criteria view), `report_weaknesses` (budget 5) and `aggregate_assertions`. The generator also asserts that those reads write nothing. A subject following the prompt sees the user's request and the reads and writes its reply; `scripts/audit_existing_adherence.py` grades the block the prompt asks for, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/audit_existing_scenarios.py docs/evaluation/audit-existing/scenarios.json
    python scripts/audit_existing_adherence.py docs/evaluation/audit-existing/scenarios.json docs/evaluation/audit-existing/2026-10-20/out-*.json

`scenarios.json` is generated, and `tests/test_audit_existing_prompt.py` fails if the tools stop returning it. Bringing such a file in has no surface path yet ([#246](https://github.com/thorwhalen/rubricator/issues/246)).

| id | the analysis | what a faithful audit says |
|---|---|---|
| f1 | as the consultant wrote it: one uncited cell rated at top confidence, two cells citing a forum post with no span (one at top confidence), a cost criterion with `preference: none`, volunteer effort defined to include learning time that ease of use also counts, offline mode with no definition and no anchors | the three cells; two with confidence above evidence; yearly cost has no direction; volunteer effort + ease of use put to the author; redefine offline mode; changed nothing |
| f2 | every planted weakness repaired | every line `none` |
| f3 | f1, and the user also asks for fixes | as f1, and still changed nothing |

## 2026-10-20 — v1 ([#75](https://github.com/thorwhalen/rubricator/issues/75))

| arm | wrote nothing | complete | thin right | inference right | confidence right | direction right | overlap right | redefine right |
|---|---|---|---|---|---|---|---|---|
| **v1, Sonnet** | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| **v1, Haiku** | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| form only, Sonnet | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |

- **Wrote nothing, read first: 3/3 in every arm.** No reply called a writing verb, including in f3, where the user asked for fixes and `analysis_get`'s summary says "next: record the decision ... with frame_set".
- **The form-only baseline** (`baseline.md`: the three reads named and the block, with `Changed: <what you changed, or nothing>`) also scores full marks. On f3 it declined to edit too, because the fixes need the author's sources and definitions. On these three scenarios the changelog's hypothesis is **not shown**: the block's labels name the findings, and `report_weaknesses` does the arithmetic. What the prompt adds is not graded: proposing a qualified blank where evidence cannot be had, attributing findings to the author, and putting overlap as a question.
- **Not established:** one run per arm, all three scenarios in one context; one hand-authored analysis and two variants of it, written by the prompt's author; nothing grades the paragraph. Three scenarios are an adherence check, not a benchmark.
