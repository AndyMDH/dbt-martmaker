-- DBT-MARTMAKER DRAFT
-- Generated from churn-metrics.csv on 2026-07-22T21:20:06+02:00. Not part
-- of the dbt DAG until a human reviews this, drops the draft__ prefix,
-- and moves it into models/marts/. Do not run `dbt build` against this
-- file in place.
--
-- Metric: Average payment amount
-- Description: Average dollar amount per payment
-- Reasoning (stakeholder, verbatim): average how much each payment is
-- for - amounts should never be null or negative
-- Proposed calculation (inferred, approved before this file was built):
-- avg(amount) grouped across all payments in stg_payments

with

source_model as (
    select * from {{ ref('stg_payments') }}
),

final as (
    select
        -- TODO: confirm the actual amount column name in stg_payments
        avg(amount) as avg_payment_amount
    from source_model
)

select * from final
