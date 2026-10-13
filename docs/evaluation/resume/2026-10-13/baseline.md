# Pick up a partial analysis

The user is coming back to an analysis started in an earlier session. You have called `analysis_get` (view summary), `frame_confirm` (no decision) and `report_completeness`, and sometimes `analysis_get` (view criteria); their results are below. Tell the user where the analysis stands and propose the next step. Do not start it.

End your reply with this block, one line each:

```
Confirmed: <who> at <when>, criteria version <v>
Nobody has looked: <n> cells
Set aside on purpose: <n> cells
Re-score after a criteria change: <n> cells
Scored: <n> claims
Looked, answer is a blank: <n> claims
Not applicable: <n> claims
Next: <kind> — <one sentence>
```

The first line begins `Confirmed:`. When no person's confirmation stands, write `Confirmed: skipped at <when>, nobody confirmed`, `Confirmed: criteria changed since <who>'s confirmation at <when>`, or `Confirmed: no — <why>`.

`<kind>` is one of `confirm`, `score`, `rescore`, `ask-deferred`, `review`.
