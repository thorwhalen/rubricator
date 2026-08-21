# ADR-0015: Source type, stance, and the constraint that stops inference passing as source

- **Status:** accepted
- **Date:** 2026-08-21
- **Deciders:** Thor Whalen

## Context
ADR-0006 requires a primary source, a secondary summary and the agent's own inference to be
distinguishable in every output, and names confusing them the most damaging error class this system
has. It supplies no mechanism.

An enum is not a mechanism. A model that wants a clean-looking citation will set the field to
`primary`, and nothing checks it. The empirical case is not speculative: an audit of four deployed
generative search engines found only **51.5%** of generated sentences fully supported by their
citations and only **74.5%** of citations actually supporting the statement they were attached to,
and characterised the systems as offering a "facade of trustworthiness" [1]. One bad citation in
four is worse in a comparison matrix than in prose, because the format certifies the content.

Separately, the evidence attached to a measure can currently only mean *supports*. An agent that
finds a contradicting span may cite it misleadingly or drop it, and either way nobody can count
which happened.

## Decision

**`source_type` sits on the reference, not on the document.** Five members — `primary`,
`secondary`, `tertiary`, `agent-inference`, `user-assertion`. The trichotomy is the established
vocabulary and is kept verbatim [2]; the two machine-author members are added because no external
vocabulary was written for a producer that manufactures plausible-looking sources at scale. It lives
on the reference because classification is relational to use: the same PDF is primary for what its
authors measured and secondary for its literature review, and both citations are right.

**Every evidence reference carries an orthogonal `stance`** — `supports | contradicts | qualifies |
background` — modelled on CiTO's citation-intent properties [3]. Orthogonal, because "a primary
source that contradicts the score" and "a secondary summary that supports it" are both real and both
need saying. An alternative scored 4 on a criterion while carrying a `contradicts` reference is the
most interesting cell in the analysis; without the field it is invisible, and what cannot be
represented cannot be counted.

**Three structural constraints, enforced by a deterministic tool and never by prompt instruction.**
ADR-0008 predicts that prompt-level honesty rules erode, and ADR-0010 forbids a tool from calling a
model — all three checks are decidable without one. They belong to `check_confidence_consistency`
and to `analysis_validate`, alongside the other structural checks, and they run whether or not
`check_citations` (ADR-0014) can reach the documents.

1. **`agent-inference` requires a non-empty `derived_from`**, listing the evidence references the
   inference was drawn from. This is `prov:wasDerivedFrom` given teeth [4]. An inference that cannot
   name what it was inferred from is not evidence; it is a justification, and it does not belong in
   the evidence array.
2. **`agent-inference` and `user-assertion` can never carry `confidence: high`.** ADR-0006 defines
   high confidence as *directly supported by cited source*. An agent's own inference is by
   definition not that, and a user's assertion is unverified by construction.
3. **A document produced by an agent run and re-ingested carries a marker, and every reference
   targeting it is forced to `secondary` at best, never `primary`.** This closes the loop the
   damaging error class actually arrives through — a generated summary, an extracted table, or a
   retrieval-time contextual preamble re-entering the corpus and then being cited as the thing
   itself.

**The marker is applied at ingestion, and nowhere else.** Nothing downstream can tell an
agent-authored document from a fetched one by inspection; only whatever writes a document into the
corpus knows where it came from. Every ingestion path therefore sets the marker — corpus load,
mid-session attachment, and the re-ingestion of a prior run's output — and no path leaves it unset.

**Evidence over time-based media requires a time selector *and* a quote over a registered
transcript**, per ADR-0014's locator profile. A bare timestamp is a pointer nobody can check, which
ADR-0006 already rules out.

**What this asks of `comparanda`** — requests, per ADR-0002, not changes this repo can make. On the
evidence reference: `sourceType`, `stance`, and `derivedFrom` as an array of evidence-reference ids,
joining the locator and `check` fields ADR-0014 asks for in the same module. On the source record:
the agent-run marker, which is what constraint 3 reads. (Schema names are `comparanda`'s
camelCase; the snake_case above is this repository's tool-side spelling of the same fields.)
`comparanda` already requires human and machine assertions to be distinguishable at a glance and
forbids colour as the sole channel carrying that; the same rule must reach evidence, so a `primary`
badge and an `agent-inference` badge differ by more than colour.

## Consequences
Some references become impossible to emit. That is the point: an agent that cannot support a claim
falls back to a qualified `missing` with a reason rather than dressing its own inference as a
source, which is ADR-0006's posture made mechanical.

The ingestion pipeline must carry origin metadata forever — a real cost, paid at the only place it
can be paid. `derived_from` turns the evidence array into a small graph, so the deterministic
validator also rejects cycles.

The three constraints are structural and therefore testable offline, in the connector, with no key:
ADR-0008 can regress on them directly instead of hoping a prompt held.

## Alternatives considered
- *An enum plus a prompt instruction.* This is what ADR-0006 effectively has today, and ADR-0008
  exists because such rules erode.
- *`stance` folded into the justification text.* Then it cannot be counted, filtered or rendered.
- *`source_type` on the document.* Cheaper to store and wrong — the same document is primary for one
  claim and secondary for another.
- *Adopting PROV-O wholesale.* It anchors derivation and attribution but has no member for the
  agent's own inference [4], which is the member this system most needs.
- *A model-based provenance check.* Forbidden inside a tool by ADR-0010, and unavailable in the
  connector at all.

## Evidence
Question rows 26–27 and § 5 of [`docs/research/findings-method.md`](../research/findings-method.md);
the full argument, including the enum's derivation and the constraint that carries it, is in
[`docs/research/sections/r5-evidence-citation.md`](../research/sections/r5-evidence-citation.md)
§ 3 (stance) and § 4.1–4.2 (source type and the three constraints).

1. [Evaluating Verifiability in Generative Search Engines — Liu, Zhang & Liang (2023), Findings of EMNLP](https://arxiv.org/abs/2304.09848)
2. [Introduction to Primary Sources — History, Philosophy and Newspaper Library, University of Illinois](https://www.library.illinois.edu/hpnl/tutorials/primary-sources/)
3. [CiTO, the Citation Typing Ontology — Peroni & Shotton, SPAR Ontologies](https://sparontologies.github.io/cito/current/cito.html)
4. [PROV-O: The PROV Ontology — Lebo, Sahoo & McGuinness (eds.), W3C Recommendation (2013)](https://www.w3.org/TR/prov-o/)
