# Confidence: what each level means

`confidence` grades **the evidence**, not how sure you feel. Asking a model how sure it is produces systematic overconfidence; asking how good the evidence is produces something a person can check (ADR-0012).

| Level | Means |
|---|---|
| `high` | directly stated by a cited source |
| `medium` | inferred from adjacent evidence in a cited source |
| `low` | plausible reasoning with little support |

`low` means thin evidence. It never means *no* evidence: that case is a blank with a reason, not a low-confidence score.

## The two uncertainties, kept apart

- **Evidential confidence** is stored with the cell. It says how good the evidence behind this score is.
- **Procedural stability** is derived, never stored or self-reported. It says how much the cell moves when it is scored again, and comes from repeated passes (`stability_report`, `disclose_variance`).

A cell can be well evidenced and unstable, or poorly evidenced and stable. Do not let one stand in for the other.

## Rules that bind

1. No citable span means a blank, never a low-confidence score.
2. The score is never hedged toward the midpoint. All uncertainty goes in `confidence`.
3. Contradiction between sources is one step down from what the evidence would otherwise carry, with a named reason from a closed set (`superseded`, `different-quantity`, `different-date`, `unexplained`, or the analysis's own declared set), opening the justification as `downgraded (<kind>): <span id> vs <span id>.`
4. For a level with no anchor of its own (2 or 4), confidence still grades the evidence, not your placement of it.
