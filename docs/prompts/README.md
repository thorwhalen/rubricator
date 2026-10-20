# Prompts

Prompts are **content**, not strings embedded in a loop (ADR-0003). Both runtimes serve the same
files: the MCP server exposes them, and the deployed agent loads them.

## Where they live

    rubricator/data/prompts/*.md    the files themselves, shipped in the wheel
    rubricator/prompts.py           the one accessor -- `prompts()`, with `root` as the seam
    rubricator/tools/prompts.py     the two verbs that serve them: `prompts_list`, `prompts_get`
    tests/test_prompts.py           what a prompt must satisfy to land

This document is the **inventory and the contract**. The prompts themselves are not reproduced here;
a prompt copied into two places is two prompts.

`prompts_list` and `prompts_get` are ordinary deterministic verbs on the ADR-0003 registry, so the
bundle is servable from the CLI and the connector today. The connector also serves every file as a native MCP prompt
(`prompts/list`, `prompts/get`), which is what makes a Claude client show them as slash commands
([#80](https://github.com/thorwhalen/rubricator/issues/80)). Both read the one accessor, so a new
`.md` file is served by both with no code change.

## The set

Ten prompts, mapped to the ADR-0005 stages. "Shipped" means the file exists and is served.

| Prompt | Stage | Shipped | Job |
|---|---|---|---|
| `frame` | 1 | — | Establish subject, decision, decider; surface ambiguity instead of resolving it silently |
| `enumerate-alternatives` | 2 | — | Extract candidates from context; flag omissions and near-duplicates |
| `propose-criteria` | 3 | **yes** | Criteria with every definition field, anchors as evidence conditions and a stated direction of preference, plus the objective ladder that produced them, rejects with a closed reason code, overlaps flagged from the ladder, and group sizes. The criteria go to `criteria_set` as they stand; the rest is checked by `rubricator.ladder` |
| `confirm-frame` | 4 | **yes** | The checkpoint's discussion, in chat: the question and decider, every alternative, every criterion with its definition, scale, anchors and direction, and the overlap probes put to the *user* in both directions. Records the user's answer through `frame_confirm` in their name and words, or nothing; reads a form's answer as the record where the client elicits it. A stated expectation about the winner changes nothing in the frame. Evaluated by `scripts/confirm_frame_adherence.py` over `docs/evaluation/confirm-frame/` |
| `extract-evidence` | 5 | — | Which returned span bears on this claim. Runs *before* `score-cell`, which never sees the corpus |
| `score-cell` | 5 | **yes** | **The default** (ADR-0011). One cell: score, confidence, one-line justification, evidence spans — and which blank, when there is no score to give. Emits the `measures_write` cell as it stands, with `confidence` and `dependsOn` beside it until the contract has slots for them (#126, #170). It also teaches the closed `procedure` facts the write call takes on every pass, the first included (round; session and prior read off the model's context; the plan's), stated only when true (#218) |
| `score-column` | 5 | — | One criterion across all alternatives. **Not the default** — it survives only as arm 2 of the ADR-0008 evaluation harness, awaiting validation (ADR-0011) |
| `review` | 6 | **yes** | Self-critique from `report_weaknesses`: cells to re-score with more evidence kept apart from criteria to redefine (whose cells never go back for re-scoring), the pivotal cell with the thinnest evidence and the evidence that would settle it, floors failed or untested, and the correlations read as a scoring diagnostic, never as redundancy. Proposes evidence, never a score. Evaluated by `scripts/review_adherence.py` over `docs/evaluation/review/` |
| `run-analysis` | — | — | The whole pipeline, for a caller who wants one instruction |
| `resume` | — | **yes** | Pick up a durable partial analysis (ADR-0017): read the stored confirmation instead of re-asking it, restate the counts, all in cells, in a fixed block that keeps nobody-has-looked, set-aside-on-purpose and looked-and-blank apart (by what a code means, not its spelling), and propose one next step without starting it. Evaluated by `scripts/resume_adherence.py` over `docs/evaluation/resume/` |
| `audit-existing` | — | — | Given an analysis someone else made, find its weaknesses |

## The file contract

Front matter, then the body. The body is what a model is given; the header never is.

```
---
id: score-cell
title: Score one cell
version: 1
stage: 5
updated: 2026-09-14
missing-codes:
  - not-evidenced
  - indeterminate
changelog:
  - 1 (2026-09-14) — what changed and the behavioural hypothesis, not a description of the diff
---
```

| key | |
|---|---|
| `id` | the key it is served under. Defaults to the filename; two files claiming one id is an error |
| `version` | an integer, bumped on every behavioural change. A prompt at version 0 fails the suite |
| `stage` | the ADR-0005 stage, where there is one |
| `missing-codes` | the missingness codes this prompt teaches, if any. Checked against the vocabulary manifest **and** against the prose |
| `changelog` | one entry per version; the entry for the current version must exist |

The dialect is deliberately small — flat scalars and `- ` lists, no nesting — because the connector
runtime must install in a bare environment and a YAML parser is a dependency this package does not
otherwise need. A prompt header that wants nested structure is a sign the structure belongs in the
tool layer.

**It has no comments.** There is no `#` handling, so a trailing `# like this` becomes part of the
value — which is why the block above carries none and the table explains the keys instead. The
loader is otherwise forgiving: a malformed header leaves the prompt at version 0 rather than
raising, so a half-written prompt is still loadable and the *suite* is what refuses it.

Each prompt file carries a version and a changelog entry. When a prompt changes, the evaluation
suite (ADR-0008) runs — that is the whole reason it exists. See the
`rubricator-dev-prompt-change` dev skill before editing one.

## What every prompt must do

**Every prompt must state the honesty rule** from ADR-0006 in its own words: prefer a qualified
blank to a plausible guess, cite spans not documents, and never present inference as source. Not by
reference — a prompt cannot follow a link. `tests/test_prompts.py` checks that all three survive
each edit, because this is the clause most likely to be lost to a tidy-up.

**And every scoring prompt must teach the two blanks apart**, because they are different findings
and only one of them is evidence about the subject: **`not-evidenced`** when the sources are silent
on the cell, **`indeterminate`** when they speak and do not settle it — they conflict, or they
underdetermine the level. A prompt that says only "emit a blank" will produce whichever code the
model reaches for first, and the completeness report cannot tell the two apart afterwards.

**Codes are declared, not inferred.** `missing-codes` in the front matter is checked against the
vendored vocabulary manifest (`rubricator/schema/comparanda/vocabularies.v1.json`), and against the
prose of the prompt itself. That is the tripwire for the next rename: when the companion repository
changes a spelling, the prompt that still teaches the old one fails the suite instead of quietly
instructing an agent to emit a value `measures_mark_missing` will refuse.

The retired spellings — `pending`, now `deferred`; `unknown`, now `indeterminate` — are banned from
prompt text outright. See [`CHANGELOG.md`](../../CHANGELOG.md) for that boundary and what it means
for any number measured on either side of it.

## Disclosures

A disclosure is content for the analysis's *reader*, not for a model: the variance notice ADR-0018 requires is the first. It follows the same file contract and is read by the same loader (`rubricator.prompts.load_bundle`), from its own directory, so the prompt rules above (the honesty clause, the vocabulary check) do not apply to it and its own do.

    rubricator/data/disclosures/*.md   the files, shipped in the wheel
    rubricator/disclosures.py          the accessor -- `disclosures()`, with `root` as the seam
    tests/test_disclosures.py          what the variance text must say, and must not

One extra header key, `placeholders`: the `{name}` fields a renderer fills with what the analysis records (its procedure records, the seeds, the assertions' independence rungs) or with "not recorded". Each is a value on a `label: value` line, never a word inside a sentence, because the procedures ADR-0018 prescribes vary per cell and no one sentence template is true of all of them. A test holds the declared list and the body's fields equal, and renders the connector's one pass, the deployed adaptive run and the empty record. Rendering is `disclose_variance` (tool 17).

`variance` must state the traversal and repeats actually used and what each step does and does not remove; that the connector's isolation is in-session isolation (attenuation, not elimination); that repeats of one model are test–retest reliability, not agreement between raters; and that human panels show the same effects (halo, joint versus separate evaluation, sequential contrast), each with its own linked source, and that this is not a claim that a machine evaluator is uniquely unreliable. It claims no size for any mitigation until the harness (#96) has measured one: a test refuses any number in the prose and any size word in the mitigation bullets.
