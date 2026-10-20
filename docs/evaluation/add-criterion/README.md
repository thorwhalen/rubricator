# add-criterion adherence runs

Five requests to add a criterion to one confirmed analysis on an invented domain (three fictional kettles, one office deciding; three fully defined criteria, two cells recorded). The analysis is built by driving the real verbs, and the subject sees the user's request and what `analysis_get` with `view: "criteria"` returns. It writes the ordered tool calls it would make and its reply. `scripts/add_criterion_adherence.py` grades them with no model call, and **replays each `criteria_set` call against a fresh copy of the analysis**, so "accepted", "new fully defined" and "nothing superseded" are what the real verb returned. This is the evidence the `rubricator-dev-prompt-change` skill requires before a prompt lands, until the ADR-0008 suite can run a prompt arm itself ([#148](https://github.com/thorwhalen/rubricator/issues/148)).

    python scripts/add_criterion_scenarios.py docs/evaluation/add-criterion/scenarios.json
    python scripts/add_criterion_adherence.py docs/evaluation/add-criterion/scenarios.json docs/evaluation/add-criterion/2026-10-20/out-*.json

`scenarios.json` is generated, and `tests/test_add_criterion.py` fails if the tools stop returning it; the same file holds the grader to the verbs (a faithful answer grades full marks, and each failure below is caught by its metric).

| id | the request | the right response |
|---|---|---|
| a1 | boil time for a full kettle, faster is better | add |
| a2 | "add sustainability" | ask what they mean |
| a3 | years the maker keeps parts in stock | ask: that is `spare-parts` |
| a4 | make repair policy count the heating element | ask: a revision of `repair-policy`, not an addition |
| a5 | energy per boil, lower is better, for the sustainability report | add |

**Existing untouched**, read first: the call sends every existing criterion exactly as `analysis_get` returned it, in order, with no `editorial`. A re-typed or tidied criterion is an edit that supersedes its cells, which is what this prompt exists to prevent. The other metrics: **action right** (one `criteria_set` call on an add, none on an ask), **no cell written** (no `measures_write` or `measures_mark_missing` call), **accepted**, **new fully defined** (all five definition fields, no `definitionGaps` on it), **nothing superseded** (`revised` empty, `supersededCells.count` 0), **says not assessed** and **next is confirm** (the reply's block), **names the criterion** (a3, a4).

## 2026-10-20 — v1 ([#128](https://github.com/thorwhalen/rubricator/issues/128))

| arm | existing untouched | action right | no cell written | accepted | new fully defined | nothing superseded | says not assessed | next is confirm | names the criterion |
|---|---|---|---|---|---|---|---|---|---|
| draft, Sonnet | 2/2 | 5/5 | 5/5 | **0/2** | n/a | n/a | 2/2 | 2/2 | 2/2 |
| draft, Haiku | 2/2 | 5/5 | 5/5 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| draft 2, Sonnet | 2/2 | 5/5 | 5/5 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| draft 2, Haiku | 1/1 | **4/5** | 5/5 | 1/1 | 1/1 | 1/1 | 1/2 | 1/2 | 2/2 |
| **v1, Sonnet** | 2/2 | 5/5 | 5/5 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| **v1, Haiku** | 2/2 | 5/5 | 5/5 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

- **Existing untouched: 2/2 in every arm that made the call.** No subject re-typed an existing criterion or wrote a cell, in any run.
- **Draft → draft 2.** Sonnet put a `provenance` object inside the new criterion, which `criteria_set` refuses ("Additional properties are not allowed"). The draft said a criterion is marked `user-stated` or `agent-proposed` but not where. The prompt now says that provenance goes in the reply's `Added` line and nothing but the stored keys goes in the criterion.
- **Draft 2 → v1.** Haiku read a5 as a means objective (energy per boil serving the sustainability report) and asked instead of adding. The means test now says what a means serves (a different thing the decider wants judged) and what is not one (the measure of the reason the user gave). Its worked example is a different request from a5, so the fix does not teach the scenario.
- **Not established:** one run per arm per text; all five scenarios in one context per arm; the scenarios are the prompt author's; the subjects could not see `criteria_set`'s real result, so the prompt's read-the-result step (stop when `revised` is not empty) is unexercised; no baseline without the prompt was run.
