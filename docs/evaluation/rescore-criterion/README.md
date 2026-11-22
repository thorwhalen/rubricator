# rescore-criterion adherence runs

**The scenario set changed on 2026-11-22** (v2, [#294](https://github.com/thorwhalen/rubricator/issues/294)): twelve scenarios. The 2026-11-02 section below describes the earlier eight-scenario set, which is in git history (`git show 1a9427d:docs/evaluation/rescore-criterion/scenarios.json`), and its rows are not comparable with the 2026-11-22 rows.

## 2026-11-22 — v2: one value-free read replaces the refusals and the questions ([#294](https://github.com/thorwhalen/rubricator/issues/294))

    python scripts/rescore_criterion_adherence.py docs/evaluation/rescore-criterion/scenarios.json docs/evaluation/rescore-criterion/2026-11-22/out-v*.json

v2 takes the claim to replace, the round and the writer from `measures_rescore_context`, a new verb. Per cell of one criterion it returns every live claim's id, contributor and author, marked `yours` for the scorer named; per writer it returns its `kind` (agent or human) and latest round. It never returns a value. The set now matches the connector, where nothing hands the subject a round:

- **Every packet** carries the read as the prompt instructs it, marked with the given scorer. No harness round, except in r8.
- **r7** no longer pre-supplies a refusal. The read names the live claim (`brindle-spare-parts-score-2`) and the scorer's latest round (2), so the right write is round 3, superseding it.
- **r8** is r1 with a harness round 2: the harness's number is the one written.
- **r9 (new):** the scorer holds two live draws in Brindle's cell. Ask which one the re-score replaces, and write nothing.
- **r10 (new):** Tamsin's quietness is Ana's claim, never the scorer's. Ask about her claim (replace it as the same rater, or write a second claim beside it), and write nothing.
- **r11 (new):** r1 with nobody naming the scorer. The read shows one agent writer, `scorer`, holding every claim in scope, with no model recorded, so it may be another agent. Propose it ("write as `scorer`?") and ask, in one line.
- **r12 (new):** r10 with nobody naming the scorer. The only writer in scope is Ana, a person. Ask who is writing, and never write as her.

Asks are judged on the reply's prose and its `Not written` line (where a cell left for the user carries its question); the block's other lines are removed, since they name the claims and the writer whatever was asked.

| arm | prior true | action right | asks right | scope right | supersedes right | round right | accepted | right outcome | no mark missing | no prior read | fresh retrieval | prior line |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1, Sonnet | 2/2 | **7/12** | **2/6** | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 12/12 | 1/1 | 1/1 | 1/1 |
| v1, Haiku | 2/2 | **7/12** | 6/6 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 11/11 | 1/1 | 1/1 | 1/1 |
| **v2, Sonnet** | 7/7 | 12/12 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 10/10 | 5/5 | 6/6 | 6/6 |
| **v2, Haiku** | 7/7 | 12/12 | 6/6 | 6/6 | **5/6** | **5/6** | **5/6** | 6/6 | 12/12 | 5/5 | 6/6 | 6/6 |

- **v1** asks for the round on every re-score without a harness round, so it writes only r8, which is right. Sonnet's asks on r9-r12 are about the round, not the claims or the writer (asks right 2/6). Haiku's also name the two live claims, Ana's claim and the missing contributor. An earlier v1 Sonnet run on r1-r11 (`drafts/out-r1-r11-v1-sonnet.json`) did read the round off the read's summary and wrote 10 of 11 right, so in Sonnet the read alone sometimes carries the fix. This run did not use it. That run-to-run difference is why v1 is not a dependable baseline.
- **v2 Haiku's one miss is r7.** It named the default id and round 2, ignoring the read's live claim (`brindle-spare-parts-score-2`) and latest round (2). The real verb refuses that write ("already replaced by"), and v2 stops a refused cell and asks, so the miss costs a question, not a wrong record. Haiku's three earlier v2 runs, under drafts of the same rule, got r7 right.
- **Drafts.** Their outputs are in `2026-11-22/drafts/`:
  - **Draft 1** was graded on the ten-scenario set of commit ab4a80f: v2 full marks; v1 5/10 action right in both models. The first adversarial review found four problems: its read hid another writer's claim when a contributor was named; personas shared their principal's rounds; a per-claim round leaked a settled blank; and r9 and r10 credited an ask about the round.
  - **Draft 2** dropped v1's "one `measures_write` call per cell". Both models batched cells (scope right 3/7).
  - **Draft 3** scored full marks on r1-r11. Its re-review found that "take the writer from the read" could write as a person, and that `measures_write` accepted a pass signed by a stored human record.
  - **Draft 4** never writes as a person, and `measures_write` refuses a procedure under a stored human signer. It scored full marks on r1-r12. Its third review found that `kind: agent` did not show the writer was this agent, and that without `author_id` a persona's claims counted as yours.
  - v2 adopts a writer without asking only when its recorded model is yours, and takes `yours` as the principal unless `author_id` names another author. r11 became an ask.
- **Declined from the third review:** refusing any write whose author `kind` contradicts the stored record. `test_an_author_already_stored_is_not_this_calls_problem` holds the opposite on purpose: a stored record never locks its contributor out. Only a pass (a `procedure`) is refused under a stored person, and the prompt always passes one.
- **What the metrics measure:** "no mark missing" applies whenever a subject lists any call, so it also counts whether the subject listed its reads.
- **How the runs were made:** each arm is one subagent (Sonnet or Haiku). It was given the prompt, `score-cell`, the advertised tool definitions and the twelve packets with the answer key stripped, and told to treat each scenario as its own conversation.

**Not established:**
- One run per arm.
- The scenarios are the prompt author's.
- Each arm ran all its scenarios in one context.
- The harness is single-shot, so none of these has a scenario: a refusal after the read (another writer racing, or r7's refusal path); a writer with no recorded round (`latestRound` null); a mixed sweep where one cell is left for the user; an unreadable stored file (`skipped`); a writer whose recorded model is the subject's own; and the user's answer to r10, r11 or r12 and the write that follows it.
- Whether withholding the prior changes the new levels is still #96's to measure.

## 2026-11-02 set

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
