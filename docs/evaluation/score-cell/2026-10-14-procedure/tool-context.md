# The tools you call (as the connector shows them)

## measures_write
Write one contributor's assertions: a value with its justification and cited evidence, or a qualified blank naming its missingness code. Writes only that contributor's file and never echoes a previously written score. Each assertion is stamped with the criteria-set version; pass expected_criteria_version to be refused if the set moved since you read it. An agent passes procedure on every pass, the first included (round number, same or fresh session, whether the prior was withheld or shown, and the plan's traversal, reduction and seed when it has one); a cell takes one draw per round: the tools record the procedure, count its repeats and derive each draw's independence rung, and refuse a rung the pass contradicts. Honesty rules run before the bytes land (ADR-0024).

Its `procedure` argument (optional):
```json
{
 "type": "object",
 "properties": {
  "traversal": {
   "type": "string",
   "enum": [
    "cell-wise",
    "column-wise",
    "row-wise",
    "single-pass"
   ]
  },
  "reduction": {
   "type": "string",
   "enum": [
    "lower-median",
    "median",
    "min",
    "max"
   ]
  },
  "seed": {
   "anyOf": [
    {
     "type": "string"
    },
    {
     "type": "number"
    }
   ]
  },
  "round": {
   "type": "integer"
  },
  "session": {
   "type": "string",
   "enum": [
    "same",
    "fresh"
   ]
  },
  "prior": {
   "type": "string",
   "enum": [
    "withheld",
    "shown"
   ]
  }
 },
 "required": [],
 "additionalProperties": false
}
```

## measures_mark_missing
Mark a selection of cells as one qualified blank -- every alternative, or those named, against every criterion, or those named -- with a note saying why. The code must be one the analysis's own vocabulary resolves: the core six, or a code declared on the analysis or the criterion. This is what makes 'fill these two criteria and mark the rest deferred' a first-class instruction. A blank from a pass takes the same procedure as measures_write, so it is counted and stamped like any other draw; with a procedure it is for one cell (exactly one of alternative_ids and one of criterion_ids) and its code is one that says someone looked, not not-assessed or deferred.

Its `procedure` argument (optional):
```json
{
 "type": "object",
 "properties": {
  "traversal": {
   "type": "string",
   "enum": [
    "cell-wise",
    "column-wise",
    "row-wise",
    "single-pass"
   ]
  },
  "reduction": {
   "type": "string",
   "enum": [
    "lower-median",
    "median",
    "min",
    "max"
   ]
  },
  "seed": {
   "anyOf": [
    {
     "type": "string"
    },
    {
     "type": "number"
    }
   ]
  },
  "round": {
   "type": "integer"
  },
  "session": {
   "type": "string",
   "enum": [
    "same",
    "fresh"
   ]
  },
  "prior": {
   "type": "string",
   "enum": [
    "withheld",
    "shown"
   ]
  }
 },
 "required": [],
 "additionalProperties": false
}
```


## What the tools do with a second assertion on a cell

A cell that already holds an assertion takes another only if the new one's independence is recorded. When you pass a `procedure`, the tools derive it from `session` and `prior` (an earlier pass in view is shared-context; a fresh session is a resample). With a `procedure` that carries neither, nothing is derived and the write is refused, naming `independence-recorded`. A cell takes one draw per round. `measures_mark_missing` takes `alternative_ids` and `criterion_ids` (lists); with a `procedure` it must name exactly one of each.
