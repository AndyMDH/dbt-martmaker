-- DBT-MARTMAKER DRAFT
-- Generated from churn-metrics.csv on 2026-07-22T21:20:06+02:00. Not part
-- of the dbt DAG until a human reviews this, drops the draft__ prefix,
-- and moves it into models/marts/. Do not run `dbt build` against this
-- file in place.
--
-- Metric: Average payment amount
-- Description: Average dollar amount per payment
-- Reasoning (stakeholder, verbatim): I quote this in pricing reviews so
-- it has to be right - refunds have skewed it negative before
-- Proposed calculation (inferred, approved before this file was built):
-- avg(amount) grouped across all payments in stg_payments -- based on
-- "refunds have skewed it negative before"
-- `amount` was confirmed as a real column on stg_payments in Step 3; an
-- unconfirmed column never reaches this file, it stays an Open Question.

with

source_model as (
    select * from {{ ref('stg_payments') }}
),

final as (
    select
        avg(amount) as avg_payment_amount
    from source_model
)

select * from final
