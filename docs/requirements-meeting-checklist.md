# Requirements meeting checklist

Bring this into a data-requirements meeting. Each item maps directly onto a
column in the metric sheet (`metric`, `definition`, `calculation`,
`source_tables`) — capturing these during the conversation is what makes
filling the sheet afterward easy instead of a guessing exercise.

## Grain & uniqueness
- What makes one row one row? ("one row per user per day," not just "user
  data")
- Is this metric truly at the grain being discussed, or is it actually a
  rollup of something finer?

## Definitions
- Write down the *exact* wording stakeholders use for a term ("active,"
  "churned," "at-risk") — different teams often mean different things by
  the same word. If two people in the room define it differently, that's
  the moment to resolve it, not later.

## Calculation
- Get the actual formula, not just the concept: numerator, denominator,
  filters, time window. "Churn rate" is not a calculation; "users with no
  login in 30 days ÷ total active users at start of period" is.

## Source data
- Which table(s) does this come from? A name mentioned in conversation
  ("the invoices table") is enough — dbt-martsmith grounds it against what
  actually exists.
- Does this data already exist somewhere, or does someone need to confirm a
  new source is being staged?

## Freshness & quality
- How fresh does this need to be? ("daily by 8am," not just "regularly")
- Any explicit data-quality requirement? ("revenue can't be null," "no
  duplicate user_ids")

## Ownership
- Who asked for this, and who owns the answer if there's ambiguity later?

## Historical vs. current state
- Does this need to reflect history (e.g. a customer's status *at the time
  of the order*) or just the current state?

## Edge cases
- What happens with nulls, duplicates, or late-arriving data? Get an
  explicit answer, even a temporary one ("exclude for now") — write it down
  as such so it can be revisited later rather than assumed permanent.
