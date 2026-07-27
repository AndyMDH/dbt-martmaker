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
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-7C3AED"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/AndyMDH/dbt-martmaker?color=7C3AED&label=version"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/AndyMDH/dbt-martmaker?color=7C3AED">
</p>

<p align="center">
  <img src="examples/workflow.svg" alt="workflow" width="720">
</p>

## Install

```bash
git clone https://github.com/AndyMDH/dbt-martmaker.git && ./dbt-martmaker/install.sh
```

- No package registry involved — `install.sh` just puts
  `skills/dbt-martmaker/` into `~/.claude/skills/` (or a project's
  `.claude/skills/`), symlinked by default so `git pull` keeps it current.
- Copying that one folder there by hand works identically; `--copy` mode
  or `--project` scope it to a copy or a single repo instead.
- Requires a dbt project with `target/manifest.json` (`dbt parse`), and an
  agent that reads Claude Code skills or `AGENTS.md`.

## Quickstart

`cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

That scaffolds `.dbt-martmaker/sheets/churn-metrics.csv` — one row per
metric, in the stakeholder's own words, not SQL:

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

- Each candidate table/column is grounded against `target/manifest.json`
  — **matched**, **ambiguous**, or **blocked**, never guessed.
- A proposal is written and **stops for your approval** before anything
  is drafted.

Full walkthrough, including the proposal and drafted SQL/schema.yml:
[`docs/USAGE.md`](docs/USAGE.md).

## Scope

- **Mart layer only** — combines models that already exist in
  `models/staging/`/`models/intermediate/`; a metric needing a genuinely
  new raw source is flagged **blocked**, never attempted.
- **Reuses your conventions** — naming/materialization and existing
  generic tests (built-in, package, or custom) are detected from your
  project, not assumed.
- **Never runs dbt** — no `dbt build`/`run`/`test`; output is a proposal
  doc plus draft SQL/schema.yml for you to review and promote yourself.

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |

## License

MIT — see [LICENSE](LICENSE).
