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
bundle is servable from the CLI and the connector today. Presenting them as native MCP `prompts/*` —
which is what makes a Claude client show them as slash commands — is the upgrade tracked by
[#80](https://github.com/thorwhalen/rubricator/issues/80); it changes how they are registered, not
where they live or what they say.

## The set

Ten prompts, mapped to the ADR-0005 stages. "Shipped" means the file exists and is served.

| Prompt | Stage | Shipped | Job |
|---|---|---|---|
| `frame` | 1 | — | Establish subject, decision, decider; surface ambiguity instead of resolving it silently |
| `enumerate-alternatives` | 2 | — | Extract candidates from context; flag omissions and near-duplicates |
| `propose-criteria` | 3 | — | Criteria with definitions, polarity, level of measurement, veto status; flag overlaps |
| `confirm-frame` | 4 | — | The checkpoint, run as an MCP elicitation where the client declares the capability |
| `extract-evidence` | 5 | — | Which returned span bears on this claim. Runs *before* `score-cell`, which never sees the corpus |
| `score-cell` | 5 | **yes** | **The default** (ADR-0011). One cell: score, confidence, one-line justification, evidence spans — and which blank, when there is no score to give |
| `score-column` | 5 | — | One criterion across all alternatives. **Not the default** — it survives only as arm 2 of the ADR-0008 evaluation harness, awaiting validation (ADR-0011) |
| `review` | 6 | — | Self-critique: thin evidence, overlapping criteria, what would most change the picture |
| `run-analysis` | — | — | The whole pipeline, for a caller who wants one instruction |
| `resume` | — | — | Pick up a durable partial analysis (ADR-0017), keyed on the non-terminal codes |
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
