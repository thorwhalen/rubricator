# MCP server design, tool granularity, prompts-as-content, and human-in-the-loop across sessions

**Research question(s):** What does the current MCP specification actually offer (tools, prompts,
resources, resource templates, sampling, roots, elicitation, transports), and which of those are the
right vehicles for `rubricator`? How granular should the tool surface be, and what is the evidence?
When should the agent put a corpus in context versus retrieve from it? How does a
human-in-the-loop checkpoint survive a session boundary? Which local package should the MCP server
be built on? Deliverable: a proposed MCP tool surface, plus the prompts and resources list.

**Brief section:** `docs/research/method.md` §5, *Agent architecture*. Produces BRIEF.md Phase 1
("the core artifact of the whole project") and part of Phase 0's `aw_agents` reading.

**Evidence grade:** strong — the protocol claims are read from the current specification revision
rather than from summaries; the tool-count and token-cost claims come from first-party vendor
documentation and one peer-reviewable preprint; the cost crossover is arithmetic over published
list prices. The weakest part is client feature support, where the community matrix covers only
extensions and the core-feature matrix has been withdrawn from the docs site (see Open questions).

---

## Bottom line

Build the MCP surface on the **official MCP Python SDK v2 / FastMCP 4** — not on the local
`py2mcp`, and not on the local `aw_agents`, neither of which can serve prompts, resources, or
elicitation. **MCP prompts are exactly the right vehicle for ADR-0003's "prompts are content"** —
they are user-selected (surfaced as slash commands), take arguments, and can embed resources in the
messages they return, so `propose-criteria` can ship the method text *and* the current analysis
state in one `prompts/get`. **MCP sampling is not an escape hatch and must not be used: it was
deprecated in the 2026-07-28 revision**, with the stated migration path "integrate directly with LLM
provider APIs" [2]. That settles the question ADR-0003 left implicit — the determinism rule holds,
and it should be extended to forbid embedding models too, since an embedding call is a model call
and would break the key-less connector. **Elicitation is the right mechanism for ADR-0005's step-4
checkpoint**, but it is a *client* capability that may be absent, so `frame_confirm` must have a
documented degraded path that asks the user in chat and records the answer. Ship **15 tools**, of
which **10 are the minimum viable set** — comfortably under the 30–50-tool threshold at which
Anthropic reports tool-selection accuracy degrading [12]. Retrieve from the corpus by default and
put it in context only under roughly 20k–40k tokens (arithmetic below), because in the connector
runtime `rubricator` controls neither the cache nor the context budget. Finally, **durable
cross-session state is not something MCP gives you** — neither `requestState` nor a Tasks `taskId`
survives "the user comes back tomorrow in a new chat" — so `rubricator` must own a store whose
record *is* a partial comparanda analysis, using `not-assessed` / `pending` exactly as
comparanda's ADR-0009 intends.

---

## Findings

### 1. What the current MCP specification actually offers (revision `2026-07-28`)

EVIDENCE. The current revision is **`2026-07-28`** [1][10]. It is not a minor increment on the
2025 revisions; several things an implementer might remember are gone or deprecated.

| Feature | Status in `2026-07-28` | Relevance here |
|---|---|---|
| **Tools** | Core, server feature, *model-controlled* [6] | The whole deterministic surface |
| **Prompts** | Core, server feature, *user-controlled*, typically surfaced as slash commands [5] | The ADR-0003 vehicle |
| **Resources** + **resource templates** | Core, server feature, *application-driven* [7] | Schema, method text, analysis documents, span deep-links |
| **Elicitation** | Core, and now the **only** client feature the overview lists [1][4] | ADR-0005 step 4 |
| **Sampling** | **Deprecated** as of `2026-07-28` [2] | Do not use — see §2 |
| **Roots** | **Deprecated** as of `2026-07-28`; migrate to tool parameters / resource URIs / server config [2][11] | Pass the corpus path as a tool argument |
| **Logging** (`notifications/message`) | **Deprecated**; log to stderr, use OpenTelemetry [2] | Do not build on it |
| **HTTP+SSE transport** (2024-11-05) | **Deprecated** since `2025-03-26`, formally classified Deprecated by SEP-2596 [2][8] | Never implement it |
| **Streamable HTTP** | The remote transport. In `2026-07-28` the **GET stream endpoint and protocol-level sessions were removed** [8] | Affects any hosted deployment |
| **stdio** | Unchanged, still the local transport | The connector's default |
| **Tasks** (extension) | Opt-in extension: durable `taskId`, `working`/`input_required`/`completed`/`failed`/`cancelled`, `tasks/get`, `tasks/update`, `tasks/cancel` [9] | Useful for long populate runs; *not* a cross-session store |
| **MCP Apps**, **Skills over MCP** | Extensions [1] | Out of scope for v1 |

Three structural changes matter to the design:

**(a) The protocol is now stateless and per-request.** There is no `initialize` handshake; every
request carries `_meta.io.modelcontextprotocol/protocolVersion`, `clientInfo` and
`clientCapabilities`, and a mandatory `server/discover` RPC returns capabilities and supported
versions [10]. The tools spec adds a non-normative **"Stateful Tools"** section stating plainly
that "MCP has no protocol-level session, so a server cannot rely on implicit per-connection state",
and prescribing the pattern `rubricator` needs: return an **explicit opaque handle** from a creation
tool and accept it as an argument on later calls, with authorization checked per call, a bounded
lifetime *stated in the creation tool's description*, and an expiry error the model can recover
from [6]. That is the `analysis_id` contract, endorsed by the spec.

**(b) Server-to-client requests are gone; MRTR replaces them.** A server no longer sends
`elicitation/create` / `sampling/createMessage` / `roots/list` as its own JSON-RPC requests. It
returns an **`InputRequiredResult`** (`resultType: "input_required"`) carrying an `inputRequests`
map and an opaque `requestState` blob; the client gathers the input and **retries the original
request** with `inputResponses` and the echoed `requestState`, under a *new* JSON-RPC id [3]. This
is explicitly a breaking change. Consequences for us:

- `requestState` is attacker-controlled and must be integrity-protected (HMAC/AEAD), bound to the
  authenticated principal, short-TTL, and bound to a digest of the originating request's salient
  parameters [3]. If we put anything meaningful in it, we inherit that whole checklist.
- The server **MUST NOT** send an `inputRequests` entry for a capability the client did not
  declare, and **MUST NOT** assume the client will ever retry [3].
- `InputRequiredResult` is permitted on exactly three methods: `tools/call`, `prompts/get`,
  `resources/read` [3].

REASONING (not evidence): the cheapest correct posture for `rubricator` is to keep `requestState`
empty or to a single opaque `analysis_id` reference, and to keep the *real* state in our own store
keyed by that id. Then the integrity requirements collapse to "the id is a random opaque token with
a bounded lifetime", which the Stateful Tools guidance already asks for.

**(c) Elicitation has two modes and a strict schema subset.** `form` mode takes a `requestedSchema`
restricted to a **flat object of primitives** — string (with `email`/`uri`/`date`/`date-time`
formats), number/integer, boolean, single-select enum (`enum` or `oneOf` with `const`+`title`), and
multi-select (`array` of enum). "Complex nested structures, arrays of objects (beyond enums), and
other advanced JSON Schema features are intentionally not supported" [4]. `url` mode is for
sensitive out-of-band interactions and is not relevant here. Responses carry
`action: accept | decline | cancel`, and servers **MUST** handle decline and cancel [4].

REASONING: this schema restriction is a hard constraint on the ADR-0005 checkpoint. You **cannot**
elicit "here are 7 proposed criteria, edit their definitions" as a structured form. What you *can*
elicit is a flat confirmation: a free-text `notes` string, a boolean per named criterion (or a
multi-select of "which of these criteria do you want to drop"), and an enum
`approve | approve-with-notes | revise`. The rich discussion — the part ADR-0005 says is the
valuable part — belongs in the **chat turn driven by a prompt**, and the elicitation is the *record
of the decision*, not the venue for the decision. That is a better design anyway: it keeps the
argument in the transcript where the user can see it.

### 2. Sampling: not an escape hatch. Settled.

EVIDENCE. Sampling (`sampling/createMessage` — the server asking the *client's* model to complete
something) is listed in the deprecated-features registry with deprecation SEP-2577, deprecated in
`2026-07-28`, migration path **"Integrate directly with LLM provider APIs"**, earliest removal
"first revision released on or after 2027-07-28" [2]. New implementations **SHOULD NOT** adopt it
[2]. It still appears in MRTR examples because MRTR must carry it during the deprecation window
[3], which is easy to mistake for endorsement.

This closes the question the brief raised. Even setting deprecation aside, sampling would have been
the wrong call for `rubricator` on three counts (REASONING):

1. **It breaks the determinism contract in the place it matters most.** ADR-0003's rule is not
   "the server must not hold an API key" — it is "tools are deterministic, the loop is not." A
   `score_column` tool that internally sampled the client's model would be a tool whose output is
   not reproducible, not testable by ADR-0008's stability check, and not auditable. The key-less
   property would be preserved; the *product* property would be destroyed.
2. **It hides the judgement from the user.** The whole ADR-0006 posture — mark authorship, mark
   source type, prefer a qualified blank — depends on the user being able to see the reasoning that
   produced a score. A sampled completion inside a tool call is invisible in the transcript.
3. **Client support was always thin**, and a feature on a removal clock will get thinner.

**Recommendation:** an explicit ADR that forbids sampling *and* forbids in-tool embedding calls.
An embedding model is a model. If `corpus_search` used embeddings it would need either a key (no
connector) or a bundled local model (a heavy, non-deterministic dependency whose version silently
changes results between runs). Lexical retrieval — BM25 plus exact/normalized substring matching —
is deterministic, key-less, dependency-light, and is *sufficient* here because the model is doing
the semantic work in its own loop and can issue several queries.

### 3. Prompts are the right vehicle for ADR-0003 — and better than expected

EVIDENCE [5]:

- Prompts are **user-controlled**: "exposed from servers to clients with the intention of the user
  being able to explicitly select them", typically as slash commands. The spec's own screenshot is
  a slash-command menu.
- A prompt definition is `{name, title?, description?, icons?, arguments?}`; each argument is
  `{name, description?, required?}` — **there is no type**. On the wire, `prompts/get` takes
  `arguments` as a flat string map.
- `prompts/get` returns `messages: [{role, content}]` where content may be `text`, `image`,
  `audio`, **`resource_link`**, or an **embedded `resource`** (uri + mimeType + text/blob).
- Argument values can be auto-completed via the completion API; `listChanged` notifications exist.
- `prompts/get` may itself return an `InputRequiredResult` [3][5].

REASONING — why this is the right fit, and the two design consequences:

*Consequence 1: arguments are strings, so pass handles, not payloads.* Every `rubricator` prompt
takes `analysis_id` (a string) and optional string knobs. The prompt body then **embeds** the
relevant state as a resource content block. So `propose-criteria(analysis_id)` returns: (i) a text
message containing the elicitation method and the ADR-0006 honesty rule, (ii) an embedded
`rubricator://analysis/{id}` resource carrying the confirmed frame and the alternatives, (iii) an
embedded `rubricator://method` resource, and (iv) a `resource_link` to the corpus index. That is
exactly "prompts ship as content the runtime can serve", and it means the prompt files stay
versioned markdown on disk with a thin assembler in front of them.

*Consequence 2: prompt count does not degrade tool selection.* Prompts are not in the model's tool
list — the user picks them. So the count discipline that governs tools (§4) does not apply. Ten
prompts is fine.

**FastMCP supports prompts natively** via `@mcp.prompt`, with argument descriptions extracted from
docstrings, `version` support from v3.0.0+, and icons from v2.13.0+ [18]. The official Python SDK v2
also exposes tools, resources (including templated resources) and prompts, and implements the
`2026-07-28` specification and every earlier revision [20].

### 4. Tool granularity: how many, how chunky, and what it costs

#### The measured evidence

EVIDENCE, first-party and quantified. Anthropic's tool-search documentation states plainly:
"Claude's ability to pick the right tool degrades once you exceed **30–50 available tools**", and
that a typical five-server MCP setup "can consume **~55k tokens** in definitions before Claude does
any work" [12]. Its "when to use tool search" guidance sets the other end of the range: use it at
**10 or more tools** or when definitions exceed **10k tokens**; standard tool calling is a better
fit "when you have fewer than 10 tools, every tool is used in every request, or your tool
definitions are small (less than 100 tokens total)" [12]. Tool definitions are billed as ordinary
input tokens, and a tool-use system prompt of 286–406 tokens (Opus 5) is added whenever any tool is
present [22].

EVIDENCE, independent. Gan & Sun's *RAG-MCP* (2025) [15] ran a stress test that varies the number
of candidate MCP servers `N` "from 1 to 11100 in 26 intervals" (one ground-truth server, `N−1`
distractors drawn from a registry of "over 4,400 publicly listed servers"). Reading their Figure 3,
they report three bands *by the position of the ground-truth server*: "MCP positions below 30
exhibit predominantly yellow regions, indicating success rates above 90%"; "in the range of
positions 31–70, clusters of purple emerge intermittently, reflecting lower accuracy as semantic
overlap among MCP descriptions increases"; and "beyond position ~100, purple dominates". Their main
comparison (qwen-max-0125 as base LLM, 20 independent trials, web-search subset of MCPBench)
reports 13.62% accuracy for the naive all-tools-in-prompt baseline ("Blank") against 43.13% with
retrieval, with average prompt tokens falling from 2,133.84 to 1,084.00. Caveats worth stating: one
model family, one benchmark subset, absolute numbers low across the board, the bands are read off a
heatmap rather than tabulated, and the stated maximum `N` (11,100) exceeds the registry size the
paper itself quotes. Treat the *shape* of the curve as transferable and the *levels* as not.

EVIDENCE, on the cost of the list itself. Anthropic's code-execution-with-MCP post reports a
workflow whose upfront tool definitions consumed ~150,000 tokens, reduced to ~2,000 tokens (a 98.7%
reduction) by loading definitions on demand [14].

#### The design rules that fall out

EVIDENCE from Anthropic's tool-authoring guidance [13]: consolidate rather than mirror an API
("more tools don't always lead to better outcomes"); prefer one `schedule_event` over
`list_users` + `list_events` + `create_event`; namespace by prefix (`asana_search`,
`asana_projects_search`) while noting effects vary by model; build in pagination/filtering/
truncation with sensible defaults (Claude Code caps tool responses at **25,000 tokens** by
default); write descriptions as if onboarding a new colleague and name parameters unambiguously
(`user_id`, not `user`); offer an optional `response_format` enum so the agent can ask for concise
or detailed output — their example shrinks a Slack response from 206 to 72 tokens.

EVIDENCE from the spec on error conventions [6]: two mechanisms, and the split matters. **Protocol
errors** (unknown tool, malformed request) are JSON-RPC errors and "models are less likely to be
able to fix" them. **Tool execution errors** — API failures, input validation, business-logic
failures — go in the result with `isError: true`, because clients **SHOULD** feed them to the model
"to enable self-correction". The spec's own example is instructive: *"Invalid departure date: must
be in the future. Current date is 08/08/2025."* — the error carries the fact needed to fix it.

EVIDENCE from real servers. Playwright MCP documents 69 distinct `browser_*` tools at
one-tool-per-action granularity (`browser_click`, `browser_hover`, `browser_type`, `browser_drag`),
returns state as structured accessibility snapshots rather than screenshots ("uses Playwright's
accessibility tree, not pixel-based input"), and annotates every tool with a read-only flag [16].
The GitHub MCP server takes the opposite route: ~21 toolsets for the local server (23 counting the
two remote-only ones) that users enable selectively, because doing so "can help the LLM with tool
choice and reduce the context size" [17].

REASONING — but note the contrast is weaker than it first looks. Playwright's 69 tools *do* fall
into obvious prefix families (`browser_cookie_*`, `browser_localstorage_*`,
`browser_sessionstorage_*`, `browser_mouse_*`, `browser_network_*`, `browser_verify_*`,
`browser_video_*`), so this is not a domain that resists grouping; it is a project that chose flat
per-action tools anyway. The transferable lesson is therefore about the *choice*, not about
necessity: a flat surface is viable when each tool is a genuinely primitive action the model
invokes directly, and a grouped/toggleable surface is preferable when the count runs to hundreds.

#### What this means for rubricator (REASONING)

`rubricator` sits in the comfortable zone: a single coherent domain with roughly a dozen genuinely
distinct deterministic operations. That means:

- **Stay under 20 tools, and tool search should not be needed.** With 15 tools at ~200 tokens of
  schema each, the list costs roughly 3k tokens plus the ~300-token tool-use system prompt — well
  under the 10k-token threshold at which deferred loading starts to pay [12][22]. Note this is a
  judgement call against one of [12]'s own criteria, not a clean pass: Anthropic lists "10 or more
  tools" as a trigger for tool search, and 15 clears it. The argument for ignoring that trigger is
  the other two clauses — the definitions are far under 10k tokens and 15 is far under the 30–50
  band where selection accuracy degrades. Measure it with `count_tokens` rather than trusting the
  estimate, and revisit if the surface grows.
- **Chunky where the matrix is, chatty nowhere.** The one place `rubricator` could accidentally
  become chatty is cell writes: 8 alternatives × 7 criteria is 56 tool calls if the tool takes one
  cell. `measures_write` therefore takes a **list** of cells, so the model can write a whole column
  in one call.
- **Separate the generation granularity from the write granularity.** The sibling research in this
  repo ([*Does Scoring Order Change Multi-Criteria Evaluations*](../scoring-order-effects.md)) recommends isolating each judgement
  — one criterion per generation — on the strength of Stureborg et al.'s finding that scoring
  multiple attributes in one generation inflates inter-attribute correlation from a human r ≈ 0.32
  to r ≈ 0.98 [24]. That is a constraint on how the **prompt** asks the model to reason, not on how
  many cells a **tool call** may carry. The prompt says "reason one cell at a time"; the tool
  accepts the batch. Nothing forces these to match, and conflating them would cost 56 round trips
  for no benefit.
- **Noun-first prefixes, no server prefix.** Clients already namespace by server (Claude Code
  renders `mcp__rubricator__<name>`), so a `rubricator_` prefix is redundant. Group instead by the
  domain noun — `analysis_*`, `corpus_*`, `frame_*`, `alternatives_*`, `criteria_*`, `measures_*`,
  `report_*` — which gives the same one-search-matches-the-group property [12] and makes the
  pipeline stages legible in the tool list itself.
- **Use `outputSchema` + `structuredContent` on every tool** [6]. Clients SHOULD validate against
  it, and it is free documentation for the model. Return the human-readable summary in `content`
  and the machine payload in `structuredContent`.
- **Use `resource_link` instead of dumping documents.** `analysis_export` and `corpus_read` return
  links the client can fetch, not 40k-token blobs.

### 5. Resources versus returning data from tools

EVIDENCE [7]: resources are **application-driven** — "host applications determin[e] how to
incorporate context", typically via a picker UI. Tools are **model-controlled** [6]. Resources
support URI templates (RFC 6570), pagination, caching (`ttlMs`, `cacheScope`), subscriptions, and
`annotations` (`audience: ["user"|"assistant"]`, `priority: 0.0–1.0`, `lastModified`).

REASONING — the rule to apply: **if the model decides to fetch it, it is a tool; if the user or the
host decides to surface it, it is a resource.** Some things are both, and that is fine: expose the
analysis document as `rubricator://analysis/{id}` so the user can pin it into context and so
comparanda's `EvidenceResolver` can resolve against it, *and* expose `analysis_get` so the model can
read a projection of it mid-loop without the user doing anything.

The `annotations.audience` field earns its keep here: `rubricator://method` and
`rubricator://confidence-rubric` are `["assistant"]` at high priority (the model should always have
them); `rubricator://analysis/{id}/span/{span_id}` is `["user"]` (a human checks the citation).

### 6. Long context versus retrieval, in 2026 prices

EVIDENCE [22]. Claude Opus 5: $5/MTok input, $25/MTok output, 1M-token context. Prompt caching
multipliers: 5-minute write 1.25×, 1-hour write 2×, cache read 0.1× ($0.50/MTok on Opus 5).
Critically, **there is no long-context surcharge any more**: "Claude 4.6 and later models … include
the full 1M token context window at standard pricing. (A 900k-token request is billed at the same
per-token rate as a 9k-token request.)" [22]. That removes the 2025-era pricing cliff that used to
make the decision for you.

REASONING — the arithmetic. Let `N` be corpus tokens and `C` the number of scoring calls.

- **Whole corpus in a 1-hour-cached prefix:** `N/1e6 × ($10 + (C−1) × $0.50)`
- **Retrieval:** ~5k tokens of retrieved spans per call at $5/MTok = **$0.025 per call**, so
  `C × $0.025`. Deterministic indexing is free.

| Traversal | C | Crossover N |
|---|---|---|
| Column-wise, 10 criteria | 10 | ≈ 17,000 tokens |
| Cell-wise, 10 alternatives × 6 criteria | 60 | ≈ 38,000 tokens |
| **Uncached** long context (any C) | any | ≈ 5,000 tokens |

**The crossover is roughly 20k–40k corpus tokens when you control caching, and roughly 5k when you
do not.** And in the connector runtime `rubricator` controls nothing: the host owns the cache
breakpoints, the host owns the context budget, and Claude Code truncates tool responses at 25,000
tokens by default [13]. So:

**Recommendation.** Always build the span index — you need it for citations regardless, and
ADR-0006 says a citation that points at a whole document is not a citation. Retrieve by default.
Put the corpus wholesale into context only when `corpus_add` reports the total under ~25k tokens
*and* the stage is enumeration (proposing alternatives or criteria), where global recall matters
more than precision. Implement this as a single documented behaviour: `corpus_search` with an empty
query returns the whole corpus when it is under the threshold, and refuses with an actionable
`isError` message above it. One tool, two regimes, no branching in the model's head.

Two quality caveats worth carrying (both from the sibling research brief in this repo, which cites
the primary sources): long-context recall is U-shaped — material in the middle of a long prompt is
attended to less well [23] — and LLM judges assimilate toward earlier judgements in the same
generation [24]. Both push the same way: retrieve a small, ordered, relevant set per judgement
rather than relying on the model to find the right passage in a wall of text.

### 7. Human-in-the-loop checkpointing that survives a session boundary

The brief asks the right question, and the answer is: **MCP does not solve this, and neither does
any of its extensions.** Three mechanisms look like they might, and each falls short:

| Mechanism | Lifetime | Why it is not enough |
|---|---|---|
| MRTR `requestState` | One request/retry pair; spec urges a **short TTL** and request-digest binding [3] | Dies with the request. By design. |
| Tasks `taskId` | Durable across disconnects and client restarts; clients are told to "store task IDs durably so polling can resume after a client crash or restart" [9] | Scoped to one operation, and the *client* holds the id. A new chat session has no idea it exists. |
| Prompt caching | 5 minutes or 1 hour [22] | A cost optimisation, not state. |

EVIDENCE from a well-trodden comparable: LangGraph's persistence model separates a **checkpointer**
(graph state snapshots scoped to a `thread_id`, enabling interrupt/resume and time travel) from a
**store** (durable information across threads), and is explicit that in-memory checkpointers lose
everything on process restart — cross-session resume requires a real database backend [21]. The
generalisable shape is: *a stable id the caller can name later, plus a durable record keyed by it,
plus an explicit resume entry point.*

**Recommendation for `rubricator` (REASONING).**

1. **The state record IS a partial comparanda analysis.** Not a bespoke checkpoint format that must
   later be converted. comparanda's ADR-0009 already defines the closed missingness set
   (`not-applicable`, `not-assessed`, `pending`, `unknown`, `withheld`) and requires that "an agent
   can be instructed to leave cells blank with a reason", with the resulting document "valid and
   complete-as-specified rather than half-broken". That is precisely a resumable checkpoint. A
   half-finished analysis is a *finished document about an unfinished analysis*.
2. **Semantics on resume, straight from the code set.** `not-assessed` = nobody has looked (the
   default for a new cell); `pending` = deliberately deferred by instruction; `unknown` = someone
   looked and could not determine. A resuming session calls `analysis_get(view="pending")` and knows
   exactly what remains, and — crucially — knows the difference between "not done" and "done, and
   the answer is that we cannot tell", which is the ADR-0006 distinction the whole product rests on.
3. **The checkpoint decision is provenance, not a flag.** Record the step-4 confirmation as an
   authored, timestamped assertion on the analysis (who confirmed, when, what text, whether it came
   through elicitation or through chat). A new session reads it and does not re-ask. This also
   means the confirmation is *auditable*, which matters more than it sounds: "the criteria were
   confirmed by a human on this date" is part of what makes the analysis defensible.
4. **The store lives in the platform user-data directory, never inside the package.** Keyed by
   `analysis_id`, one record per analysis plus a corpus-index sidecar. A `dol`-style Mapping
   interface so it can be a directory of JSON files today and object storage later without touching
   the tool implementations.
5. **Expose resumption three ways**, because the user may arrive by any of them: the
   `rubricator://analyses` resource (the host can list in-progress work), `analysis_open` with an
   existing id, and a `resume` prompt that reads the state and narrates what is left.
6. **Use the Tasks extension only for long populate runs inside one session** — it gives progress
   visibility and `input_required` mid-flight, both genuinely useful — and treat it as strictly
   optional, since support is per-client [9].

### 8. Local ecosystem read: what to build on, and ADR-0004

I read the source of `py2mcp` and `aw_agents` on this machine.

**`py2mcp`** — builds FastMCP servers from plain Python functions (`mk_mcp_server`,
`mk_mcp_from_refs`, `mk_mcp_from_store`), with input transforms, `serve_stdio`, a Streamable-HTTP +
OAuth-2.1 resource-server path (`mk_http_app` / `serve_http`), FastMCP middleware, and a server
`instructions` string. It is a well-made facade. **It is also tools-only**: a search of the package
source for `prompt`, `resource`, `elicit`, and `sampling` returns only OAuth *resource-server*
matches — there is no prompt registration, no resource registration, no elicitation, no structured
output. Its `mk_mcp_from_store` CRUD generator is a nice idea but wrong for us; the analysis store
is not a CRUD surface for the model.

**`aw_agents`** — this is the more consequential finding, and it does not support ADR-0004 as
written. `AgentBase` is an abstract class with exactly two methods, `get_tools()` returning
`[{name, description, parameters}]` and `execute_tool(name, arguments)` returning a
`{success, data, message, warnings}` dict. **There is no agent loop, no model client, no LLM access
of any kind** in the package. Its `MCPAdapter` wraps an agent for Claude Desktop using the
*low-level* `mcp.server.Server` API, stdio only, `list_tools` + `call_tool` only, and formats every
result as a single emoji-decorated `TextContent` string — no `structuredContent`, no `outputSchema`,
no `isError`, no prompts, no resources, no elicitation. The other adapter is OpenAPI for ChatGPT.

So the premise in ADR-0004 — "the declarative-spec-to-agent machinery and the multi-platform
adapters already exist there and match this problem exactly" — is **half right**. The multi-platform
*adapters* exist and are genuinely useful. The *agent* machinery does not exist: `aw_agents` is a
tool-definition container with two publishing adapters, not an agent framework. It cannot host the
deployed runtime that ADR-0004 assigns to it, because there is nothing there to own model access.
(`oa` is the OpenAI facade in the same ecosystem and does have the prompt-function machinery — a
folder of prompt templates becoming typed Python functions — which is a good model for the deployed
runtime's prompt loading, but it is OpenAI-oriented.)

**Recommendation — the four-way choice, decided.**

| Option | Verdict |
|---|---|
| `py2mcp` | **No.** Tools-only. Would force prompts and resources to be bolted onto the FastMCP object it returns, defeating the point of the facade. Keep it in mind for the CLI/OpenAPI side of ADR-0007. |
| `aw_agents` | **No, as the host.** Its MCP adapter is tools-only, stdio-only, on the low-level SDK, and predates the `2026-07-28` rewrite. Adopting it means reimplementing prompts, resources and elicitation inside it. |
| Raw official Python SDK v2 (low-level `Server`) | **No.** Correct but needlessly laborious; you would hand-write every schema. |
| **Official MCP Python SDK v2 / FastMCP 4** | **Yes.** SDK v2 implements `2026-07-28` and every earlier revision [20]. FastMCP 4.0.0 is the first version implementing modern-protocol elicitation via `InputRequiredResult`, including the stateless guard pattern where the tool returns an input requirement and the client reissues with `ctx.input_responses` [19]; it supports prompts with versioning and icons [18], resources and resource templates. Note that the fallback is **not automatic**: FastMCP *rejects* a tool that returns an `InputRequiredResult` on a handshake-era (≤ `2025-11-25`) connection "with a clear error naming the era mismatch", and the docs tell you to "branch on `ctx.request_context.protocol_version`… and fall back to `ctx.elicit()` on handshake-era ones" yourself [19]. Dual-era support is our code to write, not a freebie. |

The right shape is: **one package of plain deterministic Python functions** (`rubricator.tools`)
that know nothing about MCP; a thin FastMCP server that registers them along with the prompt and
resource content; and — *if and only if* someone wants the ChatGPT/OpenAPI target — `aw_agents` as a
**second consumer of the same functions**, never as the host. That inverts ADR-0004's "if
`aw_agents` can host the MCP surface directly, use it": it cannot, and it should not try.

Pin the protocol revision explicitly and state it in the README. Ship stdio for the connector;
Streamable HTTP only when a hosted deployment is actually wanted, and then without sessions and
without the GET stream, per the current transport spec [8].

---

## What this means for the schema / the view / the agent

### The proposed MCP tool surface

15 tools. Every one is deterministic: same arguments and same store state produce the same result,
with no model call and no network call except reading local sources. `analysis_id` is an opaque
handle per the spec's Stateful Tools guidance [6]; its retention policy is stated in
`analysis_open`'s description.

Column key — **Stage** is the ADR-0005 stage served. **Cut** marks what I would drop under time
pressure (see the cut list below).

| # | Tool | Signature (abbreviated) | Contract | Why it is deterministic | Stage | Cut |
|---|---|---|---|---|---|---|
| 1 | `analysis_open` | `(analysis_id?: str, subject?: str, aliases?: {alternatives, criteria}, allow_skip_confirmation?: bool=false) -> {analysis_id, stage, summary, next_actions}` | Creates a new in-progress analysis (a valid, minimal comparanda document with zero rows and columns) or reopens one by handle. Unknown/expired id ⇒ `isError` naming the retention window. | Store read/write only | 1, and every resume | keep |
| 2 | `analysis_get` | `(analysis_id, view: "summary"\|"frame"\|"criteria"\|"pending"\|"full"="summary") -> projection` | Reads the durable state. `pending` returns only cells that are `not-assessed`/`pending`, with counts by code. `full` returns a `resource_link`, not the document. | Pure projection | all | keep |
| 3 | `corpus_add` | `(analysis_id, sources: [{uri, text?, path?, media_type?}], chunking?: {target_chars, overlap}) -> {document_ids, span_count, token_estimate, warnings}` | Normalises, assigns stable `document_id`/`span_id`, records char offsets. Idempotent on content hash. | File/text processing, fixed chunker | 2, 5 | keep |
| 4 | `corpus_search` | `(analysis_id, query: str, k: int=8, document_ids?: [str], must_include?: [str], window_chars?: int=600) -> [{span_id, document_id, start, end, text, score}]` | **BM25 + normalized substring**, no embeddings. Empty query returns the whole corpus when under the inline threshold, else an actionable `isError`. | Lexical scoring, fixed tokenizer, fixed tie-break | 2, 3, 5 | keep |
| 5 | `corpus_read` | `(analysis_id, document_id, start?: int, end?: int, around_span_id?: str, window_chars: int=1200) -> {text, span_id, truncated}` | Windowed read so the model can widen a hit before citing it. Caps at 25k tokens and says so. | Byte-range read | 5 | **cut** — fold into `corpus_search(window_chars=...)` |
| 6 | `frame_set` | `(analysis_id, subject, decision, decider, ambiguities: [str], instructions?: str) -> {stage, validation}` | Records the frame. Requires at least one entry in `ambiguities` **or** an explicit `"none"`, so "surface ambiguity rather than resolving it silently" is mechanical, not aspirational. | Validated write | 1 | keep |
| 7 | `alternatives_set` | `(analysis_id, alternatives: [{id?, label, description?, group?, source: "user"\|"corpus"\|"inference", evidence?: [span_id]}], mode: "replace"\|"merge"="merge") -> {added, updated, near_duplicates: [{a, b, similarity}], unsourced: [id]}` | Writes rows. Flags near-duplicates by normalized token-set similarity above a configured threshold — it **flags, never merges**. Flags alternatives whose `source` is `inference` with no evidence. | String normalisation + fixed threshold | 2 | keep |
| 8 | `criteria_set` | `(analysis_id, criteria: [{id?, label, definition, polarity: "higher-better"\|"lower-better"\|"non-monotonic", level: "nominal"\|"ordinal"\|"interval"\|"ratio", measures: {score: {...}, confidence: {...}}, anchors?: {level: descriptor}, veto?: {threshold}, weight?}], mode="merge") -> {validation, hygiene}` | **Rejects any criterion without a `definition`** — ADR-0005's rule made mechanical. `hygiene` returns: missing anchors, missing polarity, definition-text overlap pairs above threshold, criterion count against the legibility guidance, and duplicate anchor descriptors. Diagnostics only; the model decides. | Schema validation + lexical overlap | 3 | keep |
| 9 | `frame_confirm` | `(analysis_id, scope: "all"\|"frame"\|"alternatives"\|"criteria"="all", confirmed_by?: str, confirmation_text?: str) -> {confirmed, mechanism: "elicitation"\|"out-of-band", record}` | **The ADR-0005 step-4 gate.** If the client declared `elicitation`, returns an `InputRequiredResult` with a flat form (`decision` enum `approve`/`approve-with-notes`/`revise`; `notes` string; optional multi-select "criteria to drop"). If not, returns success with `mechanism: "out-of-band"` and instructions that the model must ask in chat and call again with `confirmed_by` + `confirmation_text`. **The tool never confirms on its own behalf.** Writes the confirmation as authored, timestamped provenance. | It records a decision; it does not make one | **4** | keep |
| 10 | `measures_write` | `(analysis_id, cells: [{alternative_id, criterion_id, score?, confidence?, missing?: {code, note}, justification, evidence: [{span_id, quote}], source_type: "primary"\|"secondary"\|"inference"}], on_uncited: "reject"\|"downgrade"\|"allow"="downgrade") -> {written, rejected: [{cell, reason}], citation_check: [{cell, span_id, verified: bool, method}]}` | **The most important tool.** Validates against the comparanda schema; verifies each `quote` occurs in the cited `span_id` under whitespace/case normalisation; enforces "no `confidence: high` without a verified primary span" (`downgrade` demotes to medium and says so; `reject` refuses). Refuses to write scores at all if the analysis is unconfirmed and `allow_skip_confirmation` was not set at open. | String containment + schema validation | 5 | keep |
| 11 | `measures_mark_missing` | `(analysis_id, selector: {alternative_ids?, criterion_ids?, only_empty: bool=true}, code: "pending"\|"not-assessed"\|"not-applicable"\|"unknown"\|"withheld", note: str) -> {marked, skipped}` | Bulk qualified blanks. This is what makes "fill Pain and Market, mark the rest pending" a first-class instruction rather than a prompt hope, and it is the tool that makes a partial analysis a valid resumable document. | Set operations | 5, resume | keep |
| 12 | `analysis_validate` | `(analysis_id, strict: bool=true, schema_version?: str) -> {valid, schema_version, errors, warnings}` | Validates against the published comparanda JSON Schema at the boundary (ADR-0002). Non-negotiable per ADR-0008. | JSON Schema validation | 5, 6 | keep |
| 13 | `report_completeness` | `(analysis_id, by: "analysis"\|"alternative"\|"criterion"="analysis") -> counts by missingness code` | Completeness excluding `not-applicable`, per comparanda ADR-0009. | Counting | 5, 6 | **cut** — `analysis_get(view="pending")` covers it |
| 14 | `report_weaknesses` | `(analysis_id, top_k: int=10) -> {uncited, thin_evidence, low_confidence, criterion_correlations: [{a, b, spearman, n}], dominated_alternatives, veto_flags, weight_sensitivity?}` | The deterministic half of ADR-0005 step 6. Spearman correlation between score columns is the *post-hoc* evidence of the double-counting `criteria_set`'s hygiene could only guess at. Dominance and veto screening per comparanda ADR-0015. | Rank statistics on stored values | 6 | keep |
| 15 | `analysis_export` | `(analysis_id, format: "comparanda-json"\|"markdown"="comparanda-json") -> {resource_link, valid, schema_version}` | Validates then emits. Returns a `resource_link` content block, not the document body. | Serialisation | 6 | **cut** — `analysis_get(view="full")` returns the same link |

**Minimum viable set (10):** 1, 2, 3, 4, 6, 7, 8, 9, 10, 12. Cut 5, 13, 15 first (each is folded
into a tool that already exists). Cut 14 next if you must, accepting that ADR-0006's "self-critique
is part of the deliverable" degrades to unaided model opinion — which is exactly the failure mode
ADR-0008 exists to catch, so cut it last and restore it in Phase 4. Cut 11 only if you are also
willing to drop support for partial-fill instructions, which is a visible product regression.

**Tools deliberately NOT in the surface, and why:**

- No `propose_criteria` / `score_cell` / `review` tool. These are judgement. They are prompts.
  ADR-0003, enforced.
- No `detect_overlap` tool that returns a verdict. `criteria_set` returns lexical diagnostics and
  `report_weaknesses` returns rank correlations; the *judgement* that two criteria overlap belongs
  to the model and the user.
- No embedding-backed semantic search. §2.
- No aggregate/total tool. comparanda ADR-0015 is explicit that no aggregate is computed by
  default; a tool that returns one would make it the path of least resistance.
- No `analysis_list` tool. It is a resource (`rubricator://analyses`) — the *host* lists, the model
  does not browse.

### The prompts list

Ten MCP prompts. Every one takes string arguments only (protocol constraint [5]) and embeds state
as resource content blocks. Every one restates the ADR-0006 honesty rule in its own words, per
`docs/prompts/README.md`.

| Prompt | Arguments | Embeds | Stage |
|---|---|---|---|
| `run-analysis` | `analysis_id?`, `subject?` | method, tool map | the entry point / slash command |
| `frame` | `analysis_id` | method, corpus index summary | 1 |
| `enumerate-alternatives` | `analysis_id` | frame, corpus index summary | 2 |
| `propose-criteria` | `analysis_id`, `max_criteria?` | frame, alternatives, method, confidence rubric | 3 |
| `confirm-frame` | `analysis_id` | frame, alternatives, criteria with definitions | 4 — the chat script for clients without elicitation |
| `score-column` | `analysis_id`, `criterion_id` | criterion definition + anchors, alternatives, confidence rubric | 5 — **the default**, per the sibling scoring-order research |
| `score-cell` | `analysis_id`, `alternative_id`, `criterion_id` | one criterion, one alternative, retrieved spans | 5 — for repair and for hard cells |
| `review` | `analysis_id` | `report_weaknesses` output, criteria, method | 6 |
| `audit-existing` | `analysis_uri` | method, confidence rubric | — |
| `resume` | `analysis_id` | pending projection, confirmation record | resume |

(`run-analysis` and `resume` are the two entry points, and both are cheap.)

### The resources list

| URI | Kind | `annotations` | Purpose |
|---|---|---|---|
| `rubricator://method` | static | `audience: ["assistant"]`, `priority: 0.9` | The method statement and the ADR-0006 honesty rule as servable content |
| `rubricator://confidence-rubric` | static | `["assistant"]`, `0.9` | high = directly supported by a cited span; medium = inferred from adjacent evidence; low = plausible reasoning with little support |
| `rubricator://missingness-codes` | static | `["assistant"]`, `0.8` | The closed code set and when to use each |
| `rubricator://schema/comparanda/{version}` | template | `["assistant"]`, `0.6` | The published JSON Schema `analysis_validate` validates against |
| `rubricator://analyses` | static (list) | `["user"]`, `0.5` | In-progress analyses — the host-side resume affordance |
| `rubricator://analysis/{analysis_id}` | template | `["user","assistant"]`, `0.7`, `lastModified` | The analysis document |
| `rubricator://analysis/{analysis_id}/document/{document_id}` | template | `["user"]`, `0.4` | A source document, for deep-linking |
| `rubricator://analysis/{analysis_id}/span/{span_id}` | template | `["user"]`, `0.6` | **A cited span with its text.** This makes `rubricator`'s evidence references resolvable URIs, which is what comparanda's host-supplied `EvidenceResolver` (its ADR-0014) needs |

Declare `resources.listChanged: true`; `subscribe` is not needed in v1.

### Concrete implementation notes

- **Names:** `snake_case`, noun-first prefix, ASCII, 1–128 chars inclusive (spec says **SHOULD**, not
  **MUST**) [6].
- **Errors:** validation and business-rule failures ⇒ `isError: true` with a message that carries
  the fact needed to fix it (spec's own convention [6]). Unknown tool / malformed request ⇒
  JSON-RPC error. Expired `analysis_id` ⇒ `isError` naming the retention window and suggesting
  `analysis_open` [6].
- **Every tool declares `outputSchema` and returns `structuredContent`** plus a short human-readable
  `content` summary [6].
- **Token discipline:** default `k=8` on `corpus_search`; `view="summary"` default on
  `analysis_get`; never return the whole analysis inline; cap any text return at 25k tokens and say
  when truncated [13].
- **Determinism to make ADR-0008 testable:** fix the BM25 tokenizer and stopword list, fix
  tie-breaking by `(score, document_id, start)`, fix the near-duplicate threshold as a named
  constant in config, and version the chunker. A retrieval change that silently reorders spans would
  look like a prompt regression.
- **Store:** a `dol`-style Mapping in the platform user-data directory, one record per analysis plus
  a corpus-index sidecar. Never inside the package directory.
- **Fixtures:** public domains only (programming languages, cities, databases, bicycles), shared
  with comparanda per its ADR-0016.

---

## Recommended ADR actions

| ADR | Action | Reason |
|---|---|---|
| ADR-0003 | confirm | The one-spec-two-runtimes decision survives intact; MCP prompts are the right vehicle for prompts-as-content, and the deprecation of sampling removes the only tempting exception to "no tool may require a model" |
| ADR-0004 | supersede | `aw_agents` has no agent loop and no model access; its MCP adapter is tools-only, stdio-only, low-level-SDK, pre-`2026-07-28`. Build the MCP surface on the official Python SDK v2 / FastMCP 4 over a plain-function core; keep `aw_agents` only as an optional second consumer for the ChatGPT/OpenAPI target |
| ADR-0005 | amend | Step 4 stands, but the mechanism must be specified: MCP elicitation where the client supports it (flat-primitive form only — the protocol forbids nested schemas), a chat-plus-record path where it does not, and the confirmation stored as authored provenance either way |
| ADR-0007 | amend | Deliverables (1) and (2) merge: the prompt bundle ships *as MCP prompts inside the server*, not as a separate skill bundle. `py2mcp` moves to the CLI/OpenAPI line, not the connector |
| new ADR-0009 | new | *The determinism boundary.* No MCP sampling (deprecated `2026-07-28`), no in-tool model calls, **and no embedding calls** — retrieval is lexical (BM25 + normalized substring), with a fixed tokenizer and fixed tie-break so ADR-0008's stability test means something |
| new ADR-0010 | new | *In-progress analyses are durable partial comparanda documents.* An opaque `analysis_id` handle, a record that is itself schema-valid, `not-assessed`/`pending`/`unknown` carrying the resume semantics, the step-4 confirmation stored as provenance, and three resume entry points |

---

## Open questions

- **Core client feature support.** The docs site's `/clients` page now redirects to the
  introduction, and the surviving matrix at `/extensions/client-matrix` covers only MCP Apps and
  the two auth extensions [25]. I could not obtain a current, authoritative per-client table
  for prompts / resources / elicitation, and my WebSearch budget was exhausted before I could look
  further. **What would settle it:** run `server/discover` and inspect
  `_meta.io.modelcontextprotocol/clientCapabilities` on incoming requests from each target client
  (Claude Desktop, Claude Code, claude.ai connectors) with a throwaway server that logs them. That
  is a one-afternoon experiment and it should be the first thing Phase 3 does, because the
  `frame_confirm` fallback path either matters enormously or not at all depending on the answer.
- **The comparanda JSON Schema does not exist yet.** Its ADR-0004 promises a published,
  language-neutral JSON Schema generated from zodal. Until it lands, `analysis_validate` validates
  against a hand-written sketch derived from `comparanda/docs/domain-model.md`. This is the blocking
  dependency BRIEF.md anticipated; the tool surface above is designed so that only
  `analysis_validate` and the schema resource change when it arrives.
- **The near-duplicate and definition-overlap thresholds** in `alternatives_set` and `criteria_set`
  are named constants with no empirical basis yet. Settle them against the ADR-0008 fixture set,
  optimising for recall (over-flagging is cheap; a missed duplicate is expensive).
- **Whether `report_weaknesses` should compute weight sensitivity in v1.** comparanda ADR-0015
  wants it, but it only means anything when weights are actually set, and nothing in ADR-0005 asks
  the agent to set weights. Probably defer.
- **Whether Tasks is worth implementing for the populate stage.** It gives real progress visibility
  and mid-flight input on a 60-cell run, but support is per-client and unverified for our targets.
  Same experiment as the first bullet settles it.
- **Protocol churn risk.** `2026-07-28` broke server-initiated requests, removed HTTP sessions and
  the GET stream, and deprecated four features at once [2][3][8]. Pin the revision, keep the
  MCP-facing layer thin over plain functions, and expect to re-read the changelog before each
  release.

---

## REFERENCES

1. [Model Context Protocol — Specification (revision 2026-07-28) (2026)](https://modelcontextprotocol.io/specification/2026-07-28/)
2. [MCP — Deprecated Features registry, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/deprecated)
3. [MCP — Multi Round-Trip Requests (MRTR), revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr)
4. [MCP — Elicitation, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation)
5. [MCP — Prompts, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/server/prompts)
6. [MCP — Tools, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)
7. [MCP — Resources, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
8. [MCP — Streamable HTTP transport, revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
9. [MCP — Tasks extension overview (2026)](https://modelcontextprotocol.io/extensions/tasks/overview)
10. [MCP — Versioning (2026)](https://modelcontextprotocol.io/specification/versioning)
11. [MCP — Roots (deprecated), revision 2026-07-28 (2026)](https://modelcontextprotocol.io/specification/2026-07-28/client/roots)
12. [Tool search tool — Anthropic (2026)](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
13. [Writing effective tools for agents — with agents — Anthropic Engineering (2025)](https://www.anthropic.com/engineering/writing-tools-for-agents)
14. [Code execution with MCP: building more efficient agents — Anthropic Engineering (2025)](https://www.anthropic.com/engineering/code-execution-with-mcp)
15. [RAG-MCP: Mitigating Prompt Bloat in LLM Tool Selection via Retrieval-Augmented Generation — Gan & Sun (2025)](https://arxiv.org/abs/2505.03275)
16. [Playwright MCP — README, tool definitions (2026)](https://github.com/microsoft/playwright-mcp)
17. [GitHub MCP Server — README, toolsets (2026)](https://github.com/github/github-mcp-server)
18. [FastMCP — Prompts (2026)](https://gofastmcp.com/servers/prompts)
19. [FastMCP — Elicitation (2026)](https://gofastmcp.com/servers/elicitation)
20. [MCP Python SDK — official repository (2026)](https://github.com/modelcontextprotocol/python-sdk)
21. [LangGraph — Persistence (checkpointers, threads, stores) (2026)](https://docs.langchain.com/oss/python/langgraph/persistence)
22. [Pricing — Anthropic (2026)](https://platform.claude.com/docs/en/about-claude/pricing)
23. [Lost in the Middle: How Language Models Use Long Contexts — Liu et al. (2024)](https://arxiv.org/abs/2307.03172) *(cited from the sibling research brief in this repository; not independently re-fetched in this session)*
24. [Large Language Models are Inconsistent and Biased Evaluators — Stureborg, Alikaniotis & Suhara (2024)](https://arxiv.org/abs/2405.01724) *(cited from the sibling research brief in this repository; not independently re-fetched in this session)*
25. [MCP — Extension Support Matrix (2026)](https://modelcontextprotocol.io/extensions/client-matrix)
