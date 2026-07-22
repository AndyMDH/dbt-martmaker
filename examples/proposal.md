---
status: proposed
source_sheet: churn-metrics.csv
generated_at: 2026-07-22T21:20:06+02:00
naming_convention_detected_from: dbt-bouncer.yml
---

# Mart Proposal

## Summary

| Metric | Column used | Description | Proposed calculation | Proposed tests | Importance | Status |
|---|---|---|---|---|---|---|
| Payment count | `stg_payments` | Number of payments processed | count of rows in `stg_payments` | none (low importance) | low | Matched |
| Monthly churned users | — | Active in last 30 days then inactive | — (blocked, see below) | — | high | Blocked |
| Revenue lost to churn | — | Subscription revenue from users who churned this month | — (ambiguous, see below) | — | medium | Ambiguous |
| Marketing ROI | — | How efficient our marketing spend is | — (blocked, see below) | — | medium | Blocked |

## Payment count
- Description: Number of payments processed
- Reasoning (stakeholder, verbatim): just a count of payments
- Proposed calculation (inference — confirm before building): count of rows in `stg_payments`
- Proposed tests: none — importance is low, so only the description gets drafted (see AGENTS.md Step 5)
- Importance: low
- Grounding: matched `stg_payments` (models/staging/stripe/stg_payments.sql) — confirmed via manifest, score 1.0
- Status: Matched

## Monthly churned users
- Description: Active in last 30 days then inactive
- Reasoning (stakeholder, verbatim): count of users who stopped logging in over the last month based on our login/activity data
- Proposed calculation: not proposed — no source to calculate against
- Proposed tests: not proposed — nothing to attach a test to yet
- Importance: high
- Grounding: blocked — no matching staging/intermediate model found for "login/activity data"
- Status: Blocked

## Revenue lost to churn
- Description: Subscription revenue from users who churned this month
- Reasoning (stakeholder, verbatim): total subscription revenue from people who churned this month using our subscriptions data
- Proposed calculation: not proposed yet — depends on which "subscriptions" model is correct
- Proposed tests: not proposed yet — same reason
- Importance: medium
- Grounding: ambiguous for "subscriptions" — candidates: `stg_billing__subscriptions`, `int_billing__subscription_history`
- Status: Ambiguous

## Marketing ROI
- Description: How efficient our marketing spend is
- Reasoning (stakeholder, verbatim): compare what we spent on ads against the revenue it brought in - probably need ad spend and revenue numbers
- Proposed calculation: not proposed — no source for ad spend/marketing data
- Proposed tests: not proposed — nothing to attach a test to yet
- Importance: medium
- Grounding: blocked — no matching staging/intermediate model found for "ad spend" or "marketing spend"
- Status: Blocked

## Proposed changes (once approved)
- New: `draft__rpt_payment_count.sql` (grain: one row per payment) —
  tests calibrated to low importance (description only, no drafted tests).
  Note for future high/medium-importance metrics on numeric columns: this
  project already has a custom `not_negative` test (used twice elsewhere)
  — that gets proposed ahead of a generic substitute when it fits.

## Open questions
- [ ] Confirm which of [`stg_billing__subscriptions`, `int_billing__subscription_history`] is correct for "subscriptions" (Revenue lost to churn)
- [ ] "login/activity data" (Monthly churned users) needs a new source staged first — out of scope for this tool
- [ ] "ad spend"/"marketing spend" (Marketing ROI) needs a new source staged first — out of scope for this tool

## Next steps
1. Resolve open questions above.
2. **Reply to approve** — nothing has been built yet, and the calculation
   above is an inference, not what the stakeholder literally wrote. Once
   you confirm, the draft SQL/schema.yml for Payment count gets written
   for review.
3. After that: rename (drop the `draft__` prefix), move into the real
   `models/marts/...` directory, and run `dbt parse`/`dbt-bouncer` locally.
