# ADR-0005: Elicit the frame before scoring anything

- **Status:** accepted
- **Date:** 2026-08-18

## Context
The tempting design takes a prompt and returns a filled matrix. It is also the design that produces
confident, useless comparisons, because the hard part is not scoring — it is deciding *what* is
being compared and *against what*. A matrix with the wrong criteria is worse than no matrix,
because it looks like analysis.

Experience from the originating work: the criteria were the subject of an extended discussion
before any cell was filled, and that discussion determined everything downstream. The single
biggest failure mode was scoring against criteria nobody had interrogated.

## Decision
A staged pipeline, with the frame settled before the matrix is populated:

1. **Frame** — establish the subject, the decision being made, and who is deciding. Surface
   ambiguity rather than resolving it silently.
2. **Enumerate alternatives** — from context, with explicit gaps ("you named six; sources mention
   three more — include them?"). Deduplicate near-identical entries and say so.
3. **Propose criteria** — with definitions, polarity (is higher better?), level of measurement,
   and any veto status. Every criterion arrives with a *definition*, because undefined criteria get
   scored inconsistently. Flag overlapping criteria explicitly: double-counting is the classic
   defect of hand-built matrices.
4. **Confirm with the user** — a checkpoint before the expensive step. Skippable by explicit
   instruction, never by default.
5. **Populate** — score, confidence, one-line justification and citations per cell. Honour partial
   instructions ("fill these two criteria, mark the rest pending").
6. **Review** — self-critique: which scores rest on thin evidence, which criteria overlap, which
   cells would most change the picture if wrong.

Step 4 is the one under pressure to remove. Keep it. It is where the analysis becomes the user's
rather than the model's.

## Consequences
Slower than one-shot generation, and produces something defensible. The pipeline is also the
natural tool decomposition for ADR-0003: each stage is one or more MCP tools plus a prompt.
