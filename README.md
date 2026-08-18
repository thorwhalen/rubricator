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
fill Pain and Market; leave the rest pending" is a supported request.

## Two ways to run it

Both are first-class, and the point of the architecture is that they share almost everything.

**As a Claude connector / MCP server.** No LLM API key. The intelligence is the Claude session
you are already in; `rubricator` supplies the tools, the schema, the prompts and the method. This
is the cheapest path to value and should work on day one.

**As a deployed agent.** A standalone service with its own model access, for scheduled or
unattended runs. Python, built on the `aw_agents` family — write the agent once, deploy to
several platforms.

The shared core is an **MCP tool specification**. The connector exposes it directly; the deployed
agent drives the same tools through its own loop.

## Status

Pre-implementation. This repository contains the specification: architecture decision records and
research briefs. Start at **[BRIEF.md](./BRIEF.md)**.

## License

Apache-2.0. See [LICENSE](./LICENSE).
