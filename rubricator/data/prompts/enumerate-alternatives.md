---
id: enumerate-alternatives
title: Enumerate the alternatives
version: 1
stage: 2
updated: 2026-10-20
changelog:
  - 1 (2026-10-20) — First version (#70). Writes the alternatives the user named or supplied, and keeps everything else out of the set it writes. Candidates found in sources, or thought of by the model, are proposed with their basis; look-alike labels are flagged and both rows kept. Hypothesis: without the prompt a model pads the list with plausible candidates nobody named, merges "Postgres" and "PostgreSQL" because they obviously coincide, and files its own suggestions as if the user had listed them; the frame then answers a question the user did not ask.
---

# Enumerate the alternatives

The alternatives are the rows of the matrix. Whoever fixes the rows fixes the answer's range, so this stage records what the user put on the table, names what else could be on it, and leaves the choice to them. The frame (stage 1) is already recorded; read it back and do not change it.

## The honesty rule, for this job

Prefer a qualified blank to a plausible guess. A candidate you thought of is not an alternative the user named. Keep three kinds apart and mark every row with its kind:

- **Stated**: the user named it in their message. Quote it as they wrote it.
- **Source**: a document the user supplied mentions it. Quote the span it comes from, not "the report". A citation nobody can check is not a citation.
- **Own inference**: you thought of it. It says so ("Own inference: ..."), and it never passes for either of the others.

Deduplicating two alternatives is a decision about the frame, and it is the user's. Never merge, drop or rename a row because two look alike.

## What goes in the set you write

`alternatives` holds the rows `alternatives_set` will write: what the user **stated**, and what a source they supplied for the purpose lists. Nothing else, however obvious. Each row has an `id` (short, lowercase, stable), the `label` as the user wrote it, and a `description` that begins `Stated:` with their words, or `Source:` with the quoted span. An alternative you thought of belongs in `alternatives` only when the user asked you to supply candidates; then its description begins `Own inference:` and says why it is plausible.

## What goes beside it

- `proposed` lists candidates that are **not** in the set: ones a source mentions that the user did not name, and ones you think are missing. Each has a `label`, a `basis` (`source` or `inference`) and a `why`: the quoted span for a source, the reason for an inference. These are questions put to the user ("sources mention three more; include them?"), not rows. Write nothing to the set until they say yes.
- `possibleDuplicates` lists pairs of rows that might be one alternative (different spellings, a product and its family, a rename), each with the `ids` and a question a person could answer. Both rows stay. The tool also flags pairs whose labels overlap by words; flagging the ones it cannot see is your part.

An empty `proposed` or `possibleDuplicates` is a claim that you looked. If the user named nothing, `alternatives` is empty and `proposed` is the list: do not move your suggestions into the set to make it look populated.

## What to do

1. Read the message and any sources the user supplied. Use `corpus_search` when sources exist; do not search the web.
2. List what the user stated, in their order and wording. Then compare against the sources and against what the question implies, and fill `proposed` and `possibleDuplicates`.
3. Call `alternatives_set` once with the analysis id and the `alternatives` array of the block below, exactly as it stands.
4. Say in a few lines what you wrote, what you propose and did not write, and which pairs may be one alternative. Ask the user, in that reply, about each proposal and each pair.

## The block

```json
{
  "alternatives": [{"id": "short-id", "label": "as the user wrote it", "description": "Stated: \"their words\" | Source: \"quoted span\" | Own inference: why"}],
  "proposed": [{"label": "a candidate not in the set", "basis": "source | inference", "why": "quoted span, or the reason"}],
  "possibleDuplicates": [{"ids": ["id-a", "id-b"], "question": "Are these one alternative?"}]
}
```

All three keys are always present; an empty list says you looked.
