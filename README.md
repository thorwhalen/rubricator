# rubricator

**The agent that turns a pile of context into a defensible comparison.** It reads your documents, your prompt and your half-formed question, and produces a [comparanda](https://github.com/thorwhalen/comparanda) analysis: alternatives, criteria, scores, confidence, justifications, and citations back to spans in the source, with honest blanks where the sources are silent.

*Human reading this?* [Skip to the part for carbon-based contributors](#for-carbon-based-contributors).

## For agents

rubricator is an **MCP tool surface plus versioned prompts**. The tools are deterministic: they validate, store, search, check citations and count. The judgement is yours, the calling model's. No tool calls a model, so the connector needs no API key.

**Where things are.**

- [`CLAUDE.md`](CLAUDE.md) is the guide for an agent working *on* this repository: the vocabulary, the standing constraints, where everything lives.
- [`skills/`](skills/) holds two developer skills, `rubricator-dev-tool-contract` (read before adding or changing a tool) and `rubricator-dev-prompt-change` (read before editing a prompt). In a clone they are already active in Claude Code through the relative symlinks in `.claude/skills/`. With a `gh` release that has the `skill` command, `gh skill install thorwhalen/rubricator rubricator-dev-tool-contract` installs one elsewhere.
- [`rubricator/surface/frozen.py`](rubricator/surface/frozen.py) is the tool surface: one row per tool, implemented or planned, with the exact description and schemas a model is shown.
- [`rubricator/data/prompts/`](rubricator/data/prompts/) holds the method as prompts (`propose-criteria`, `confirm-frame`, `score-cell`, `resume`). Over MCP, read them with `prompts_list` and `prompts_get`.
- End-user workflows (run an analysis, add or re-score a criterion, audit an analysis) ship as those MCP prompts, not as skills ([ADR-0003](docs/adr/0003-mcp-as-the-shared-core.md), [ADR-0007](docs/adr/0007-outputs-and-packaging.md)).

**Connect it to Claude Code.**

    uv tool install "rubricator[mcp] @ git+https://github.com/thorwhalen/rubricator"
    claude mcp add rubricator -- rubricator-mcp

Then ask, for example: *"Use rubricator to compare three note-taking apps for a two-person team. First call `prompts_list`, read the prompts you need with `prompts_get` and follow them; ask me what matters before you score anything."* Claude Desktop and HTTP setup: [docs/install.md](docs/install.md).

**What you can do with it.** Open an analysis, add source documents and search them lexically, record the frame, alternatives and criteria, get the user's confirmation, write scores with span citations or qualified blanks, and read back completeness and agreement. The same verbs are plain Python functions:

```python
from rubricator.compose import build_runtime
from rubricator.surface import bind

verbs = bind(build_runtime(blobs={}))  # an in-memory store; omit blobs to persist on disk
verbs["analysis_open"](analysis_id="kettles", question="Which kettle for a small office?")
verbs["corpus_add"](analysis_id="kettles", sources=[{
    "id": "k2", "agentProduced": False,
    "text": "The K2 kettle boils one litre in under four minutes. "
            "Boil-dry protection cuts the power when it runs empty.",
}])
hits = verbs["corpus_search"](analysis_id="kettles", query="boil-dry protection")["hits"]
assert "Boil-dry protection" in hits[0]["text"]
```

Every verb validates its arguments against the frozen input schema and refuses with a message naming what to fix. `verbs["frame_set"](analysis_id="kettles", ambiguities=[], colour="blue")` is refused, naming the allowed fields.

**Rules the tools hold you to.** Elicit the frame before scoring: scores are refused until the user has confirmed the frame, alternatives and criteria ([ADR-0005](docs/adr/0005-the-elicitation-pipeline.md)). Prefer a qualified blank to a confident guess ([ADR-0006](docs/adr/0006-evidence-and-honest-uncertainty.md)). Cite spans, not documents. Mark what a model wrote as agent-produced: a reference into it is secondary at best.

## What it does

Given a subject and some context, a prompt, a folder of documents, a repository or a conversation, it:

1. **elicits the frame**: what is actually being compared, and against what criteria. Usually the most valuable step, and the one most tools skip;
2. **populates the matrix**: a score, a confidence and a one-line justification per cell;
3. **cites**: evidence references pointing at spans in the source, so a reader can check;
4. **reports what it could not determine**, using qualified missingness rather than a confident guess.

It is opinionated about method and flexible about instruction. "Only fill Pain and Market; leave the rest deferred" is a supported request, and what comes back is a valid document about an unfinished analysis rather than a broken one.

Its output is a **comparanda** analysis. That schema is the contract between the two projects, and the reason they are separate repositories: `comparanda` renders and persists comparisons no matter who made them, and `rubricator` makes them whether or not anyone renders them.

An analysis made elsewhere comes in the same way it goes out: `rubricator import colleague.json` validates the comparanda document, splits it into a frame and one file per contributor, and stores it so it can be read and audited (the `audit-existing` prompt). A document the merge would refuse is refused whole, with the reason.

## Two ways to run it

Both are first-class, and the point of the architecture is that they share almost everything.

**As a Claude connector / MCP server.** No LLM API key. The intelligence is the Claude session you are already in; rubricator supplies the tools, the schema, the prompts and the method. Install it as above. It is not on PyPI yet, hence the GitHub URL. The `mcp` extra installs the MCP server framework and no model client; model access lives in the separate `agent` extra. `rubricator-mcp --transport http` serves Streamable HTTP on loopback with no authentication: [docs/connector-http.md](docs/connector-http.md).

**As a deployed agent.** A standalone service with its own model access, for scheduled or unattended runs. Python, on the official MCP SDK; an earlier draft named a different framework, and [why that was rejected](https://github.com/thorwhalen/rubricator/discussions/112) is recorded. Not built yet.

The shared core is an **MCP tool specification**. The connector exposes it directly; the deployed agent will drive the same tools through its own loop.

## Status

Early. The v1 vertical slice runs: the deterministic tool layer, a store, lexical corpus search, and the same verbs over both a CLI and an MCP connector, with the first prompts shipped beside them. Much of the repository is still specification: architecture decision records and research briefs.

Analyses persist in `~/.local/share/rubricator/working/` (set `RUBRICATOR_DATA_DIR` to move the whole data root). **They are kept for 30 days after their last write**, then expire and may be deleted; export one to keep it.

## For carbon-based contributors

**Why the name.** A *rubricator* was the scribe who went through a finished manuscript adding the rubrics, the headings and marks in red that made a wall of text navigable.

**Set up and run the tests.**

    uv venv .venv && . .venv/bin/activate
    uv pip install -e ".[test,mcp]"
    python -m pytest -q

The suite includes the package's doctests. CI runs it bare (no extras, Python 3.10 and 3.12), then the connector tests with the `mcp` extra, then the determinism checks on their own, so a regression in the one architectural rule is unmistakable.

**Read in this order.** [BRIEF.md](BRIEF.md), then [docs/adr/](docs/adr/README.md) (decisions; `proposed` means genuinely open), then the [research ledger](docs/research/README.md). [CHANGELOG.md](CHANGELOG.md) is not a release log: it records the boundaries across which a number stops meaning the same thing.

**Contributing.** The public-repo rule is strict: no content from any private engagement, and fixtures use invented domains, not anonymised ones. A prompt change needs an evaluation run before it lands. A tool is a row in the frozen surface before it is code. Questions go to [issues](https://github.com/thorwhalen/rubricator/issues) or [discussions](https://github.com/thorwhalen/rubricator/discussions).

## License

Apache-2.0. See [LICENSE](./LICENSE).
