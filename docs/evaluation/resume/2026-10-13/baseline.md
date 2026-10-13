# Pick up a partial analysis

The user is coming back to an analysis started in an earlier session. You have called `analysis_get` (view summary), `frame_confirm` (no decision) and `report_completeness`, and sometimes `analysis_get` (view criteria); their results are below. Tell the user where the analysis stands and propose the next step. Do not start it.

End your reply with this block, one line each:

```
Confirmed: <who> at <when>, criteria version <v>   (or `Confirmed: no`, or `Confirmed: criteria changed since <who>'s confirmation at <when>`)
Nobody has looked: <n>
Set aside on purpose: <n>
Looked, answer is a blank: <n>
Scored: <n>
Re-score after a criteria change: <n>
Next: <kind> — <one sentence>
```

`<kind>` is one of `confirm`, `score`, `rescore`, `ask-deferred`, `review`.
