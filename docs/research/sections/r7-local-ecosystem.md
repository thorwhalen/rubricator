# The local ecosystem — does ADR-0004 survive contact?

**Research question(s):** Read the local `aw_agents`, `aix`, `py2mcp` and `oa` packages properly.
Can `aw_agents` host an MCP surface that exposes **prompts and resources**, not only tools — which
ADR-0003 requires? Does ADR-0004 (Python for the agent runtime, on `aw_agents`) survive? Where
should the MCP server live? What must `aix` gain before the variance/sampling work of ADR-0008 is
possible? What are this ecosystem's Python project conventions?

**Brief section:** `docs/research/method.md` §5 (Agent architecture) and the BRIEF's first
deliverable item 4 ("your reading of `aw_agents` and whether ADR-0004 survives it").

**Evidence grade:** **strong** — every claim about a local package comes from reading its source,
tests and packaging metadata, and the two decisive facts (that `aw_agents` wires only `list_tools`
and `call_tool`; that a `py2mcp`-built server is a live `FastMCP` object carrying `.prompt`,
`.resource` and `.add_resource`) were executed and confirmed against the installed versions.
Protocol and backend claims are cited to the MCP specification, the FastMCP documentation, the
Claude Code MCP reference and the LiteLLM documentation.

## Bottom line

ADR-0004 **survives on language and fails on framework**. Python is the right host: it is where the
schema tooling, the LLM facade, the MCP builder and every project convention already are. But
`aw_agents` cannot do the job ADR-0003 assigns to the MCP layer. Its MCP adapter registers exactly
two handlers — `list_tools` and `call_tool` — over the low-level MCP SDK server. There is no
`prompts/list`, no `prompts/get`, no `resources/list`, no `resources/read`, and no seam to add them
without forking the adapter. Since "prompts ship as **content the runtime can serve**" is the
sentence in ADR-0003 that makes one tool specification serve two runtimes, that single fact decides
the question. Build the MCP surface on **`py2mcp`/FastMCP** instead: it already returns a live
`FastMCP` object, so tools come from `py2mcp.mk_mcp_server(...)` and prompts and resources are
registered directly on the returned server; it already ships both transports rubricator will want
(stdio for Claude Desktop/Code, Streamable HTTP with OAuth 2.1 resource-server auth for a hosted
connector); and its adapter layer, unlike `aw_agents`', is tested. Amend ADR-0004 accordingly and
demote `aw_agents` to an optional later adapter for a non-MCP surface. On `aix`: it is the correct
chokepoint by policy and it is *not currently sufficient* — `chat()` returns
`response.choices[0].message.content` and discards everything else, so `n`-sampling, `seed`,
`logprobs`, token usage and provider-enforced JSON schema are all unreachable through the facade
even though LiteLLM underneath supports every one of them. Six concrete `aix` issues are listed
below; none is large, and all of them are facade gaps rather than capability gaps.

## Findings

### 1. `aw_agents` — a tool-exposure shim, not an agent framework

**EVIDENCE** (source read: package `__init__`, `base.py`, `util.py`, both adapters, the one bundled
agent, both test files, `pyproject.toml`, CHANGELOG and git log; version 0.1.3, classified
`Development Status :: 3 - Alpha`).

**The declarative spec is two abstract methods.** `AgentBase` is an ABC requiring
`get_tools() -> list[dict]` and `execute_tool(name, arguments) -> dict`, plus a concrete
`get_metadata()`. There is no spec object, no schema, no registry, no declaration language. Tools
are hand-written dicts (`{"name", "description", "parameters"}`) returned from a method, assembled
with a `create_json_schema(properties, required, **kwargs)` helper that is a dict literal with a
docstring. `ToolExecutionResult` is a small success/data/message/warnings/metadata carrier, but the
base class types `execute_tool`'s return as a plain `dict`, so the carrier is advisory.
"Declarative-spec-to-agent machinery", as ADR-0004 anticipated, is not what is there.

**The MCP adapter is tools-only, and this is the decisive finding.** `MCPAdapter` imports the
official MCP Python SDK's *low-level* server (`mcp.server.Server`, `mcp.server.stdio.stdio_server`,
`mcp.types.Tool`/`TextContent`) [10] — not FastMCP — and its `_setup_handlers` registers exactly
two decorators: `@self.server.list_tools()` and `@self.server.call_tool()`. Nothing else. I
confirmed by introspection that the same low-level `Server` class *does* expose
`list_prompts`, `get_prompt`, `list_resources`, `list_resource_templates`, `read_resource`,
`subscribe_resource` and `unsubscribe_resource`. So the capability exists in the SDK and is simply
unwired here — and there is no hook, kwarg or subclass point through which a consumer supplies
them. You would either fork `_setup_handlers` or reach past the adapter into `adapter.server` and
register handlers yourself, at which point `aw_agents` contributes nothing but an interface shape.

**Plainly, for the record: `aw_agents` cannot host an MCP surface that exposes prompts and
resources.** ADR-0003 requires exactly that. This is the finding that decides ADR-0004.

**Tool results are stringified.** `call_tool` returns `[TextContent(type="text", text=...)]` where
the text is a human-formatted string built from `"✓ " + message`, `str(result["data"])` and a
bulleted warnings list. rubricator's tools return structured comparanda fragments; `str(dict)` is a
Python repr, not JSON, and a model receiving `{'score': 3, 'confidence': 'medium'}` in Python repr
must reverse-engineer it. FastMCP, by contrast, derives structured content from typed return values.
This alone would be disqualifying.

**Transport and deployment.** stdio only. No Streamable HTTP, no SSE, no authentication, no session
identity. The `OpenAPIAdapter` (FastAPI) builds one POST endpoint per tool, generating a Pydantic
model per tool from the JSON schema via a `_json_type_to_python` map that flattens `"array" -> list`
and `"object" -> dict` — it **drops `items` and `properties` sub-schemas**. Every rubricator tool
input is nested (a list of criteria objects, a list of evidence spans), so the OpenAPI surface would
lose its contract precisely where the contract matters. It also sets
`allow_origins=["*"]` together with `allow_credentials=True`.

**No model access, no loop, no state, no streaming.** A grep of the package source for `litellm`,
`openai`, `anthropic`, `prompt`, `resource`, `session` and `stream` turns up no model-access, prompt,
resource, session-identity or streaming machinery: the only hits are a `requests.Session` and
`stream=True` inside the bundled download agent, the `read_stream`/`write_stream` pair handed to
`stdio_server`, and a `chat.openai.com` URL in a docstring. The README's
roadmap lists "Persistent state management" as an unchecked box. So the ADR-0004 premise — that the
deployed agent gets "its own model access" from `aw_agents` — does not hold either: you write the
loop and wire the model client yourself regardless of which framework you pick.

**Maturity.** Two test files, eleven test functions, all of them exercising the single bundled
`DownloadAgent` (its tool list, its metadata, `list_downloads`, an unknown-tool path) and the
`DownloadEngine`'s filename/extension routing. **Zero tests touch `MCPAdapter` or `OpenAPIAdapter`**
— the only part of the package rubricator would consume is the untested part. The recent commits
are `wads` scaffolding chores (SPDX license, `.editorconfig`, CHANGELOG backfill), not feature work.

**REASONING (not evidence):** the package name and README promise "write once, deploy to several
chatbot platforms". What is delivered is one two-method interface, two adapters and one agent. That
is a reasonable seed and a poor foundation for a project whose *entire architecture* (ADR-0003) is
"the MCP tool specification is the shared core". Adopting it would mean rubricator immediately
maintaining a fork of the layer it depends on most.

### 2. `py2mcp` — the right base, with one small gap rubricator (or an upstream PR) closes

**EVIDENCE** (source read: `main.py`, `base.py`, `serve.py`, `http.py`, `trans.py`, `util.py`, four
test modules, README, `pyproject.toml`; version 0.1.9, `Development Status :: 4 - Beta`, single
runtime dependency `fastmcp`).

The API is three builders plus two runners:

- `mk_mcp_server(funcs, *, name, input_trans, auth, middleware, instructions) -> FastMCP`
- `mk_mcp_from_refs(['pkg.mod:func', ...], ...)` — from config strings, for a JSON-configured bundle
- `mk_mcp_from_store(MutableMapping, name=...)` — auto-generates list/get/set/delete tools
- `serve_stdio(refs, ...)` and `python -m py2mcp --config ...` — the local path a Claude Desktop
  one-click bundle launches
- `mk_http_app(...)` / `serve_http(...)` — Streamable HTTP as an OAuth 2.1 **resource server**: it
  validates a managed IdP's JWTs with mandatory RFC 8707 audience binding [11] and publishes RFC
  9728 protected-resource metadata [12]. It never issues tokens.

**Prompts and resources are one line away, and I verified it.** `mk_mcp_server` returns a live
`fastmcp.server.server.FastMCP`; on the installed version (`fastmcp` 3.1.1, `py2mcp` 0.1.9) that
object carries `.prompt`, `.resource` and `.add_resource`. FastMCP declares prompts with
`@mcp.prompt` on a function whose parameters become the prompt's arguments, returning a string, a
list of messages, or a `PromptResult` [5]; resources with `@mcp.resource("scheme://uri")` plus
`FileResource` / `DirectoryResource` / `TextResource` registered through `add_resource` [6]. So
`py2mcp` supplying only tools is not a blocker — it is a missing convenience. **Gap:** the builders
have no `prompts=` / `resources=` kwarg, so rubricator either registers them on the returned object
or contributes the kwargs upstream. Recommend the upstream contribution; it mirrors the existing
`middleware=` and `instructions=` kwargs exactly.

Two other seams matter to rubricator. `middleware=` accepts FastMCP middleware attached at
construction, whose hooks include `on_call_tool`, `on_get_prompt`, `on_read_resource` and the
corresponding list hooks [7] — the correct place for a per-analysis audit log and token accounting,
so no tool has to remember to record itself. `instructions=` sets the server's model-facing
description, which is where ADR-0006's honesty rule belongs at the server level, restated in every
prompt as `docs/prompts/README.md` requires.

**Smaller notes.** `input_trans` is a single `dict -> dict` applied to the kwargs of *every* tool —
coarse, and rubricator probably will not use it. Despite the README's "input/output transformations"
heading, only `mk_input_trans` exists; there is no output transformation. The repo has two test
trees (`py2mcp/tests/` and `tests/`), a layout wart worth not copying.

### 3. Claude clients really do surface prompts and resources — so ADR-0003's design pays off

**EVIDENCE.** MCP prompts are specified as **user-controlled**: "Prompts are designed to be
user-controlled, meaning they are exposed from servers to clients with the intention of the user
being able to explicitly select them for use", "typically … triggered through user-initiated
commands", the spec's own example being slash commands [1]; the companion Resources page defines the
matching `resources/list`, `resources/read` and `resources/templates/list` methods [2]. The Claude
Code MCP reference confirms the concrete
mechanism: "MCP servers can expose prompts that become available as commands in Claude Code … MCP
prompts appear with the format `/mcp__servername__promptname`", and separately "MCP servers can
expose resources that you can reference using @ mentions … Use the format
`@server:protocol://resource/path`", with "Claude Code automatically provides tools to list and read
MCP resources when servers support them" [4].

**REASONING (not evidence):** this is exactly the delivery vehicle ADR-0007 item 2 wants for the
"skill / prompt bundle", and it means items 1 and 2 of ADR-0007 are *the same artifact* rather than
two. A connector that serves `frame`, `enumerate-alternatives`, `propose-criteria`, `score-column`,
`review` and `audit-existing` as prompts gives the user `/mcp__rubricator__propose_criteria` for
free, and serving the comparanda JSON Schema and the criteria-hygiene checklist as resources gives
`@rubricator:rubricator://schema/analysis.json`. None of that is reachable through `aw_agents`.

One escape hatch worth knowing about and *not* relying on: MCP **sampling** lets a server ask the
client to run inference — "no server API keys necessary" — but clients that support it "MUST declare
the `sampling` capability", and the spec adds that there "**SHOULD** always be a human in the loop
with the ability to deny sampling requests" — a recommendation, not a hard requirement [3].
The Claude Code MCP reference documents **elicitation** support explicitly ("MCP servers can request
structured input from you mid-task using elicitation … No configuration is required on your side")
but does not document sampling at all [4]. **REASONING:** treat sampling as unavailable for v1 and keep ADR-0003's rule
intact — no tool may require a model; where inference is needed, expose a prompt plus a
deterministic validator tool. Elicitation, however, is available and is a genuinely good fit for
ADR-0005's step-4 confirmation checkpoint; consider it after the prompt-driven version works.

### 4. `aix` — the right chokepoint, currently insufficient for ADR-0008

**EVIDENCE** (source read: `__init__.py`, `chat.py`, `prompts.py`, `config.py`, `credentials.py`,
`batches.py`, `stores.py`, `vision.py`, root `conftest.py`, `tests/test_import_is_hermetic.py`,
README, CONTRIBUTING, `pyproject.toml`; version 0.0.39).

**What is genuinely good and should simply be used.**

- *Config layering with one source of truth.* Precedence, highest first: explicit call argument →
  `configure(...)` / `using(...)` → `AIX_*` environment variables → a user TOML file → shipped
  defaults. Frozen dataclasses per capability (`ChatConfig` carries `model`, `temperature`,
  `max_tokens`), and `using(...)` is a context manager that restores on exit — the natural way for an
  evaluation harness to pin a model per run.
- *Semantic aliases.* `fast` / `best` / `cheap` in `DEFAULT_ALIASES`, extended via
  `configure(aliases=...)` or the `[aliases]` TOML section; unknown names pass through as literal
  model ids. Good for expressing "score with `best`, self-critique with `fast`" without hardcoding
  a model.
- *Credentials.* Provider inferred from the model id; resolution order explicit-arg → provider env
  var (with soft `.env` discovery) → per-user config store → interactive prompt-and-persist. Missing
  keys raise `MissingCredentialError` naming which key, how to set it and where to get one.
  `check_keys()` reports availability without revealing values.
- *Hermetic import.* `aix._litellm` defers the LiteLLM import because importing LiteLLM fetches its
  model-cost map over HTTPS; `tests/test_import_is_hermetic.py` guards this in a subprocess under a
  socket guard, with the environment variable that would mask the failure explicitly stripped. This
  is a package that has been debugged in anger, and it is the reason to prefer it over a raw SDK
  beyond the owner's standing rule.

**The blocking gap: `chat()` throws the response away.** `chat(prompt, *, model, temperature,
max_tokens, stream, api_key, **kwargs) -> str | Iterable[str]`, and its extractor is
`response.choices[0].message.content or ""`. Consequences, all directly in rubricator's path:

- `n=` reaches LiteLLM through `**kwargs`, the request is billed for *n* samples, and choices 1..n-1
  are silently discarded. Provider-side n-sampling is therefore unusable through the facade.
- `usage` (prompt/completion tokens, hence cost), `finish_reason`, `logprobs` and the raw response
  are all unreachable. An evaluation suite cannot report cost per analysis or detect truncation.
- `seed=` passes through undocumented and untested, with no way to learn whether the provider
  honoured it.
- `response_format=` passes through, but since the declared return type is `str`, every caller
  hand-rolls `json.loads` and its own fence-stripping.

**Structured output today is prompt engineering, not enforcement.** Two paths exist:

1. `prompt_func(template, *, output_schema={'name': str, 'age': int}, egress=..., model=...,
   temperature=...)`. `_schema_to_json_schema` builds a **flat** schema from a mapping of Python
   types; the schema is appended to the prompt as "Respond with valid JSON matching this schema: …
   Only return the JSON, no additional text"; `_parse_structured_output` strips a markdown fence and
   calls `json.loads`. There is no `response_format`, no nesting (no array-of-objects, no enums, no
   required/optional distinction), **no validation of the parsed object against the schema**, and no
   retry. rubricator's cell payload — score, confidence, justification, and a list of evidence spans
   each with a document id and a character range — is not expressible in it.
2. `constrained_answer(prompt, valid_answers, *, model, temperature, enhance_prompt=False, n=1)`.
   This one does use real JSON mode (`response_format={"type": "json_object"}`) and expects
   `{"answer": ...}`, accepting a list of options, `bool`/`int`/`float`, or a `(min, max)` range.
   **Defect worth filing:** the returned answer is *type-coerced* but never checked for membership
   in `valid_answers`, and a range is never bounds-checked — so with `["cats", "dogs"]` a reply of
   `"lizards"` is returned as a valid answer. For rubricator, where a criterion's anchored level set
   *is* the constraint, that failure must never pass silently.
   **Second issue:** `n > 1` is `[f() for _ in range(n)]` — serial, one process-blocking call after
   another, no concurrency (while `batch_chat` in the neighbouring module has a `ThreadPoolExecutor`),
   no per-sample seed, and everything but the bare answer discarded.

**The important structural point:** LiteLLM — the backend `aix` already wraps — supports `n`,
`seed`, `temperature`, `top_p`, `logprobs`, `tools`/`tool_choice` and `response_format`, exposes
`get_supported_openai_params(model, custom_llm_provider)` so support can be probed rather than
assumed [8], and supports `response_format={"type": "json_schema", "json_schema": …, "strict": true}`
across OpenAI, Anthropic, Gemini, Vertex and Bedrock, accepts a Pydantic model directly as
`response_format`, offers `supports_response_schema(model)`, and can do client-side validation via
`enable_json_schema_validation` for models lacking native support [9]. **Every gap below is a facade
gap, not a capability gap** — which is what makes the fix small and makes fixing it in `aix` (rather
than wrapping around it in rubricator) obviously correct.

**Two more things in `aix` worth knowing.**

- `batch_chat(prompts, *, model, batch_size, max_workers, show_progress, **chat_kwargs)` is
  order-preserving over a `ThreadPoolExecutor`, but **swallows exceptions into the result string** as
  `f"ERROR: {str(e)}"`. An evaluation harness would silently record a rate-limit as a score.
- `aix.stores` is a stub — its own docstring says "TODO: Finish this module". It is an
  extension→text-decoder registry with only `txt` and `md` registered and a commented-out PDF hook.
  It is **not** a store layer; rubricator must not build corpus loading on it. Use `dol` / `graze` /
  `contaix` instead.

**The closest prior art in the whole ecosystem is `aix.vision.compare_images`.** It takes a rubric
of aspects and returns `ImageComparison(match, confidence, explanation, aspects, model)` where
`aspects` is a tuple of `RubricVerdict(aspect, match: bool, confidence: float, note: str)`, and the
container behaves as an ordered read-only mapping from aspect to verdict. Its docstring records the
same design choice rubricator's method brief reaches independently: *"The comparison is pointwise
(each aspect judged on its own), not a ranked pairwise comparison, to avoid position bias."* It
defaults `temperature=0.0` for a stable verdict. **REASONING:** this is the shape to learn from and
the shape to improve on — its verdicts are boolean rather than graded, its rubric aspects are bare
strings with no definitions, there are no evidence spans, and there is no `unknown`. Those four
deltas are, almost exactly, what ADR-0005 and ADR-0006 add.

### 5. `oa` — one idea to lift, no dependency to take

**EVIDENCE** (version 0.1.52; OpenAI-specific, the pre-LiteLLM generation; `aix`'s own notes
document `aix.prompts.constrained_answer` as a drop-in replacement for `oa.constrained_answer`).

`oa.tools.prompt_function(template, *, defaults, ..., prompt_func=chat, ingress, egress, ...)` is
the more sophisticated templating layer: it builds a real `i2.Sig` signature from the template
(named parameters, defaults from the `{var:default}` dialect, triple-backtick blocks excluded from
injection so example JSON can appear literally in a prompt), and **`prompt_func=None` returns a
function that renders the prompt string without calling any model**. That last property is exactly
the connector runtime's requirement: render, hand to the caller's model, never call one ourselves.
`oa.tools` also carries `make_generic_json_schema` / `_ensure_json_schema`, which accept a Python
type, a JSON-type name, a JSON string or a Mapping, and `oa.oa_types` bridges Pydantic models via
`ju`. `aix` has since absorbed the `{var:default}` dialect and the `egress` hook.

**Recommendation:** do not depend on `oa`. Lift the `prompt_func=None` idea into rubricator's own
prompt loader (rendering must be model-free by construction), and if it proves generally useful,
propose it to `aix` as `prompt_func(..., render_only=True)`.

### 6. Other local packages that are obviously relevant

- **`ju`** — JSON Schema Utils: `signature_to_json_schema`, `json_schema_to_signature`, and
  Pydantic helpers. Two uses. FastMCP already derives tool schemas from signatures, so that use is a
  fallback; the real use is the ADR-0002 boundary. **Caveat:** `ju` is schema *translation*, not
  validation — validating an emitted analysis against comparanda's published draft-2020-12 schema is
  a job for `jsonschema` itself.
- **`contaix`** — turns repos, documentation sites and file collections into clean markdown contexts
  for agents, and ships installable agent skills. This is the corpus-ingestion side of "point it at
  a folder of documents". **Caveat for ADR-0006:** it produces cleaned markdown, so rubricator must
  keep an offset mapping back to the original if spans are to be checkable in the source a reader
  actually opens. That is a real design constraint, not a footnote.
- **`aikb`** — `MutableMapping` CRUD over agent knowledge bases; the natural persistence shape for
  saved analyses, and it composes with `py2mcp.mk_mcp_from_store`.
- **`graze`** and **`dol`** — caching and store abstractions, already `aw_agents`' and the wider
  ecosystem's default.
- **`wads`** and **`reci`** — CI scaffolding and recipe-compiled workflows (see §7).
- Nothing in the local ecosystem does LLM-as-judge evaluation, calibration or agreement statistics.
  **REASONING:** that is rubricator's own ADR-0008 work, and if it generalises it is a candidate for
  extraction later — not a reason to look for an existing package now.

### 7. Project scaffolding — the ecosystem's Python conventions

**EVIDENCE** (read across a recent, well-formed package, plus `aix` and `py2mcp`, plus the
`setup-py-project` skill and the `wads` reusable CI workflow).

- **Build**: `hatchling`, `pyproject.toml` only — no `setup.py`, no `setup.cfg`. `requires-python =
  ">=3.10"`. SPDX `license = "MIT"` as the single source of truth (a duplicate `License ::`
  classifier is explicitly removed as redundant). `[project.urls]` with Homepage / Repository /
  Issues / Changelog / Documentation.
- **Layout**: package directory beside `pyproject.toml` at the repo root; `tests/` as a sibling, not
  nested inside the package; `misc/` for notebooks and working documents; `examples/` for runnable
  examples; `.claude/handoffs/` gitignored for session handoffs; `CHANGELOG.md` in Keep-a-Changelog
  form; `LICENSE`; `.editorconfig` from the `wads` scaffolding.
- **Lint/format**: `ruff` at `line-length = 88`, `target-version = "py310"`, `select = ["D100"]`
  (module docstrings enforced — matching the global instruction that every module needs one),
  `ignore = ["D203", "E501", "B905"]`, Google docstring convention, and per-file `D` ignores for
  `tests`, `examples`, `scrap`. `black` and `mypy` disabled by default in `[tool.wads.ci.quality]`.
- **Tests**: `pytest` with `testpaths = ["tests"]` and `doctest_optionflags = ["NORMALIZE_WHITESPACE",
  "ELLIPSIS"]`. Doctests in the package source are collected by the CI's `--doctest-modules`, so
  every public function carries an example — usually `# doctest: +SKIP` where it would need a
  network or a key. Unit tests mock the provider backend so the suite runs with no credentials. A
  root-level `conftest.py` is the convention when a setting must apply to *both* the `tests/` run and
  the `--doctest-modules` run, since a `conftest.py` only governs what is collected beneath it.
- **CI**: `.github/workflows/ci.yml` is a **thin stub** calling the reusable workflow
  `i2mint/wads/.github/workflows/uv-ci.yml@master` with `permissions: {contents: write, pages:
  write}` and explicitly listed secrets (not `secrets: inherit`, which does not reliably propagate
  across account boundaries). All actual configuration lives in `pyproject.toml` under
  `[tool.wads.ci.*]`: `testing.python_versions` (typically `["3.10", "3.12"]`), `pytest_args`,
  `coverage_*`, `exclude_paths`, `test_on_windows`, `quality.ruff|black|mypy`, `env.test_envvars`
  (how an API key reaches CI from secrets), `build.sdist|wheel`, `publish.enabled`, and
  `docs.builder = "epythet"`. Merging to the default branch bumps the version, publishes to PyPI and
  tags. Older repos still carry the full inline template — the stub is the current form.
- **Bootstrapping**: `wads.project_setup.setup_project(...)`, or the `setup-py-project` skill, which
  also handles name availability checks on PyPI and GitHub. `reci` compiles declarative CI recipes
  when the stub is not enough.

**REASONING:** rubricator should match this exactly, with three project-specific additions —
`[tool.wads.ci.env] test_envvars` left *empty* for the connector-only test suite (the whole point of
ADR-0003 is that it needs no key), a `[project.optional-dependencies] agent` extra carrying `aix`
so the connector install stays key-free and dependency-light, and prompt/schema content declared in
`[tool.hatch.build]` `include` so the prompt files ship in the wheel (they are content the runtime
serves, per ADR-0003, and a wheel without them is a broken server).

## What this means for the schema / the view / the agent

**Package layout.** Two extras, one package:

```
rubricator/
  __init__.py
  tools/          # deterministic tool functions — plain Python, no model calls, ever
  prompts/        # versioned .md content files (ADR-0005 stages) + a loader
  schema/         # the vendored comparanda JSON Schema + boundary validation
  mcp/            # server assembly (see below)
  agent/          # deployed runtime — imports aix; NOT imported by mcp/
```

`pip install rubricator` gives the connector with no LLM dependency;
`pip install "rubricator[agent]"` adds `aix`. **The `mcp/` package must never import `agent/`** —
that import is the mechanical enforcement of ADR-0003's "no tool may require a model", and it should
be asserted by a test in the shape of `aix`'s hermetic-import test: run
`python -c "import rubricator.mcp"` in a subprocess and assert `litellm` and `aix` are absent from
`sys.modules`.

**Server assembly.** One function, `rubricator.mcp.build_server() -> FastMCP`:

```
server = py2mcp.mk_mcp_server(
    TOOLS,                       # the deterministic tool functions of Phase 1
    name="rubricator",
    instructions=HONESTY_RULE,   # ADR-0006, at the server level
    middleware=[AnalysisAudit()],# per-run log; no tool has to remember to record itself
)
for spec in load_prompts():      # ADR-0005 stages, from prompts/*.md
    server.prompt(spec.render, name=spec.name, description=spec.description)
server.add_resource(TextResource(uri="rubricator://schema/analysis.json", ...))
server.add_resource(TextResource(uri="rubricator://method/criteria-hygiene.md", ...))
```

Run it with `py2mcp.serve_stdio` for Claude Desktop and Claude Code; later, `py2mcp.mk_http_app`
with a JWT `auth` config for a hosted connector. Both transports come free.

**Prompt loading must be model-free by construction.** `load_prompts()` returns objects whose
`render(**kwargs) -> str` performs template substitution only — the `oa` `prompt_func=None`
property, lifted. A prompt that could reach a model is a prompt that breaks the connector.

**Validation at the boundary, deterministically.** `rubricator.schema.validate_analysis(obj) ->
ValidationReport` uses `jsonschema` against comparanda's published schema (ADR-0002), and is exposed
as an MCP tool so the caller's model can check its own draft before emitting it. `ju` is for
signature↔schema translation, not for this.

**The `constrained_answer` membership defect is rubricator's problem too.** Anchored criterion
levels are exactly the "valid answers" case, and a level outside the anchored set must be a hard
error, never a silent pass-through. Until `aix` fixes it (issue A3 below), rubricator's
`score_cell` path must re-check membership itself.

**ADR-0008 stability work needs a sampling primitive that does not exist yet.** The target shape:

```
sample_scores(prompt, *, n, temperature, seed=None, model=None) -> list[Sample]
```

where each `Sample` carries the parsed payload, the raw text, `finish_reason` and `usage`, and the
call is concurrent. Today the ecosystem's nearest match is the documented polling idiom —
`Pipe(partial(constrained_answer, n=10), Counter)` — which is serial, discards justifications, and
cannot report cost. Build `sample_scores` in `aix` (issue A2), not in rubricator.

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0004 | **amend** | Python confirmed; `aw_agents` rejected for v1 — its MCP adapter wires only `list_tools`/`call_tool` and cannot serve the prompts and resources ADR-0003 requires. Build on `py2mcp`/FastMCP. |
| ADR-0003 | confirm | Its central mechanism is now verified end to end: MCP prompts surface as `/mcp__server__prompt` slash commands and resources as `@server:uri` mentions in Claude Code [4]. |
| ADR-0007 | **amend** | Items 1 and 2 collapse into one artifact: serving prompts *is* the prompt bundle. The sequence stands; the item count does not. |
| ADR-0002 | confirm | `jsonschema` + a vendored published schema is the mechanism; no change to the decision. |
| ADR-0008 | confirm | Unchanged as a decision, but blocked on the `aix` gaps below; note the dependency in the implementation plan rather than in the ADR. |
| — | **new ADR** | "All LLM access goes through `aix`" — the repository owner's standing rule, currently written down nowhere in this repo, and the rule that makes the `mcp/`-must-not-import-`agent/` test meaningful. |

### Draft replacement Decision section for ADR-0004

> ## Decision
>
> **Python for the agent runtime.** Confirmed. The schema tooling, the LLM facade, the MCP builder
> and every project convention are already Python; a JS/TS runtime would share a language with the
> UI and nothing else.
>
> **The MCP surface is a standalone FastMCP server, built with `py2mcp`.** Not `aw_agents`. Reading
> `aw_agents` settled the fork this ADR posed: its MCP adapter registers exactly two handlers,
> `list_tools` and `call_tool`, over the low-level MCP SDK server, and offers no seam for
> `prompts/list`, `prompts/get`, `resources/list` or `resources/read`. ADR-0003 requires prompts to
> ship as content the runtime serves; that requirement is unsatisfiable on `aw_agents` without
> forking its adapter. Its tool responses are additionally stringified into human-readable text
> rather than structured content, its OpenAPI adapter drops nested input sub-schemas, its adapters
> carry no tests, and it provides no model access, loop, session or streaming — so it does not
> supply the "deployed agent owning its own model access" this ADR assumed either.
>
> `py2mcp` returns a live `FastMCP` object, so `mk_mcp_server(...)` supplies the tools and prompts
> and resources are registered on the returned server. It ships stdio serving for Claude Desktop and
> Claude Code and Streamable HTTP with OAuth 2.1 resource-server authentication for a hosted
> connector, plus a middleware seam for per-run auditing. Contribute `prompts=` and `resources=`
> kwargs upstream to `py2mcp` so the assembly is declarative.
>
> **All LLM access goes through `aix`, never a raw provider SDK.** The deployed agent (`agent/`)
> owns that dependency; the MCP layer (`mcp/`) must not import it, and a test asserts so. `aix`
> needs the gaps in the Phase 0 research filed and closed before ADR-0008's variance work is
> possible; those are `aix` issues, not rubricator code.
>
> **`aw_agents` is not rejected forever.** If a ChatGPT Custom GPT or another non-MCP chatbot
> surface is ever wanted, `aw_agents`' `OpenAPIAdapter` becomes a candidate — it would consume the
> same tool functions. That is a v2 question, and it needs the nested-sub-schema flattening fixed
> first.
>
> **No JS/TS agent runtime in v1.** Unchanged. File an issue; revisit only for a concrete deployment
> target. Reserve the npm name.

## The `aix` gap list — ready to become issues

Each is a facade gap; LiteLLM already supports the underlying capability [8][9].

**A1 — `chat()` discards the response.** Add a sibling that returns the whole thing rather than
changing `chat()`'s contract: `complete(prompt, *, model, temperature, max_tokens, n, seed,
response_format, api_key, **kwargs) -> Completion`, where `Completion` carries `texts:
list[str]` (all `n` choices, not just choice 0), `usage`, `finish_reasons`, `model`, and the raw
response. *Why it blocks rubricator:* ADR-0008's stability metric needs the n samples that are
currently paid for and thrown away, and cost-per-analysis reporting needs `usage`.

**A2 — no sampling primitive.** `sample(prompt, *, n, temperature, seed=None, concurrency=None,
model=None) -> list[Sample]`, concurrent (the `ThreadPoolExecutor` in `batches.py` is the model),
each `Sample` carrying the parsed payload, the raw text, `finish_reason` and `usage`. Prefer
provider-side `n` where `get_supported_openai_params` reports support, and fall back to concurrent
independent calls otherwise. *Why:* ADR-0008 stability and any agreement statistic. Today
`constrained_answer(n=10)` is ten blocking serial calls returning ten bare answers.

**A3 — `constrained_answer` does not enforce its constraint.** The answer is type-coerced but never
checked for membership in `valid_answers`, and a `(min, max)` range is never bounds-checked, so an
out-of-set reply is returned as valid. Add validation with a bounded retry and a
`ConstraintViolation` error on exhaustion. *Why:* anchored criterion levels are precisely this case,
and a silent out-of-set score is the worst kind of failure for a tool whose product claim is honesty.

**A4 — no provider-enforced structured output.** `prompt_func(output_schema=...)` appends the schema
to the prompt and `json.loads` the reply; the schema is flat (no nested objects, no arrays of
objects, no enums, no required/optional), and the parsed object is never validated against it. Add
`response_schema=` accepting a JSON Schema dict or a Pydantic model, routed to
`response_format={"type": "json_schema", "strict": true}` where `supports_response_schema(model)` is
true, falling back to JSON mode plus client-side validation and a bounded repair retry. *Why:* a
scored cell is a nested object with a list of evidence spans — not expressible today.

**A5 — `seed` and determinism are undocumented.** Promote `seed` to a named keyword-only parameter
on the new `complete`/`sample`, document that support is provider-dependent, and expose a
`supports(model, param)` helper over `get_supported_openai_params` so a caller can degrade
deliberately rather than discover silently. *Why:* ADR-0008 must distinguish "the model is unstable"
from "the provider ignored our seed".

**A6 — `batch_chat` swallows exceptions.** Errors become the string `f"ERROR: {str(e)}"` in the results
list. Add `on_error: 'raise' | 'return' | 'skip'` (default `'raise'`), with `'return'` yielding a
typed error object rather than a string. *Why:* an evaluation harness would otherwise silently score
a rate-limit.

**Bonus, in `py2mcp` rather than `aix`:** add `prompts=` and `resources=` kwargs to the builders,
mirroring the existing `middleware=` and `instructions=` kwargs, so a prompts-and-resources server
is declarative rather than assembled by hand.

## Open questions

- **Does `aix` want these changes, or does rubricator wrap?** The gaps are small and clearly belong
  in the facade, and the owner's rule points to `aix`. But `complete()` alongside `chat()` widens the
  API surface, and `aix` has so far kept `chat()` deliberately narrow. **Settled by:** filing A1 and
  A2 and getting a maintainer's call on the shape before writing rubricator's `agent/`.
- **Does Claude Desktop surface MCP prompts and resources the same way Claude Code does?** The Claude
  Code reference documents both mechanisms precisely [4]; I did not verify the Desktop client's
  behaviour and will not assert it. **Settled by:** installing the connector in Desktop once the
  first prompts exist — a ten-minute check that should happen in Phase 3, not be assumed in Phase 1.
- **Span offsets through `contaix`.** If corpus ingestion cleans documents into markdown, character
  ranges index the *cleaned* text, and a citation nobody can check in the original is exactly what
  ADR-0006 forbids. **Settled by:** deciding early whether rubricator cites into a normalized,
  persisted rendition (and ships it as an MCP resource so the span is resolvable) or maintains an
  offset map back to the source. This is a Phase 1 schema decision, not a Phase 3 detail.
- **Is elicitation the right home for ADR-0005's step-4 confirmation checkpoint?** Claude Code
  supports it with no configuration [4], and it would make the checkpoint structural rather than
  conversational. But it binds the checkpoint to clients that implement it, and a checkpoint that
  silently vanishes on a client that does not is worse than a conversational one. **Settled by:**
  building the prompt-driven checkpoint first and measuring whether it actually gets skipped.
- **Whether `py2mcp` remains version-stable.** It pins `fastmcp` unbounded, and the installed
  `fastmcp` is a 3.x release; the combination works today (verified), but rubricator should pin a
  `fastmcp` floor and watch for FastMCP 3.x API drift.

## REFERENCES

1. [Model Context Protocol Specification (2025-06-18) — Server Features: Prompts](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts)
2. [Model Context Protocol Specification (2025-06-18) — Server Features: Resources](https://modelcontextprotocol.io/specification/2025-06-18/server/resources)
3. [Model Context Protocol Specification (2025-06-18) — Client Features: Sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
4. [Connect Claude Code to tools via MCP — Anthropic Claude Code documentation](https://code.claude.com/docs/en/mcp)
5. [FastMCP — Prompts](https://gofastmcp.com/servers/prompts)
6. [FastMCP — Resources & Templates](https://gofastmcp.com/servers/resources)
7. [FastMCP — Middleware](https://gofastmcp.com/servers/middleware)
8. [LiteLLM — Input Params for completion()](https://docs.litellm.ai/docs/completion/input)
9. [LiteLLM — JSON Mode and Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode)
10. [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol/python-sdk)
11. [RFC 8707: Resource Indicators for OAuth 2.0 — Campbell, Bradley & Tschofenig (2020)](https://www.rfc-editor.org/rfc/rfc8707.html)
12. [RFC 9728: OAuth 2.0 Protected Resource Metadata — Jones, Hunt & Parecki (2025)](https://www.rfc-editor.org/rfc/rfc9728.html)
