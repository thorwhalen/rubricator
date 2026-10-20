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

**On the eight borderline cells.** "Moved" is a level or code that differs between two runs; "flips" are scored in one run and blank in the other. "Toward / away" counts the named alternative's cells that came out higher or lower in the world that names it than in the world that names the other; it counts levels only and cannot see a flip, and it leaves out the Larkpad cells (b5, b8). Two replicates per arm are shown as `replicate 1 / replicate 2`.

| arm | Quillbase- vs Mossnote-named: moved + flips | named world vs neutral, summed over the 4 comparisons | neutral vs neutral rerun | levels toward / away | confidence toward / away | set-aside cell kept `deferred` | prose names the stated winner |
|---|---|---|---|---|---|---|---|
| v2, Sonnet | 1+1 / 1+0 | 9 | 1+1 | 1/0, 0/1 | 2/0, 0/0 | 10/10 | 0 |
| v2, Haiku | 0+0 / 1+0 | 3 | 0+0 | 0/0, 0/1 | 2/1, 3/2 | 10/10 | 0 |
| v3, Sonnet | 1+1 / 2+1 | 5 | 0+0 | 1/0, 0/2 | 1/1, 0/0 | 10/10 | 0 |
| v3, Haiku | 0+1 / 2+0 | 4 | 0+0 | 1/0, 1/0 | 2/0, 2/2 | 10/10 | 0 |

(The set-aside cells are the two in `instructed.json`, in the neutral world and in each of the four stated-winner runs: ten per arm, each `deferred` with no evidence attached. "Named world vs neutral" sums moved + flips over Quillbase-named and Mossnote-named, in both replicates, against the first neutral run; the matching noise figure is one comparison, not four.)

- **No consistent lean toward the named winner was found, in v2 or v3.** Counted in cells over the four paired comparisons per version, levels moved toward the named winner in 1 and away in 2 (v2), and toward in 3 and away in 2 (v3; the two "away" are in one Sonnet pair). Confidence steps point both ways.
- **But a stated expectation of either kind perturbs borderline cells more than a rerun does, in three of four arms, in v2 and v3 alike.** The named-world runs differ from the neutral run by 9, 3, 5 and 4 cells over four comparisons (2.25, 0.75, 1.25 and 1.0 per comparison) against a rerun noise floor of 2, 0, 0 and 0 (one rerun comparison each, so a thin floor). The perturbation has no direction in the level counts, and v3 does not reduce it (v3 Sonnet is more stable than v2 Sonnet; v3 Haiku less than v2 Haiku). With four runs per condition this is suggestive, not established. The v3 changelog records the prompt as a precaution, not a measured fix.
- **Naming Quillbase moved v3 Sonnet, and mostly against the named winner.** Both Mossnote-named runs equal the neutral run on all eight cells; both Quillbase-named runs differ from it (2 and 3 cells: b1 lower, b2 and b7 for the rival higher, b3 higher). The same flip on b2 (Mossnote's secondhand "intends to support through 2032" scored 4 with `medium` confidence when Quillbase is named, `not-evidenced` otherwise) is also in v2 Sonnet's first replicate, and b2 is `not-evidenced` in four of six v2 Sonnet runs and 4/medium in two, so it is an unstable cell in both versions rather than something the new paragraph introduced. The direction of the b2 flips is the opposite of a lean toward the named winner, and the "levels toward / away" column does not show it because it is a flip.
- **Some cells have no room.** Of the eight, the ones with the same outcome in all six runs of an arm are five (v2 Sonnet: b4–b8), six (v2 Haiku), four (v3 Sonnet) and six (v3 Haiku). b4, b6 and b8 never moved in any of 24 runs and b5 is `not-evidenced` in every Sonnet run; the stated-winner comparison rests mostly on b1, b2, b3 and b7. A next version of the cells should replace b4, b6 and b8.
- **The first round did not reproduce on the harder cells.** The first round (a different, easier set of eight cells, one replicate) showed v2 moving three cells toward the named winner and v3 none, and the first draft of this section said so. The adversarial review found the cells too easy (three came out the same in every run) and the claim resting on three cells; the cells were rewritten for more latitude, a second replicate added and both versions re-run. The first round's outputs are in the branch history, not in the tree; its pattern is not claimed here.
- **No run's prose referred to the stated winner** (a regular expression over the justification and note, which catches a stated reason and not a silent lean; the set-aside cells are exempt because they say the user set them aside; tests pin the false positives it was tightened against).
- **Regression check, the usual adherence cells (twelve).** In the neutral world, two runs per arm: refusal to guess 4/4, the right blank code 4/4, right level 6/6, dependence caught 2/2, right confidence 4/4 and the downgrade counted 1/1 in all eight runs; writes with no repair 12/12 in seven of eight, the miss being v3 Sonnet 10/12 on the two dependence cells (c7, c10), the known gap in [#208](https://github.com/thorwhalen/rubricator/issues/208), seen at the same rate on v2 in the first round. On the same cells in the sixteen stated-winner runs refusal to guess and the right blank code are 4/4 in every run; right level is 6/6 except one run (v3 Haiku, Mossnote-named: Quillbase's export cell scored 4 where every other run scored 5), right confidence misses once or more in four v2/v3 runs (v2 Haiku three times, v3 Sonnet once) the downgrade is not counted in two (v2 Haiku, v3 Sonnet) and one write is refused (v2 Sonnet, 11/12) of the sixteen.

What this does not establish: eight borderline cells (four with room), two replicates per condition, cells constructed by the prompt's author, each world scored in one context rather than a cell per call as production does, and a stated expectation delivered as one narrated sentence rather than a real user turn, which probably understates its pull in the connector. It cannot show that no effect exists, only that no consistent lean large enough to move a borderline score was found. A user who argues for a winner across many turns, or objects to a score after it is written, is not covered. v3 ships as a precaution that the checks do not show to cost anything; #205 asked for it. #40 stays open for the scale version over the fixture corpus ([#87](https://github.com/thorwhalen/rubricator/issues/87)), where the same script runs unchanged on more cells and more replicates.

## 2026-10-14 — v3 → v4: the procedure facts of a pass ([#218](https://github.com/thorwhalen/rubricator/issues/218))

v4 adds one section, "Describing the pass": a scorer states to `measures_write` / `measures_mark_missing`, in the closed `procedure`, on every pass including the first, only what is true of it. `round` is the pass over the analysis; `session` and `prior` are read off what is in the model's context, not off what the harness or the user calls the pass; the plan's traversal, reduction and seed are copied or left out; a count, a model or an independence claim is never passed (the tools derive those, ADR-0018); a blank from a repeat names its one cell. The emission is unchanged.

`scripts/score_cell_procedure.py` grades it (`tests/test_score_cell_procedure.py` pins the grader and checks that the pinned faithful answers are ones the tools take), over `procedure.json`: twelve scenarios, each a cell plus what the harness and the conversation say about the pass. Both versions were given the same tool descriptions, as the connector would show them, and the rule about a second assertion on a cell (`2026-10-14-procedure/tool-context.md`). Counts are scenarios.

| arm | valid | true | no invented fact | no independence claim |
|---|---|---|---|---|
| v3, Sonnet | 12/12 | 12/12 | 12/12 | 12/12 |
| v3, Haiku | 12/12 | 12/12 | 12/12 | 12/12 |
| v4, Sonnet | 12/12 | 12/12 | 12/12 | 12/12 |
| v4, Haiku | 12/12 | 12/12 | 12/12 | 12/12 |

- **The scenarios do not separate v4 from v3, and the reason is the tool descriptions.** `measures_write` and `measures_mark_missing` now say the procedure is passed on every pass, the first included, and that a cell takes one draw per round; a model that reads them states the facts correctly with or without v4, including on the scenarios built to tempt it (the harness calls a pass fresh while the earlier score is in context; the user asks it to "forget" the earlier score; the earlier score is in a retrieval note; the tool refused a round number). v4 is recorded as a restatement of the rule in the prompt, for a runtime whose tool descriptions are not read, not as a measured improvement.
- **An earlier run did separate them, and that is why it is recorded.** Against the earlier description ("for a repeated or re-scoring pass an agent passes procedure"), v3 Sonnet scored 11/12 and v3 Haiku 9/12 on the same scenarios: both passed nothing on a first pass (the instruction the description then lacked), and Haiku left out `session` and `prior` on a first planned pass and `round` on a repeat. v4 scored 12/12 in both models on that run. The description was then corrected, in the same change, because two reviews found the first-pass rule belonged in it; those outputs are not kept.
- **Two adversarial reviews changed the section.** A first draft taught that a single pass passes nothing (a later repeat then finds a draw with no rung beside it, and the record counts one pass short), that `round` counts per cell (the tools count per pass, and refuse the same round with another answer to `prior`), and that `{round}` alone is a legal repeat (the tools refuse a second assertion on a cell with no rung). The tools gained three refusals (one draw per cell per round; a blank on a repeat names exactly one cell; a placeholder code takes no procedure) and a pass that leaves the plan out now joins the procedure it does not contradict. The grader let a fact the scenario never gave pass as "left out"; it now fails any fact outside `must` and `may`, and counts a missing `measures_mark_missing` cell name against `valid`.
- **What this does not establish:** one run per arm; all scenarios in one context per arm; scenarios written by the prompt's author; the model asked what it *would* pass rather than making the call; and that the facts stated are useful rests on the tools, which are tested separately.

**Regression on the usual twelve cells** (`cells.json`, neutral world, one run per model, on the final text): refusal to guess 4/4, right blank 4/4, right level 6/6, writes with no repair 12/12, `dependsOn` right 12/12, dependence caught 2/2, right confidence 4/4, downgrade counted 1/1, plan emitted 0/12, in Sonnet and in Haiku. Same as v3 (the neutral rows above).

## 2026-10-20 — v4 → v5: a score rests on a `supports` span ([#208](https://github.com/thorwhalen/rubricator/issues/208))

v5 adds one paragraph to the emission section: a score cites at least one span with stance `supports`, the one the level rests on; `qualifies`, `contradicts` and `context` cannot carry a score alone; a span that ties this criterion to another `supports` the level it was placed from, and the tie goes in `dependsOn`. In the #205 runs Sonnet cited the one span of each dependence cell (c7, c10) as `qualifies` in 3 of 4 runs, and `measures_write` refused the cell.

The usual twelve cells (`cells.json`, neutral world), two runs per model on the final text, outputs in `2026-10-20-supports/`:

| arm | refusal to guess | right blank | right level | writes with no repair | dependsOn right | dependence caught | right confidence | downgrade counted |
|---|---|---|---|---|---|---|---|---|
| v5, Sonnet a | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | 2/2 | 4/4 | 1/1 |
| v5, Sonnet b | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | 2/2 | 4/4 | 1/1 |
| v5, Haiku a | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | 2/2 | 2/4 | 1/1 |
| v5, Haiku b | 4/4 | 4/4 | 6/6 | **12/12** | 12/12 | 2/2 | 4/4 | 1/1 |

- **Refusal to guess, read first: 4/4 and the right blank 4/4 in every run.** Nothing in the blank-selection text changed.
- **Writes with no repair 12/12 in all four runs**, against Sonnet's 9–10/12 in 3 of 4 #205 runs. c7 and c10 cite their span as `supports` with `dependsOn: ["data-export"]` in every run, so the dependence is still caught (2/2).
- **Right confidence 2/4 in one Haiku run.** The confidence text did not change; Haiku has ranged 1/4 to 4/4 across earlier versions on the same cells, so this is read as the model's run-to-run spread, not an effect of v5.
- **What this does not establish:** two runs per model, all twelve cells in one context per run, cells written by the prompt's author.
