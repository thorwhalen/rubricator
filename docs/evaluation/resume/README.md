# resume adherence runs

Twelve partial analyses on an invented domain (three fictional kettles, one office deciding), each built by driving the real verbs to a state and recording what a resuming session's reads return: `analysis_get` (outstanding view), `frame_confirm` with no decision, and the criteria view where a declared code needs it. (The v1 runs read the summary view and `report_completeness`; their fixtures are kept in `2026-10-13/scenarios-v1.json`.) A subject following the prompt sees only those tool results and writes its reply; `scripts/resume_adherence.py` grades the block the prompt asks for, with no model call. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/resume_scenarios.py docs/evaluation/resume/scenarios.json
    python scripts/resume_adherence.py docs/evaluation/resume/scenarios.json docs/evaluation/resume/2026-10-13-v2/out-*.json

The v1 runs were graded against `2026-10-13/scenarios-v1.json` (what the tools returned then: the summary view and `report_completeness`); `scenarios.json` is what they return now, for v2.

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
| s8 | the checkpoint was skipped at open: `confirmed: true`, `record.decision: skip`, and a summary that says it was skipped at open and nobody confirmed (fixed in [#187](https://github.com/thorwhalen/rubricator/issues/187); the recorded runs saw the old "already confirmed by agent" wording) | `score` |
| s9 | the user answered `revise`, and the changes were never put back | `confirm` |
| s10 | two raters on one cell, and an alternative removed after it was scored: claims outnumber live cells (v1's units; v2 counts only the six live cells) | `score` |
| s11 | only the criteria were confirmed (`scope: criteria`) | `confirm` |
| s12 | a `not-applicable` cell beside scores and a silent blank | `score` |

## 2026-10-13 — v2, one unit and the cells named ([#186](https://github.com/thorwhalen/rubricator/issues/186), [#188](https://github.com/thorwhalen/rubricator/issues/188))

The same twelve states, re-read through the tools as they are now: `analysis_get` in its outstanding view (with `counts.byKind`) and `frame_confirm`; `report_completeness` is no longer read. Two metrics are new: **adds up** (nobody + set aside + scored + blank + not applicable equals `counts.cells`; re-score is a subset) and **names a real place** (a `score` step names a column or row that has a cell nobody has looked at, and none that has not; checked in the five `score` scenarios, and only s5, s10 and s12 can tell a right name from a wrong one, since in the others every column and row has such a cell).

| arm | blanks kept apart | settled counted as work | block complete | confirmation read right | no re-ask | re-ask when needed | counts right | adds up | next right | names a real place |
|---|---|---|---|---|---|---|---|---|---|---|
| **v2, Sonnet** | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 12/12 | 12/12 | 12/12 | 5/5 |
| **v2, Haiku** | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 12/12 | 12/12 | 12/12 | 5/5 |

- **Blanks kept apart, read first: 12/12 in both arms.** The before is v1's 12/12 on the older fixtures; the rest of the table cannot be compared cell by cell, because the units and the reads changed (v1's `counts right` was in claims for three lines).
- **Run twice.** The adversarial review corrected two sentences of the prompt (a not-applicable cell leaves every comparison and rate but is still a cell; re-score is a subset of the other lines), so both arms were re-run on the final text; the table is that run. The first Sonnet re-run scored `no re-ask` 7/8 on a reply saying "there is nothing to re-confirm": the grader read the negation as a re-ask, so its check now ignores "nothing to / no need to / not" before the verb (tested), and the reply is graded as the correct answer it was.
- **What changed against v1:** s10 now reads 4 scored cells and 2 outstanding, not 7 claims; both arms name the column that holds the unlooked-at cells where v1 said the records did not say.
- **Not established:** one run per arm; all twelve scenarios in one context per arm; the scenarios are the prompt author's; a baseline without the prompt was not re-run for v2 (the form-only baseline in `2026-10-13/baseline.md` is v1's form and reads claims).

## 2026-10-13 — v1 ([#76](https://github.com/thorwhalen/rubricator/issues/76))

**Blanks kept apart, read first: 12/12 in every arm.** No arm reported a settled blank as work remaining.

| arm | blanks kept apart | settled counted as work | block complete | confirmation read right | no re-ask | re-ask when needed | counts right | next right |
|---|---|---|---|---|---|---|---|---|
| **v1, Sonnet** | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 12/12 | 12/12 |
| **v1, Haiku** | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 12/12 | 12/12 |
| form only, Sonnet | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 12/12 | 12/12 |
| form only, Haiku | 12/12 | 0/6 | 12/12 | 12/12 | 8/8 | 4/4 | 10/12 | 12/12 |

- **No re-ask** fails a reply whose `Next` is `confirm` where the confirmation stands, *and* one whose prose asks the user to (re-)confirm while the block says otherwise.
- **The form-only baseline** (`baseline.md`) gives the subject the same block, the same `Confirmed:` forms and the same five `Next` kinds, and nothing else: no call order, no rule about which field holds which count, no confirmation rule, no honesty clause. It was run to test the changelog's hypothesis that the guidance, not the form, keeps the kinds apart. **On these twelve scenarios it does not show that.** The block's labels alone were enough for both models to keep settled blanks out of work remaining and to read `instructions` and `record` rather than `confirmed`. The one difference is Haiku's scored count when cells answer an older definition (s3, s7): without "take each number from its field", it subtracted the superseded cells from the scored claims. The prompt's other content — the honesty clause, the rule against filling a settled blank or narrating the earlier session, asking the question in the reply that records it as asked — is not graded here.
- **Read by hand, not graded:** every v1 reply proposes one step or asks one question and stops; none offers to fill a settled blank. In s8 both v1 arms say outright that the tool's summary ("already confirmed by agent") is a skip, not a confirmation. In s9 both ask whether to make the changes the user asked for before putting the frame back. With only the summary view read, neither can name which column the remaining cells sit in, and both say so rather than guess ([#188](https://github.com/thorwhalen/rubricator/issues/188)).
- **Before the review**, a seven-scenario draft (s1–s7, a block with no units and no `Not applicable` line) scored 7/7 in both arms. The adversarial review found the draft's account of the tools wrong in common states — `frame_confirm` with no decision records that the question was asked; claims and cells were mixed in one block; a skipped, revised or partial confirmation was read as given or as never asked; `not-applicable` had no line — and that the grader read prose as the block. s8–s12 were added for those states, the grader now reads only the block, and every metric has a test that fails when it is broken. The draft's outputs are not kept: the current grader cannot read its block.

What this run does not establish: each arm saw all twelve scenarios in one context, not one session each; each arm ran once, so stability is unmeasured; the scenarios were built by the prompt's author, and a baseline that already carries the block is a generous one. A model given no form at all cannot be graded by this script, so that hypothesis is untested. Twelve scenarios are an adherence check, not a benchmark.

## 2026-10-13 — v2 re-run against changed tool text ([#206](https://github.com/thorwhalen/rubricator/issues/206))

The prompt did not change. Five of the twelve stored scenarios (s2, s3, s8, s9, s11) were regenerated because `frame_confirm`'s own text changed (its `instructions` now mention the joined scopes, and a read on a skipped analysis says a confirmation can be recorded), so both models were run again on the regenerated set (`2026-10-13-v2-rerun-206/`). The row is the same as the first v2 run: every metric at the same count in both models (blanks kept apart 12/12, confirmation read right 12/12, no re-ask 8/8, re-ask when needed 4/4, counts right 12/12, next step right 12/12, settled counted as work 0/6). One run per arm.
