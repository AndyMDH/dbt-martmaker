<div align="center">
  <img src="assets/logo.svg" alt="dbt-martmaker" width="380">
</div>

<p align="center">
  Turns a metric requirements sheet into a draft dbt mart model
  (<code>dim_</code>/<code>fct_</code>/<code>rpt_</code>), grounded against
  your project's own <code>target/manifest.json</code>. An <b>agent
  skill</b> — instructions Claude Code (or any <code>AGENTS.md</code>-reading
  agent) follows directly. No package, no server, no CLI binary.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-C2410C"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/AndyMDH/dbt-martmaker?color=C2410C&label=version"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/AndyMDH/dbt-martmaker?color=C2410C">
</p>

<p align="center">
  <img src="examples/workflow.svg" alt="workflow" width="720">
</p>

## Install

```
/plugin marketplace add AndyMDH/dbt-martmaker
/plugin install dbt-martmaker
```

That is a normal Claude Code plugin install — no clone, no script, and
`/plugin update dbt-martmaker` picks up new releases. Requires a dbt
project with `target/manifest.json` (`dbt parse`).

Working in one repo only, or not using the plugin system? Clone and run
`./install.sh --project` instead — see [`install.sh`](install.sh) for the
project-scoped and copy-instead-of-symlink variants.

## Quickstart

`cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

That scaffolds `.dbt-martmaker/sheets/churn-metrics.csv` — one row per
metric, in the stakeholder's own words, not SQL
([full file](examples/churn-metrics.csv)):

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

Each candidate table/column is then grounded against `target/manifest.json`
— **matched**, **ambiguous**, or **blocked**, never guessed — and a
proposal is written that **stops for your approval** before anything is
drafted. This is the proposal's summary table
([full file](examples/proposal.md)):

<p align="center">
  <img src="examples/proposal-preview.svg" alt="example proposal summary table" width="900">
</p>

Full walkthrough — per-metric detail, drafted SQL/schema.yml once
approved, and the under-the-hood steps: [`docs/USAGE.md`](docs/USAGE.md).

## Scope

- **Mart layer only** — combines models that already exist in
  `models/staging/`/`models/intermediate/`; a metric needing a genuinely
  new raw source is flagged **blocked**, never attempted.
- **Checks the dbt Semantic Layer first** — if your project runs
  MetricFlow, a metric that already exists there is flagged, never
  silently duplicated as a new physical mart.
- **Reuses your conventions** — naming/materialization and existing
  generic tests (built-in, package, or custom) are detected from your
  project, not assumed.
- **Never runs dbt** — no `dbt build`/`run`/`test`; output is a proposal
  doc plus draft SQL/schema.yml for you to review and promote yourself.

## Utilities

Two read-only status checks, outside the main propose-then-build flow:

- `scripts/doctor.py [start_dir]` — is this project ready? Checks for
  `target/manifest.json`, PyYAML, and (as enrichment, never blocking)
  `catalog.json`/`semantic_manifest.json`/`dbt-bouncer.yml`. Run this
  first if you're not sure the skill has what it needs.
- `scripts/list_sheets.py <project_root>` — status of every sheet in
  `.dbt-martmaker/sheets/`: no proposal yet / proposed / built / stale.

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, release by release. |

## License

MIT — see [LICENSE](LICENSE).
