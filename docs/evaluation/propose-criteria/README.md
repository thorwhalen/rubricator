# propose-criteria adherence runs

Invented decisions, each with a proposal written blind by a model following the prompt, graded with no model call by `scripts/propose_criteria_adherence.py`. This is the evaluation the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148), [#94](https://github.com/thorwhalen/rubricator/issues/94)).

`frames.json` holds the decisions. The subject sees only each subject, the alternatives with their brochure text, and what the user said. Every frame sets the same three traps: a **means objective the user states as a requirement** ("it must sync with…", "it has to export…"), which must be rejected as `means-objective` and not become a column; a **brochure feature** every alternative advertises and nobody asked for, which must not become a criterion; and, in two frames, something the **user dismissed**, which must be recorded as `user-rejected`. The domains (a choir, a robotics team, an allotment society, a hiking club) are invented.

    python scripts/propose_criteria_adherence.py docs/evaluation/propose-criteria/frames.json docs/evaluation/propose-criteria/2026-10-13/out-*.json

## 2026-10-13: v1 ([#68](https://github.com/thorwhalen/rubricator/issues/68))

| arm | criteria_set, no repair, no gaps | ladder kept | means objective rejected | brochure trap avoided | user dismissal recorded | quotes verbatim | no absence anchor |
|---|---|---|---|---|---|---|---|
| draft, Sonnet | 3/3 | 1/3 | 3/3 | 3/3 | 1/1 | 3/3 | 3/3 |
| draft, Haiku | 3/3 | 3/3 | **0/3** | 3/3 | **0/1** | 3/3 | **1/3** |
| **v1, Sonnet** | 4/4 | 4/4 | 4/4 | 4/4 | 2/2 | 4/4 | 4/4 |
| **v1, Haiku** | 4/4 | 4/4 | 4/4 | 4/4 | 2/2 | 4/4 | 4/4 |

**Ladder kept** is `rubricator.ladder.proposal_problems` returning nothing. It checks four things: the ladder's leaves are exactly the criteria; every reject carries a code from ADR-0016's closed set; every two criteria refining one objective are flagged with an indifference question; and group sizes and provenance match the ladder.

- **The draft failed in two ways, one per model.**
  - **Sonnet** had the right means objectives in the right exclusions, but paraphrased them. A checker cannot match a paraphrase. The prompt now says to name the rejected label word for word.
  - **Haiku** made a real error. Where the user said "must" or "has to", it either only asked about the requirement in `questions` or made it a column. Either way it never rejected it. It also labelled a brochure feature `user-rejected` while the thing the user actually dismissed went unrecorded. And it hid an absence inside an anchor clause ("a source states X but does not state Y"), which score-cell can never meet.

  The prompt now says to reject a "must" as a means objective **and** ask whether it is a veto. It also defines `user-rejected` by what the user dismissed, and names the absence-in-a-clause pattern.
- **Frame `f4` was written after the revision**, and its outputs were never seen while revising. `f1`–`f3` informed the revision, so the v1 rows are blind on `f4` only.

What this run does not establish:

- Each arm wrote its proposals in one context.
- Each arm ran once, so stability is unmeasured.
- The frames were written by the prompt's author.
- The checks are structural. They cannot tell a good criteria set from a well-formed bad one. Whether the right criteria were proposed, and whether an overlap the ladder misses is a real one, needs a human reading the outputs, and the stored outputs are kept for that.

Four frames make an adherence check, not a benchmark.
