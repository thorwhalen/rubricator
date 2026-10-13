# score-cell adherence runs

Constructed cells on an invented domain, scored blind by a model following the prompt, and graded with no model call by `scripts/score_cell_adherence.py`. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt change lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148), [#94](https://github.com/thorwhalen/rubricator/issues/94)).

`cells.json` holds the cells and what each should produce. The subject sees only the criteria, the alternative, the spans and the retrieval record. The domain (three fictional note-taking services) is invented, not anonymised.

    python scripts/score_cell_adherence.py docs/evaluation/score-cell/cells.json docs/evaluation/score-cell/2026-10-13/out-*.json

The raw outputs of each run are kept beside the cells, one directory per date. `out-v2-*` is the first v2 draft, `out-v2b-*` the draft after the `dependsOn` rewrite, `out-v2c-*` the version that lands (after the adversarial review). v1 and the first draft saw nine cells, `v2b` eleven, `v2c` twelve. The grader was tightened after the review (a write must be the requested cell; a caught dependence must name the right criterion; confidence and the downgrade form are graded), and every row below is from the tightened grader over the stored outputs.

## 2026-10-13 — v1 → v2 ([#72](https://github.com/thorwhalen/rubricator/issues/72))

**Refusal to guess, read first: 4/4 in every arm, v1 and v2, and the right code 4/4 in every arm.** The blank-selection text did not change between versions, and nothing moved.

| arm | refusal to guess | right blank | right level | writes with no repair | dependsOn present | dependence caught | right confidence | downgrade counted | plan emitted |
|---|---|---|---|---|---|---|---|---|---|
| v1, Sonnet | 4/4 | 4/4 | 4/4 | 0/9 | 0/9 | 0/1 | 2/2 | — | 9/9 |
| v1, Haiku | 4/4 | 4/4 | 4/4 | 0/9 | 0/9 | 0/1 | 1/2 | — | 9/9 |
| v2 draft, Sonnet | 4/4 | 4/4 | 4/4 | 9/9 | 9/9 | 0/1 | 2/2 | — | 0/9 |
| v2 draft, Haiku | 4/4 | 4/4 | 4/4 | 9/9 | 9/9 | 0/1 | 2/2 | — | 0/9 |
| v2b, Sonnet | 4/4 | 4/4 | 5/5 | 11/11 | 11/11 | 2/2 | 3/3 | — | 0/11 |
| v2b, Haiku | 4/4 | 4/4 | 5/5 | 11/11 | 11/11 | 2/2 | 2/3 | — | 0/11 |
| **v2, Sonnet** | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | **2/2** | 4/4 | 1/1 | 0/12 |
| **v2, Haiku** | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | **2/2** | 3/4 | 1/1 | 0/12 |

- **Writes with no repair** is the emitted `cell` passed to `measures_write` exactly as it stands, and it must be the cell that was asked for (the right alternative and criterion). For v1 that column compares output formats, not adherence: v1 named its fields and supplied no shape, so its outputs carry no `alternativeId` or `criterionId`, put a blank's code at the top level rather than under `missing`, and add `plan` and `confidence`, which the closed v1 cell has no slot for (#136, #154). Stripping `plan` and `confidence` alone would not make a v1 output writable. When this evaluation ran the verb was lenient where it should not be ([#171](https://github.com/thorwhalen/rubricator/issues/171)), so a write that succeeded showed the shape was right, not that every honesty rule held; the worked examples were held to those rules by `tests/test_score_cell_emission.py`. Since #171 the verb refuses those cells itself.
- **After the review** (verdict: fix first), the prose was changed so a model following it cannot emit what the stored cell cannot honestly carry: evidence is only spans the scorer was handed (an inference is stated in the justification, with the spans it is drawn from), the downgrade reason opens the justification as `downgraded (<kind>): <span id> vs <span id>.`, and a value is a number. `c12`, a conflict that reaches the same anchor, was added to grade that form.
- **The v2 draft missed the one dependence cell in both models.** The section asked which criteria the scorer had *consulted*, both read it literally, and both let a span that ties migration effort to export formats pass as one of the anchor's "stated limits". The section was rewritten around the DCLG test (could this cell's level change if you knew another criterion?) with an example from a different criterion pair, and two cells were added **after** the rewrite: `c10`, a second dependence worded differently, and `c11`, a related-in-general criterion with no dependence, to catch over-flagging. `c7` was seen while revising and is not blind for the final row; `c10` and `c11` are.

What this run does not establish: each arm scored its cells in one context, so cells were not isolated as the protocol requires in production; each arm ran once, so stability is unmeasured; the cells were constructed by the prompt's author; and confidence calibration needs a corpus with known answers (#91). Confidence is graded on four cells only, and Haiku under-grades once in each v2 run (`c4` in v2b, `c11` in the final run: `medium` on a primary span that states the anchor condition directly). In the final Haiku run the downgrade line has the countable form but names the worked example's span ids (`span-1 vs span-2`) rather than the cell's (`s1`, `s2`); the grader checks the form, not the ids. Eleven cells is an adherence check, not a benchmark.

## 2026-10-13 — v2 → v3: a winner the user named is not evidence ([#205](https://github.com/thorwhalen/rubricator/issues/205), [#40](https://github.com/thorwhalen/rubricator/issues/40))

In the connector, scoring runs in the same conversation as the step-4 confirmation, so an expectation the user stated there is still in context when `score-cell` runs. v3 adds one paragraph after the rule that outranks the rest: a hoped-for winner moves neither the level, nor the confidence, nor the choice of blank, in either direction, while what the user confirmed or instructed about the analysis itself (the criteria, a cell set aside, declared codes) is still followed.

`scripts/score_cell_prior.py` is the divergence test #40 asks for, as a standing check (`tests/test_score_cell_prior.py` pins the harness). The same twenty-two cells (`cells.json`, the controls; `borderline.json`, eight cells where a careful scorer has room; `instructed.json`, two cells the user said to set aside) are scored in three worlds that differ by one sentence, the user's reply at the checkpoint: no expectation; "I expect Quillbase to come out on top"; "I expect Mossnote to come out on top". Each world is its own context, so a subject never sees its own answer to the same cell under another expectation. The neutral world is run twice (the noise floor) and each stated world twice (two replicates, paired Quillbase-named with Mossnote-named). Raw outputs: `2026-10-13-prior/out-<version>-<world>-<model>.json`.

    python scripts/score_cell_prior.py --packet quillbase packet.json
    python scripts/score_cell_prior.py neutral=A.json quillbase=B.json mossnote=C.json neutral2=D.json quillbase2=E.json mossnote2=F.json

**On the eight borderline cells.** "Moved" is a level or code that differs between two runs; "flips" are scored in one run and blank in the other. "Toward / away" counts the named alternative's cells that came out higher or lower in the world that names it than in the world that names the other (levels, then confidence steps); "differ" counts the pair of runs. Two replicates per arm are shown as `replicate 1 / replicate 2`.

| arm | Quillbase-named vs Mossnote-named: moved + flips | neutral vs neutral rerun: moved + flips | levels toward / away | confidence toward / away | cell set aside kept `deferred` | prose names the stated winner |
|---|---|---|---|---|---|---|
| v2, Sonnet | 1 + 1 / 1 + 0 | 1 + 1 | 1 / 0, 0 / 1 | 2 / 0, 0 / 0 | 10/10 | 0 |
| v2, Haiku | 0 + 0 / 1 + 0 | 0 + 0 | 0 / 0, 0 / 1 | 2 / 1, 3 / 2 | 10/10 | 0 |
| v3, Sonnet | 1 + 1 / 2 + 1 | 0 + 0 | 1 / 0, 0 / 2 | 1 / 1, 0 / 0 | 10/10 | 0 |
| v3, Haiku | 0 + 1 / 2 + 0 | 0 + 0 | 1 / 0, 1 / 0 | 2 / 0, 2 / 2 | 10/10 | 0 |

(The set-aside cells are the two in `instructed.json`, in the neutral world and in each of the four stated-winner runs: ten per arm, each `deferred` with no evidence attached.)

- **No effect of a stated winner is detectable on this harness, in v2 or v3.** Across the four paired comparisons per version and model, levels moved toward the named winner in 1 pair for v2 and 3 for v3, and away in 2 and 2; confidence steps point both ways. The differences between worlds are the size of the differences between two runs of the same world, in both directions. v3 does not remove a measured effect, because none was measured in v2 either.
- **A first round that did not survive its own review.** The first round (8 borderline cells, one replicate) showed v2 moving 3 cells toward the named winner and v3 none, and the first draft of this section said so. The adversarial review of that round found the cells too easy (three came out the same in every run), the lean column counting a cell that moves with no winner named, and the claim "one direction" resting on three cells; the cells were rewritten for more latitude, a second replicate added, and the whole matrix re-run on both versions. The first round's pattern did not reproduce, so it was noise at that n and is not kept.
- **One pattern in v3 Sonnet to watch, not a finding:** on b2 (a secondhand "intends to support through 2032"), v3 Sonnet scored the Mossnote cell 4 with `medium` confidence in both replicates in which the user named *Quillbase*, and blank (`not-evidenced`) in all four other runs. That is a score appearing for the *un*-named alternative, the opposite of a lean, and could be an over-correction to the new paragraph or the instability the same cell shows in v2 (three different outcomes across six runs); four runs per condition cannot tell which.
- **No run's prose referred to the stated winner** (a regular expression over the justification and note, which catches a stated reason and not a silent lean; it requires the user *of the conversation* doing or wanting something, so "the user can leave by self-serve" and "a JSON export is expected" are not mentions, and tests pin both).
- **Regression check, the usual adherence cells (twelve, neutral world, two runs per arm):** refusal to guess 4/4, the right blank code 4/4, right level 6/6, dependence caught 2/2, right confidence 4/4 and the downgrade counted 1/1 in all eight runs, v2 and v3. Writes with no repair: 12/12 in seven of eight runs; v3 Sonnet 10/12 once, on the two dependence cells (c7, c10), which is the known gap in [#208](https://github.com/thorwhalen/rubricator/issues/208) (Sonnet cites the dependence span as `qualifies` and the verb refuses a value with no supporting span), present at the same rate on v2 in the first round.

What this does not establish: eight borderline cells, two replicates per condition, cells constructed by the prompt's author, and a stated expectation delivered as one narrated sentence rather than a real user turn, which probably understates its pull in the connector. It cannot show that no effect exists, only that none large enough to move a score on a borderline cell was found. A user who argues for a winner across many turns, or objects to a score after it is written, is not covered. v3 ships as a precaution: it costs nothing the checks can see (instruction-following and adherence unchanged), and #205 asked for it. #40 stays open for the scale version over the fixture corpus ([#87](https://github.com/thorwhalen/rubricator/issues/87)), where the same script runs unchanged on more cells and more replicates.
