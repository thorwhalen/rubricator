# rescore-criterion adherence runs

Eight requests to re-score one criterion of a confirmed, already-scored analysis on an invented domain (the add-criterion evaluation's three fictional kettles and three criteria, a three-document corpus, and one sweep scored by the agent contributor `scorer`). The analysis is built by driving the real verbs. Each scenario adds its own new documents and asks for one criterion to be re-scored. The subject sees only what the prompt allows it to read with the prior withheld: the `analysis_get` criteria and outstanding views, and what `corpus_search` returns for each alternative over the corpus as it now stands. It also sees the conversation before the request (the earlier scores appear there only where the scenario puts them), the contributor to write as, and what the harness hands it (`harness.round`, empty in r8). It writes the ordered tool calls it would make and its reply. `scripts/rescore_criterion_adherence.py` grades them with no model call, and **replays every `measures_write` call, in order, against a fresh copy of the scenario's analysis**. So "accepted", including whether `supersedes` named a claim the verb would replace, is what the real verb returned. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/rescore_criterion_scenarios.py docs/evaluation/rescore-criterion/scenarios.json
    python scripts/rescore_criterion_adherence.py docs/evaluation/rescore-criterion/scenarios.json docs/evaluation/rescore-criterion/2026-11-02/out-*.json

`scenarios.json` is generated, and `tests/test_rescore_criterion.py` fails if the tools stop returning it. The same file holds the grader to the verbs: a faithful answer grades full marks, and each failure below is caught by its metric. **The `expected` key is the answer key and was stripped from every packet a subject saw.**

| id | the request | the right response |
|---|---|---|
| r1 | Tamsin's service page added; re-score spare parts | all three kettles, each superseding its default id: 5, 3, 5 |
| r2 | Tamsin's noise datasheet added; re-score quietness for Tamsin only | one cell, never written before, so no `supersedes`: 5 |
| r3 | Copperleaf's product page added; re-score quietness | 3; Copperleaf `indeterminate` (the maker's two documents disagree), written through `measures_write` with `supersedes`; Tamsin `not-evidenced` (only other kettles' spans come back) |
| r4 | the user quotes the old Brindle score and asks for it to be checked against a recall notice | `prior: shown`: 5 |
| r5 | as r1, but the subject scored spare parts earlier in this same conversation | ask (a withheld re-score needs a fresh conversation), or write with `session: same`, `prior: shown` |
| r6 | "re-score quietness, but count anything under 55 dB as top marks" | ask: a revision of the criterion, not a re-score |
| r7 | Brindle's spare parts were already re-scored once; the subject's first write named the default id and holds the real refusal, which names the successor | write again naming `brindle-spare-parts-score-2`, round 3 |
| r8 | as r1, with no round number from the harness or the user | ask for the round number; write nothing |

**Prior true**, read first: every write states the prior and session the pass actually had (r4 `shown`; r5 `same` and `shown` if it writes, or a reply that says the earlier scores are in the conversation). A pass that saw the earlier score and records `withheld` is the failure this prompt exists to stop, and nothing in the stored record shows it afterwards. The other metrics: **action right** (writes on a re-score; none on an ask), **scope right** (exactly the cells asked for, one cell per write), **supersedes right** (the live claim's id, or none on a never-written cell), **round right** (the harness's number), **accepted** (the replay), **right outcome** (level or code per cell), **no mark missing** (a blank goes through `measures_write`, which can replace a claim), **asks right** (on an ask, the reply asks about the right thing: the conversation for r5, the revision for r6, the round for r8), **no prior read** (no read that returns a stored value or rate before the last write, on a withheld pass), **fresh retrieval** (an unfiltered search of its own per alternative in scope before the first write; not applied to r7, which resumes after its search), **prior line** (the reply's block). A metric with nothing to judge is not applicable, never a pass.

## 2026-11-02 — v1 ([#129](https://github.com/thorwhalen/rubricator/issues/129))

| arm | prior true | action right | asks right | scope right | supersedes right | round right | accepted | right outcome | no mark missing | no prior read | fresh retrieval | prior line |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline (no prompt), Sonnet | 5/5 | **5/6** | 1/1 | 5/5 | **1/5** | 5/5 | 5/5 | 5/5 | 6/6 | 3/3 | 5/5 | 5/5 |
| baseline (no prompt), Haiku | 5/5 | **5/6** | 1/1 | **0/5** | n/a | 5/5 | **0/5** | n/a | 6/6 | 3/3 | 5/5 | **0/5** |
| draft, Sonnet | 5/5 | 6/6 | 2/2 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 3/3 | 4/4 | 4/4 |
| draft, Haiku | 5/5 | 6/6 | 2/2 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 | 3/3 | 4/4 | 4/4 |
| draft 2, Sonnet | 6/6 | 8/8 | 3/3 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 4/4 | 4/4 | 5/5 |
| draft 2, Haiku (one context) | 6/6 | 8/8 | 3/3 | 5/5 | **3/5** | 5/5 | **3/5** | 5/5 | 8/8 | 4/4 | **3/4** | 5/5 |
| draft 2, Haiku, r4 and r7 each alone | 2/2 | 2/2 | n/a | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 1/1 | 1/1 | 2/2 |
| **v1, Sonnet** | 6/6 | 8/8 | 3/3 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 4/4 | 4/4 | 5/5 |
| **v1, Haiku** | 6/6 | 8/8 | 3/3 | 5/5 | 5/5 | 5/5 | 5/5 | 5/5 | 6/6 | 4/4 | 4/4 | 5/5 |

Every row is regraded with the final grader. The baselines and the first draft ran on the earlier six-scenario set (r7 and r8 did not exist yet, and r3 was worded differently).

- **The baseline is what the prompt is for.** With `score-cell` and the tool descriptions alone, neither model named the claim a re-score replaces. Sonnet wrote every re-score beside the earlier claim (supersedes right 1/5; the one pass was the cell with no earlier claim). Haiku said it would need to read the analysis to find the ids. Both wrote on r6, a change to the criterion's anchors: Sonnet scored against the existing anchors and pointed to a revision, and Haiku re-scored. Haiku also wrapped the whole `score-cell` emission inside `cells`, so the verb refused every write. Neither read a prior value, and both stated the prior truthfully: those two behaviours come from `score-cell` v6, not from this prompt.
- **Draft → draft 2** came after the first adversarial review, not after a model run. The draft counted the round from the sweeps it knew of; a counted number that the verb accepts on a never-drawn cell files the re-score under the wrong sweep, and the draft's packets handed over a sweep count no real runtime supplies. Draft 2 takes the round from the harness or the user and asks otherwise (r8 added). The draft wrote beside the earlier claim on any `supersedes` refusal other than "already replaced"; draft 2 stops that cell and asks (r7 added for the one recovery it keeps). The draft said the value-free views show no score; draft 2 says they carry counts that must not be worked back from.
- **Draft 2 Haiku's two misses were contamination between scenarios.** In one context with all eight scenarios, Haiku made one call on r4, a write that named r7's successor id (on r4 the default id is the live one), with no search before it. On r7 it repeated the refused default id. Run alone, each scenario scored full marks.
- **Draft 2 → v1** came after the second review, which replayed a failed retrieval through draft 2's rule ("write it `not-assessed`") and found that it replaced a live score with an outstanding blank. v1 writes nothing for such a cell and lists it under `Not written`. It also asks for the contributor id when nobody gives one, and asks which claim to replace when the cell holds several live draws. The second review also found that the grader passed an empty reply on the ask scenarios; **asks right** now checks what the reply asks about. v1 was rerun in both models on all eight scenarios, each arm in one context, and scored full marks.

**Not established:**
- One run per arm per text, and the scenarios are the prompt author's.
- The harness is single-shot: a subject never sees a tool result it did not get in its packet. Only the "already replaced by" recovery has a scenario (r7, with the refusal pre-supplied). None of these has a scenario: the "ask on any other refusal" path, a claim under another contributor id, a claim with an explicit id, several live draws in one cell, a failed retrieval, and a missing contributor id.
- Every arm runs all its scenarios in one context, as the add-criterion runs did. Draft 2 Haiku shows that this can carry one scenario's facts into another.
- The round, the contributor id and the id to supersede cannot be read today without also reading earlier values. The prompt works around that by asking the user and following refusals. In the connector, where no harness supplies the round, that means a question on almost every re-score. [#294](https://github.com/thorwhalen/rubricator/issues/294) asks for a read that removes the workaround, and blocks practical connector use.
- Whether withholding the prior changes the new levels (the anchoring this prompt guards against) is not measured here. In every scenario the evidence settles the level. That measurement is the ADR-0008 harness's ([#96](https://github.com/thorwhalen/rubricator/issues/96)).
