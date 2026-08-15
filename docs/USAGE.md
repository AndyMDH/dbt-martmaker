# Usage

See the README's [Quickstart](../README.md#quickstart) for the example
metric sheet and proposal summary table. This doc picks up from there.

## The metric sheet

`reasoning` is the stakeholder's *why* — the decision the metric feeds,
who's asking — not a formula. No SQL, no table names required: the skill
mines the incidental hints ("from our subscriptions data") to *propose*
the matched columns and calculation, which you then approve or correct.
Full file: [`../examples/churn-metrics.csv`](../examples/churn-metrics.csv)

## The proposal

The README shows the Summary table; full per-metric detail plus open
questions follow it in the real output. Each proposed metric also gets a
small **fake-data preview table** showing
exactly what the output would look like — and when the grain is unclear
("a sense of volume"… total ever? per month?), the proposal shows 2–3
example tables to pick from instead of asking "what granularity do you
want?". Full file: [`../examples/proposal.md`](../examples/proposal.md)

## Once approved

Draft SQL + schema.yml, tests scaled to importance and reusing an existing
custom test where one fits:
[`draft__rpt_avg_payment_amount.sql`](../examples/draft__rpt_avg_payment_amount.sql) ·
[`draft___payments__models.yml`](../examples/draft___payments__models.yml)

## Under the hood

1. Parses the sheet, reading `reasoning` for candidate tables/columns and a
   rough shape of the calculation.
2. Detects your project's naming/materialization conventions
   (`dbt-bouncer.yml`, or sampled from existing marts) and surveys generic
   tests already in use — built-in, package, and custom — so it can reuse
   your project's own conventions instead of a generic default.
3. Grounds each candidate against `target/manifest.json` — **matched**,
   **ambiguous**, or **blocked**, never guessed. When `target/catalog.json`
   is present, a matched or ambiguous candidate also carries each column's
   real warehouse data type.
4. Checks whether the metric already exists as a live metric in your dbt
   Semantic Layer, when the project has one (`target/semantic_manifest.json`).
   A confident hit never gets silently duplicated as a new mart — it
   becomes an open question instead.
5. Writes a proposal (summary table + per-metric detail, `reasoning` shown
   verbatim next to its own proposed calculation, a "one row per ___"
   grain statement, the exact assertions a build will encode, and a
   fake-data preview of the output table — with 2–3 alternative shapes to
   pick from when the grain is unclear) and **stops for your approval** —
   nothing is built yet.
6. Once approved: writes draft SQL/schema.yml into `.dbt-martmaker/drafts/`,
   one metric at a time, tests scaled to each metric's `importance` and
   reusing an existing custom/package test where one already fits.
7. You review, then promote the drafts into `models/marts/` yourself.
