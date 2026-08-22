# ADR-0023: One bytes mapping, two targets, and a projection that is write-only by type

- **Status:** accepted
- **Date:** 2026-08-22
- **Deciders:** Thor Whalen

## Context
ADR-0017 mandates a store behind a Mapping interface, in the platform user-data directory, never
inside the package. Its 2026-08-22 amendment splits the stored record into a frame plus one file per
contributor and rules that the merge happens on read. What neither contemplates is where those files
physically live for a *team*, and what — if anything — GitHub is for.

The owner settled both:

> "Files are the single source of truth — one file per contributor per analysis, so two people
> editing never collide; schema-validated, diffable, portable; **the same code path as the
> filesystem backend with a different root.** GitHub Discussions and Issues are a **generated
> one-way projection**, written from the files and **never read back as truth**."

One ecosystem fact shapes the plan, and it was checked rather than assumed: the local
GitHub-over-Mapping package is **entirely read-only** — a source scan of the installed release finds
no `__setitem__`, no persister base and no `MutableMapping` anywhere in it. The GitHub target must
be built. The filesystem side needs nothing built: the ecosystem's file and JSON stores are already
`MutableMapping` subclasses.

## Decision

**The persistence interface is `MutableMapping[str, bytes]`, and it is the only interface this
design invents — which is to say it invents none.** It is `collections.abc`; `dol` already supplies
implementations; and every `dol` decorator — filtering, key caching, read-only wrapping, caching —
applies to all of them for free. There is deliberately **no port set**: splitting ports before any
of them has two implementations freezes a guess about which axes vary.

**`AnalysisStore` is a facade over exactly one injected mapping.** The JSON codec, the key template
and the write-time validation sit **above** the seam; only the leaf bytes store varies. It exposes
`frame`, `contributions`, `write_contribution`, `read`, `renditions`, `analyses` and
`capabilities` — and `analyses()` is present from v1 specifically because a migration needs to
enumerate, and adding it later means editing every implementation.

**Write-time honesty validation is unbypassable.** `write_contribution` validates on the way in
through an `on_write` hook injected at the composition root. There is no path in any backend that
stores an invalid document, and no backend may grow its own write path past it.

**The merge is a pure function in the package core, never in a backend.** If two backends own their
own merge, the filesystem and GitHub cases diverge and nobody notices for months. Same inputs,
byte-identical output; order-independent; a genuine same-version conflict refused rather than
resolved.

**Two targets, and the second is literally the first with a different root.** A filesystem store in
the platform user-data directory is v1. The GitHub target is a subclass that writes, adds, commits,
then pulls with rebase and pushes — **exactly one retry, then fail loudly, never force**. Diffs and
history come free. The composition root changes by one argument; `AnalysisStore`, the merge, the
ingest, every tool, the MCP server, the backend and the browser all see a
`MutableMapping[str, bytes]` and cannot tell the difference. Migration is
`for k, v in old.items(): new[k] = v`.

**`multi_writer` may only be declared true when `per_contributor_files` is.** The
collision-freedom invariant is what makes a locking-free push and a last-write-wins browser
provider safe; the capability pair is where that invariant is recorded and tested rather than
remembered. The capability record mirrors the companion view layer's provider capabilities field for
field, because two capability vocabularies that drift produce a UI that lies.

**The GitHub projection is write-only by type.** A Discussion per criterion carrying the framing
argument, an Issue per cell needing evidence; keys stable and derived from the analysis so a re-run
updates rather than duplicates. The writer protocol has **no read method**, so "never read back as
truth" is enforced by the type rather than by a comment, and adding a read path later requires
changing the protocol — a visible decision.

**Projection is invoked by a CLI verb, never by a tool.** A tool reaching GitHub would break the
determinism boundary and the connector's offline guarantee in one call. That is why one CLI verb is
in v1 even though ADR-0007's amendment puts the CLI last in the shipping order.

**v1 renders the projection for real and writes it nowhere.** The projector functions are complete
and tested; the writer is a null implementation that returns the documents. Zero API calls, fully
testable offline, and the shape is proved before anything is published. This is the purest instance
of the "whole architecture from v1, simple component wired in" directive ADR-0020 records — and it
is the correct order, because a v1 depending on a write path that does not exist upstream is a v1
that does not ship.

## Consequences
A team moves from a private folder to a shared repository by changing one argument, and gets review,
diffs, blame and history without this project implementing any of them. The projection makes the
criteria argument — which is the part of the product users actually value — legible in the place
teams already argue.

The GitHub target is the **largest single build item in the persistence layer**, because the
ecosystem supplies no write path. Writing it as a `dol` subclass keeps it at roughly a hundred
lines; writing it as a contents-API client would be a second code path and is deliberately deferred
to the case that needs it, a server with no working tree.

**And one gap is inherited rather than solved: `dol` has no async support**, while MCP handlers are
async. Every store call from a handler either blocks the event loop or needs a thread-pool wrapper.
That choice belongs in `AnalysisStore`, once, and it is not made in v1.

## Alternatives considered
- *A five-port abstraction mirroring the companion repository's.* Four of the five are view-state
  conveniences. One interface with two implementations is a seam; five interfaces with one
  implementation each is a guess.
- *A GitHub contents-API key-value store instead of a clone.* No working tree, so no diff, no local
  read, and a network round trip per key. Right for a server; wrong for the first target.
- *Reading the projection back to reconcile edits made in a Discussion.* The seductive one. It makes
  GitHub a second source of truth with a different schema and no validation, and every conflict then
  has two authorities.
- *One shared analysis file with locking.* This is the failure the whole layout exists to prevent.
