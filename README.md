# rubricator

**The agent that turns a pile of context into a defensible comparison.**

A *rubricator* was the scribe who went through a finished manuscript adding the rubrics — the
headings and marks, in red, that made a wall of text navigable. This one reads your documents,
your prompt, and your half-formed question, and produces a structured comparison: alternatives,
criteria, scores, confidence, justifications, and citations back to the source.

Its output is a **comparanda** analysis. That schema is the contract between the two projects, and
the reason they are separate repositories: `comparanda` renders and persists comparisons no matter
who made them, and `rubricator` makes them whether or not anyone renders them.

## What it does

Given a subject and some context — a prompt, a folder of documents, a repository, a conversation —
it:

1. **elicits the frame**: what is actually being compared, and against what criteria. Usually the
   most valuable step, and the one most tools skip;
2. **populates the matrix**: a score, a confidence and a one-line justification per cell;
3. **cites**: evidence references pointing at spans in the source, so a reader can check;
4. **reports what it could not determine**, using qualified missingness rather than a confident
   guess.

It is opinionated about method — see the research brief — and flexible about instruction. "Only
fill Pain and Market; leave the rest deferred" is a supported request, and what comes back is a
valid document about an unfinished analysis rather than a broken one.

## Two ways to run it

Both are first-class, and the point of the architecture is that they share almost everything.

**As a Claude connector / MCP server.** No LLM API key. The intelligence is the Claude session
you are already in; `rubricator` supplies the tools, the schema, the prompts and the method. This
is the cheapest path to value and should work on day one.

    pip install "rubricator[mcp]"
    rubricator-mcp                        # stdio; or: python -m rubricator.mcp
    rubricator-mcp --root ./analyses      # keep analyses in this directory
    rubricator-mcp --transport http       # Streamable HTTP on 127.0.0.1:8765, no auth: see docs/connector-http.md

Point an MCP client at that command. The `mcp` extra installs the MCP server framework and no
model client; the model access lives in the separate `agent` extra.

**As a deployed agent.** A standalone service with its own model access, for scheduled or
unattended runs. Python, on the official MCP SDK — an earlier draft named a different framework;
see [why that was rejected](https://github.com/thorwhalen/rubricator/discussions/112).

The shared core is an **MCP tool specification**. The connector exposes it directly; the deployed
agent drives the same tools through its own loop.

## Status

Early. The v1 vertical slice runs — the deterministic tool layer, a store, and the same verbs over
both a CLI and an MCP connector — and the first prompt ships with it. Most of the repository is
still specification: architecture decision records and research briefs.

Analyses persist in `~/.local/share/rubricator/working/` (set `RUBRICATOR_DATA_DIR` to move the
whole data root) and are kept for 30 days from their last write; an export is yours to keep.

Start at **[BRIEF.md](./BRIEF.md)**. [`CHANGELOG.md`](./CHANGELOG.md) is not a release log; it
records the boundaries across which a number stops meaning the same thing.

## License

Apache-2.0. See [LICENSE](./LICENSE).
