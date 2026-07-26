---
status: proposed
source_sheet: churn-metrics.csv
generated_at: 2026-07-26T10:41:18+02:00
naming_convention_detected_from: dbt-bouncer.yml
---

# Mart Proposal

## Summary

| Metric | Column used | Description | Proposed calculation | Grain | Proposed tests | Importance | Status |
|---|---|---|---|---|---|---|---|
| Payment count | `stg_payments` | Number of payments processed | count of rows in `stg_payments` | undecided — see open questions | none (low importance) | low | Matched |
| Average payment amount | `stg_payments` | Average dollar amount per payment | avg(amount) in `stg_payments` | one row total | not_null, not_negative (reused) | high | Matched |
| Monthly churned users | — | Active in last 30 days then inactive | — (blocked, see below) | — | — | high | Blocked |
| Revenue lost to churn | — | Subscription revenue from users who churned this month | — (ambiguous, see below) | — | — | medium | Ambiguous |
| Marketing ROI | — | How efficient our marketing spend is | — (blocked, see below) | — | — | medium | Blocked |

## Payment count
- Description: Number of payments processed
- Reasoning (stakeholder, verbatim): just a count of payments
- Proposed calculation (inference — confirm before building): count of rows in `stg_payments`
- Grain (inference — confirm before building): **undecided** — "just a count of payments" doesn't say over what period, so pick from the options below
- Proposed tests: none — importance is low, so only the description gets drafted (see AGENTS.md Step 5)
- Importance: low
- Grounding: matched `stg_payments` (models/staging/stripe/stg_payments.sql) — confirmed via manifest, score 1.0
- Status: Matched

**Option A — one running total** *(fake data — shape only, no query was run)*:

| payment_count |
|---|
| 1204 |

**Option B — one row per month** *(fake data)*:

| month | payment_count |
|---|---|
| 2026-05 | 188 |
| 2026-06 | 203 |
| 2026-07 | 174 |

## Average payment amount
- Description: Average dollar amount per payment
- Reasoning (stakeholder, verbatim): average how much each payment is for - amounts should never be null or negative
- Proposed calculation (inference — confirm before building): `avg(amount)` across all rows in `stg_payments`
- Grain (inference — confirm before building): one row total — the reasoning reads as one overall average, with no per-period or per-customer signal
- Proposed tests: `not_null` (explicit in reasoning) + `not_negative` — this project already has that custom test (used twice elsewhere), reused here instead of a generic substitute (see AGENTS.md Step 5)
- Importance: high
- Grounding: matched `stg_payments` (models/staging/stripe/stg_payments.sql) — confirmed via manifest, score 1.0
- Status: Matched

**What the output would look like** *(fake data — shape only, no query was run)*:

| avg_payment_amount |
|---|
| 52.40 |

## Monthly churned users
- Description: Active in last 30 days then inactive
- Reasoning (stakeholder, verbatim): count of users who stopped logging in over the last month based on our login/activity data
- Proposed calculation: not proposed — no source to calculate against
- Grain: — (nothing to shape yet)
- Proposed tests: not proposed — nothing to attach a test to yet
- Importance: high
- Grounding: blocked — no matching staging/intermediate model found for "login/activity data"
- Status: Blocked

## Revenue lost to churn
- Description: Subscription revenue from users who churned this month
- Reasoning (stakeholder, verbatim): total subscription revenue from people who churned this month using our subscriptions data
- Proposed calculation: not proposed yet — depends on which "subscriptions" model is correct
- Grain: — (decided once the source is; "this month" suggests one row per month)
- Proposed tests: not proposed yet — same reason
- Importance: medium
- Grounding: ambiguous for "subscriptions" — candidates: `stg_billing__subscriptions`, `int_billing__subscription_history`
- Status: Ambiguous

## Marketing ROI
- Description: How efficient our marketing spend is
- Reasoning (stakeholder, verbatim): compare what we spent on ads against the revenue it brought in - probably need ad spend and revenue numbers
- Proposed calculation: not proposed — no source for ad spend/marketing data
- Grain: — (nothing to shape yet)
- Proposed tests: not proposed — nothing to attach a test to yet
- Importance: medium
- Grounding: blocked — no matching staging/intermediate model found for "ad spend" or "marketing spend"
- Status: Blocked

## Proposed changes (once approved)
- New: `draft__rpt_avg_payment_amount.sql` (grain: one row total, aggregate) —
  `not_null` + the project's existing `not_negative` custom test, since
  importance is high and the reasoning explicitly ruled out null/negative
  values. See [`draft__rpt_avg_payment_amount.sql`](draft__rpt_avg_payment_amount.sql)
  and [`draft___payments__models.yml`](draft___payments__models.yml) for
  what these actually look like once built.
- Pending: `draft__rpt_payment_count.sql` — stays unbuilt until the grain
  question below is answered (Option A or B), even if the rest is approved.

## Open questions
- [ ] **Payment count**: which of the option tables above is the one you pictured — A (one running total) or B (one row per month)?
- [ ] Confirm which of [`stg_billing__subscriptions`, `int_billing__subscription_history`] is correct for "subscriptions" (Revenue lost to churn)
- [ ] "login/activity data" (Monthly churned users) needs a new source staged first — out of scope for this tool
- [ ] "ad spend"/"marketing spend" (Marketing ROI) needs a new source staged first — out of scope for this tool

## Next steps
1. Resolve open questions above.
2. **Reply to approve** — nothing has been built yet, and every calculation
   above is an inference, not what the stakeholder literally wrote. Once
   you confirm, the draft SQL/schema.yml for the Matched rows with a
   decided grain get written for review.
3. After that: rename (drop the `draft__` prefix), move into the real
   `models/marts/...` directory, and run `dbt parse`/`dbt-bouncer` locally.
