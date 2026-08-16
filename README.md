<div align="center">
  <img src="assets/logo.svg" alt="dbt-martmaker" width="380">
</div>

<p align="center">
  dbt-martmaker turns a metric requirements sheet into a draft dbt mart
  model (<code>dim_</code>/<code>fct_</code>/<code>rpt_</code>). It grounds
  every match against your project's own <code>target/manifest.json</code>
  — it never guesses.
</p>

<p align="center">
  This is an agent skill, not a package or a hosted service. Claude Code
  (or any <code>AGENTS.md</code>-reading agent) follows these instructions
  directly, calling a few small Python scripts along the way.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-C2410C"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/AndyMDH/dbt-martmaker?color=C2410C&label=version"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/AndyMDH/dbt-martmaker?color=C2410C">
</p>

<p align="center">
  <img src="examples/workflow.svg" alt="workflow" width="900">
</p>

## Why

Analytics teams get metric requests in Slack threads, emails, and hallway
conversations. Turning one into a real dbt model takes real work, even for
a simple metric. An engineer must find the right staging model, infer a
calculation from a vague description, and pick the right tests.

dbt-martmaker moves that first pass into a structured sheet. A stakeholder
fills it out alone, with no SQL required. The tool grounds every claim
against your actual project, and stops for your approval before it writes
a single file.

## Install

```
/plugin marketplace add AndyMDH/dbt-martmaker
/plugin install dbt-martmaker
```

This is a normal Claude Code plugin install. It needs no clone and no
script, and `/plugin update dbt-martmaker` picks up new releases. It needs
a dbt project with a `target/manifest.json` file. If the project has none
yet, run `dbt parse` first.

To use it in one repo only, or without the plugin system, clone the repo
and run `./install.sh --project`. See [`install.sh`](install.sh) for the
project-scoped and copy-instead-of-symlink options.

Not sure the project has everything the skill needs? Run
`python scripts/doctor.py` first — see [Utilities](#utilities).

## Quickstart

`cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

That command creates `.dbt-martmaker/sheets/churn-metrics.csv`. Each row
holds one metric, described in the stakeholder's own words, not SQL
([full file](examples/churn-metrics.csv)):

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

The tool grounds each candidate table and column against
`target/manifest.json`. Every result is **matched**, **ambiguous**, or
**blocked** — never guessed. It then writes a proposal and stops for your
approval before it drafts anything. This is the proposal's summary table
([full file](examples/proposal.md)):

<p align="center">
  <img src="examples/proposal-preview.svg" alt="example proposal summary table" width="900">
</p>

Full walkthrough — per-metric detail, drafted SQL/schema.yml once
approved, and the under-the-hood steps: [`docs/USAGE.md`](docs/USAGE.md).

## Scope

- **Mart layer only.** It combines models that already exist in
  `models/staging/` and `models/intermediate/` — plus, when configured,
  public models from a sibling dbt Mesh project. A metric that needs a new
  raw source is flagged **blocked**, never attempted.
- **Checks the dbt Semantic Layer first.** If your project runs
  MetricFlow, a metric that already exists there is flagged. It is never
  duplicated as a new physical mart.
- **Never guesses, and gets sharper over time.** Every match is
  **matched**, **ambiguous**, or **blocked** — never invented. A project
  can teach it its own vocabulary (`glossary.yml`), and every human
  correction is remembered for next time (`corrections.jsonl`). An
  optional embeddings API adds one more signal, never a way to auto-match
  on its own. See [Matching](#matching).
- **Reuses your project's conventions.** Naming, materialization, and
  existing generic tests come from your project. Nothing is assumed.
- **Never runs dbt.** It never runs `dbt build`, `run`, or `test`. The
  output is a proposal plus draft SQL and schema.yml, for you to review
  and promote yourself.

## Matching

Grounding starts with token overlap between your reference and the real
model names, columns, and descriptions in `target/manifest.json`. Three
optional layers make it sharper without changing what "matched" means —
no layer can lower the bar, only widen what gets found:

- **`.dbt-martmaker/glossary.yml`** — your own synonym pairs, on top of a
  small built-in list. Add a pair here when a real stakeholder term keeps
  reading as blocked against a model that names the same thing
  differently.
- **`.dbt-martmaker/corrections.jsonl`** — append-only, one line per human
  correction. Checked before every future run of that exact reference, so
  the tool never makes the same wrong match twice.
- **`VOYAGE_API_KEY`** — set this to enable embedding-based similarity via
  the Voyage AI API. It can lift a `blocked` reference to `ambiguous` when
  it finds something token overlap missed, and it can attach a confidence
  score to an existing match — but it can never auto-match by itself.
  Absent the key, or on any API failure, grounding runs exactly as it
  does offline.

Running dbt Mesh? List sibling projects in
`.dbt-martmaker/mesh_manifests.yml`, and their public models join the
candidate pool too. Full detail on all four:
[`skills/dbt-martmaker/AGENTS.md`](skills/dbt-martmaker/AGENTS.md#configuration-optional).

## Utilities

Two read-only status checks, outside the main propose-then-build flow:

- **`scripts/doctor.py [start_dir]`** — a readiness check. It reports
  whether `target/manifest.json` and PyYAML are present. It also reports
  `catalog.json`, `semantic_manifest.json`, and `dbt-bouncer.yml` as
  optional enrichment, never blocking. Run this first when it is unclear
  whether the project has what the skill needs.
- **`scripts/list_sheets.py <project_root>`** — the status of every sheet
  in `.dbt-martmaker/sheets/`: no proposal yet, proposed, built, or stale.

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, release by release. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Local development setup, the branch strategy, and how a release is tagged. |

## License

MIT — see [LICENSE](LICENSE).
