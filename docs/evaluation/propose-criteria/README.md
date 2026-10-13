# propose-criteria adherence runs

Invented decisions, each with a proposal written blind by a model following the prompt, graded with no model call by `scripts/propose_criteria_adherence.py`. This is the evaluation the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148), [#94](https://github.com/thorwhalen/rubricator/issues/94)).

`frames.json` holds the decisions. The subject sees only each subject, the alternatives with their brochure text, and what the user said. Every frame sets the same three traps: a **means objective the user states as a requirement** ("it must sync with…", "it has to export…"), which must be rejected as `means-objective` and not become a column; a **brochure feature** every alternative advertises and nobody asked for, which must not become a criterion; and, in two frames, something the **user dismissed**, which must be recorded as `user-rejected`. The domains (a choir, a robotics team, an allotment society, a hiking club) are invented.

    python scripts/propose_criteria_adherence.py docs/evaluation/propose-criteria/frames.json docs/evaluation/propose-criteria/2026-10-13/out-*.json

## 2026-10-13: v1 ([#68](https://github.com/thorwhalen/rubricator/issues/68))

Every row below is the current grader run over the stored outputs; `tests/test_propose_criteria.py` holds the final rows to it.

| arm | frames | criteria_set, no repair, no gaps | ladder kept | means objective rejected | brochure trap avoided | user dismissal recorded | quotes verbatim | no absence anchor |
|---|---|---|---|---|---|---|---|---|
| draft, Sonnet | f1–f3 | 3/3 | 0/3 | 3/3 | 0/3 | 1/1 | 3/3 | 3/3 |
| draft, Haiku | f1–f3 | 3/3 | 3/3 | **0/3** | 0/3 | **0/1** | 3/3 | **1/3** |
| rev1, Sonnet | f1–f4 | 4/4 | 4/4 | 4/4 | 0/4 | 2/2 | 4/4 | 4/4 |
| rev1, Haiku | f1–f4 | 4/4 | 4/4 | 4/4 | 0/4 | 2/2 | 4/4 | 4/4 |
| **v1, Sonnet** | f1–f5 | 5/5 | 5/5 | 5/5 | 5/5 | 3/3 | 5/5 | 5/5 |
| **v1, Haiku** | f1–f5 | 5/5 | 5/5 | 5/5 | 5/5 | 3/3 | 5/5 | 5/5 |

What each column checks:

- **Ladder kept**: `rubricator.ladder.proposal_problems` returns nothing. That means:
  - the leaves are exactly the criteria, each refining one objective;
  - every reject carries a code from ADR-0016's closed set;
  - each means objective is named, by its label, at the start of an exclusion of every criterion it serves;
  - every two criteria refining one objective are flagged with an indifference question;
  - group sizes and provenance match the ladder;
  - every criterion has at least one exclusion and one missing rule.
- **Means objective rejected**: the stated requirement is a `means-objective` reject, and its keyword appears in no criterion.
- **Brochure trap avoided**: the feature every brochure advertises is neither a criterion nor a reject. It is not a candidate at all ([#175](https://github.com/thorwhalen/rubricator/issues/175)).

How the prompt changed between rows:

- **Draft → rev1.**
  - Haiku only asked about a requirement stated with "must" (or made it a column) instead of rejecting it as a means objective.
  - It labelled a brochure feature `user-rejected` while the thing the user dismissed went unrecorded.
  - It hid absences inside anchor clauses ("states X but does not state Y").
  - Sonnet paraphrased means objectives in exclusions.
  - The prompt now covers all four, and `f4` was added after this revision.
- **rev1 → v1, after the adversarial review.** The draft's worked example listed a brochure-only feature as `no-discrimination-expected`, which that code does not mean, and both models copied it (the 0/4 column). Now:
  - a feature only the alternatives raise is asked about, not rejected;
  - a means objective's exclusion begins with its label;
  - the worked example's anchors measure the outcome rather than the rejected mechanism;
  - target and anchor levels are stated on the 1–5 scale;
  - group imbalance is raised.

  The grader was tightened at the same time, and every earlier row is shown under it. `f5` was added after this revision.
- **What was blind.** The v1 rows are blind on `f5`. `f1`–`f4` informed earlier revisions.

What this run does not establish:

- Each arm wrote its proposals in one context, and ran once, so stability is unmeasured.
- The frames were written by the prompt's author.
- The checks are structural and keyword-based. They cannot tell a good criteria set from a well-formed bad one, and the absence check is a pattern that a new phrasing can slip past. Whether the right criteria were proposed, and whether an overlap the ladder does not see is real, needs a human reading the stored outputs.

Five frames make an adherence check, not a benchmark.
