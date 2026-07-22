---
status: proposed
source_sheet: churn-metrics.csv
generated_at: 2026-07-22T21:20:06+02:00
naming_convention_detected_from: dbt-bouncer.yml
---

# Mart Proposal

## Payment count
- Definition: Number of payments processed
- Calculation: just a count of payments
- Grounding: matched `stg_payments` (models/staging/stripe/stg_payments.sql) — confirmed via manifest, score 1.0
- Status: Matched

## Monthly churned users
- Definition: Active in last 30 days then inactive
- Calculation: count of users who stopped logging in over the last month
- Grounding: blocked — no matching staging/intermediate model found for "user_events"
- Status: Blocked

## Revenue lost to churn
- Definition: Subscription revenue from users who churned this month
- Calculation: total subscription revenue from people who churned this month
- Grounding: ambiguous for "subscriptions" — candidates: `stg_billing__subscriptions`, `int_billing__subscription_history`
- Status: Ambiguous

## Open questions
- [ ] Confirm which of [`stg_billing__subscriptions`, `int_billing__subscription_history`] is correct for "subscriptions" (Revenue lost to churn)
- [ ] "user_events" (Monthly churned users) needs a new source staged first — out of scope for this tool

## Next steps for human review
1. Resolve open questions above (bring to the next meeting if needed).
2. Review the draft SQL/schema.yml under `models/`.
3. Rename (drop the `draft__` prefix), move into the real `models/marts/...`
   directory, and run `dbt parse`/`dbt-bouncer` locally.
