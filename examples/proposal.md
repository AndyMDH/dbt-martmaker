---
status: proposed
source_sheet: churn-metrics.csv
generated_at: 2026-07-22T21:20:06+02:00
naming_convention_detected_from: dbt-bouncer.yml
---

# Mart Proposal

## Summary

| Metric | Column used | Description | Calculation | Importance | Status |
|---|---|---|---|---|---|
| Payment count | `stg_payments` | Number of payments processed | just a count of payments | low | Matched |
| Monthly churned users | — | Active in last 30 days then inactive | count of users who stopped logging in over the last month | high | Blocked |
| Revenue lost to churn | — | Subscription revenue from users who churned this month | total subscription revenue from people who churned this month | medium | Ambiguous |

## Payment count
- Definition: Number of payments processed
- Calculation: just a count of payments
- Importance: low
- Grounding: matched `stg_payments` (models/staging/stripe/stg_payments.sql) — confirmed via manifest, score 1.0
- Status: Matched

## Monthly churned users
- Definition: Active in last 30 days then inactive
- Calculation: count of users who stopped logging in over the last month
- Importance: high
- Grounding: blocked — no matching staging/intermediate model found for "user_events"
- Status: Blocked

## Revenue lost to churn
- Definition: Subscription revenue from users who churned this month
- Calculation: total subscription revenue from people who churned this month
- Importance: medium
- Grounding: ambiguous for "subscriptions" — candidates: `stg_billing__subscriptions`, `int_billing__subscription_history`
- Status: Ambiguous

## Proposed changes (once approved)
- New: `draft__rpt_payment_count.sql` (grain: one row per payment) —
  tests calibrated to low importance (description only, no drafted tests)

## Open questions
- [ ] Confirm which of [`stg_billing__subscriptions`, `int_billing__subscription_history`] is correct for "subscriptions" (Revenue lost to churn)
- [ ] "user_events" (Monthly churned users) needs a new source staged first — out of scope for this tool

## Next steps
1. Resolve open questions above.
2. **Reply to approve** — nothing has been built yet. Once you confirm,
   the draft SQL/schema.yml for Payment count gets written for review.
3. After that: rename (drop the `draft__` prefix), move into the real
   `models/marts/...` directory, and run `dbt parse`/`dbt-bouncer` locally.
