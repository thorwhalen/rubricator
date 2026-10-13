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

- **Writes with no repair** is the emitted `cell` passed to `measures_write` exactly as it stands, and it must be the cell that was asked for (the right alternative and criterion). For v1 that column compares output formats, not adherence: v1 named its fields and supplied no shape, so its outputs carry no `alternativeId` or `criterionId`, put a blank's code at the top level rather than under `missing`, and add `plan` and `confidence`, which the closed v1 cell has no slot for (#136, #154). Stripping `plan` and `confidence` alone would not make a v1 output writable. The verb is also lenient where it should not be ([#171](https://github.com/thorwhalen/rubricator/issues/171)), so a write that succeeds shows the shape is right, not that every honesty rule held; the worked examples are held to those rules by `tests/test_score_cell_emission.py`.
- **After the review** (verdict: fix first), the prose was changed so a model following it cannot emit what the stored cell cannot honestly carry: evidence is only spans the scorer was handed (an inference is stated in the justification, with the spans it is drawn from), the downgrade reason opens the justification as `downgraded (<kind>): <span id> vs <span id>.`, and a value is a number. `c12`, a conflict that reaches the same anchor, was added to grade that form.
- **The v2 draft missed the one dependence cell in both models.** The section asked which criteria the scorer had *consulted*, both read it literally, and both let a span that ties migration effort to export formats pass as one of the anchor's "stated limits". The section was rewritten around the DCLG test (could this cell's level change if you knew another criterion?) with an example from a different criterion pair, and two cells were added **after** the rewrite: `c10`, a second dependence worded differently, and `c11`, a related-in-general criterion with no dependence, to catch over-flagging. `c7` was seen while revising and is not blind for the final row; `c10` and `c11` are.

What this run does not establish: each arm scored its cells in one context, so cells were not isolated as the protocol requires in production; each arm ran once, so stability is unmeasured; the cells were constructed by the prompt's author; and confidence calibration needs a corpus with known answers (#91). Confidence is graded on four cells only, and Haiku under-grades once in each v2 run (`c4` in v2b, `c11` in the final run: `medium` on a primary span that states the anchor condition directly). In the final Haiku run the downgrade line has the countable form but names the worked example's span ids (`span-1 vs span-2`) rather than the cell's (`s1`, `s2`); the grader checks the form, not the ids. Eleven cells is an adherence check, not a benchmark.
