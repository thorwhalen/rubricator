# resume adherence runs

Seven partial analyses on an invented domain (three fictional kettles, one office deciding), each built by driving the real verbs to a state and recording what a resuming session's reads return: `analysis_get` (summary), `frame_confirm` with no decision, `report_completeness`, and the criteria view where a declared code needs it. A subject following the prompt sees only those tool results and writes its reply; `scripts/resume_adherence.py` grades the block the prompt asks for, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/resume_scenarios.py docs/evaluation/resume/scenarios.json
    python scripts/resume_adherence.py docs/evaluation/resume/scenarios.json docs/evaluation/resume/2026-10-13/out-*.json

`scenarios.json` is generated, and `tests/test_resume.py` fails if the tools stop returning it, so the subjects are never graded against a state the tools no longer produce. The expectations are stated by hand in the generator and checked there against the fields the prompt names.

| id | the state | the step it should propose |
|---|---|---|
| s1 | confirmed; scores, a silent and a conflicting blank, two cells deferred, four untouched | `score` |
| s2 | never confirmed | `confirm` |
| s3 | confirmed, then a criterion revised: `frame_confirm` returns `confirmed: true` **and** instructions to ask again | `confirm` |
| s4 | confirmed; nothing untouched, three cells deferred | `ask-deferred` |
| s5 | confirmed; two cells carry `queued`, a code declared on the criterion as refining `deferred` | `score` |
| s6 | confirmed; every cell scored or a settled blank | `review` |
| s7 | revised and confirmed again; every cell answers the older definition | `rescore` |

## 2026-10-13 — v1 ([#76](https://github.com/thorwhalen/rubricator/issues/76))

**Blanks kept apart, read first: 7/7 in every arm.** No arm reported a settled blank as work remaining.

| arm | blanks kept apart | settled counted as work | block complete | confirmation read right | no re-ask | re-ask when needed | counts right | next right |
|---|---|---|---|---|---|---|---|---|
| **v1, Sonnet** | 7/7 | 0/5 | 7/7 | 7/7 | 5/5 | 2/2 | 7/7 | 7/7 |
| **v1, Haiku** | 7/7 | 0/5 | 7/7 | 7/7 | 5/5 | 2/2 | 7/7 | 7/7 |
| form only, Sonnet | 7/7 | 0/5 | 7/7 | 7/7 | 5/5 | 2/2 | 7/7 | 7/7 |
| form only, Haiku | 7/7 | 0/5 | 7/7 | 7/7 | 5/5 | 2/2 | 5/7 | 7/7 |

- **The form-only baseline** (`baseline.md`) gives the subject the same block and the same five `Next` kinds, and nothing else: no call order, no rule about which field holds which count, no confirmation rule, no honesty clause. It was run to test the changelog's hypothesis that the guidance, not the form, is what keeps the kinds apart. **On these seven scenarios it does not show that.** The block's labels alone were enough for both models to keep settled blanks out of work remaining, and to read `instructions` rather than `confirmed` in s3. The one difference is Haiku's scored count when cells answer an older definition (s3, s7): without "take each number from the field that holds it", it subtracted the superseded cells from the scored ones. The prompt's other content — the honesty clause, the rule against filling a settled blank or narrating the earlier session, the read-only call order — is not exercised by this grader.
- **Read by hand, not graded:** every v1 reply proposes one step and stops; none offers to fill a settled blank. One Haiku reply (s6) calls all three settled blanks unsettled by "the sources", when two of them are silence, not conflict.

What this run does not establish: each arm saw all seven scenarios in one context, not one session each; each arm ran once, so stability is unmeasured; the scenarios were built by the prompt's author, and a baseline that already carries the block is a generous one. The hypothesis about a model with no form at all is untested, because its reply cannot be graded without the block. Seven scenarios are an adherence check, not a benchmark.
