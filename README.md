<div align="center">
  <img src="assets/logo.svg" alt="dbt-martmaker" width="380">
</div>

<p align="center">
  dbt-martmaker turns a metric requirements sheet into a draft dbt mart
  model (<code>dim_</code>/<code>fct_</code>/<code>rpt_</code>). It grounds
  every match against your project's own <code>target/manifest.json</code>
  and never guesses.
</p>

<p align="center">
  This is an agent skill. Claude Code, or any <code>AGENTS.md</code>-reading
  agent, follows these instructions directly and calls a few small Python
  scripts along the way. There is no package to install and no service to
  run.
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
a simple metric. An engineer has to find the right staging model, infer a
calculation from a vague description, and pick the right tests.

dbt-martmaker moves that first pass into a structured sheet that a
stakeholder can fill out alone, with no SQL required. It only combines
models you already have in `models/staging/` and `models/intermediate/`
(plus public models from a sibling project, if you run dbt Mesh). A metric
that needs a genuinely new raw source stays **blocked**, not attempted,
and the tool never runs `dbt build`, `run`, or `test` on your behalf.

It also knows the difference between "this needs another look at the
sheet" and "this needs an actual conversation," and says so, rather than
asking the same written question a third time.

## Install

```
/plugin marketplace add AndyMDH/dbt-martmaker
/plugin install dbt-martmaker
```

This installs dbt-martmaker as a Claude Code plugin. It needs a dbt
project with a `target/manifest.json` file. If the project has none yet,
run `dbt parse` first.

Not sure the project has everything the skill needs? Run
`python scripts/doctor.py` first. It checks for `target/manifest.json`,
PyYAML, and a few optional extras, and tells you exactly what is missing.

## Quickstart

`cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

That creates `.dbt-martmaker/sheets/churn-metrics.csv`. Each row holds one
metric, described in the stakeholder's own words, not SQL
([full file](examples/churn-metrics.csv)):

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

The tool grounds each candidate table and column against
`target/manifest.json`, and against your dbt Semantic Layer too, if you
run one. Every result comes back **matched**, **ambiguous**, or
**blocked**. A project can teach it new vocabulary, remember past
corrections, and opt into embedding-based matching as one more signal,
but none of that can auto-match on its own — the tool still asks before
it drafts anything. This is the proposal's summary table
([full file](examples/proposal.md)):

<p align="center">
  <img src="examples/proposal-preview.svg" alt="example proposal summary table" width="900">
</p>

Working with more than one sheet at once? `python scripts/list_sheets.py
<project_root>` shows each one's status: no proposal yet, proposed, built,
or stale.

Full walkthrough — per-metric detail, drafted SQL/schema.yml once
approved, and the under-the-hood steps: [`docs/USAGE.md`](docs/USAGE.md).
Everything above (the glossary, corrections, embeddings, dbt Mesh, and how
escalation works) is documented step by step in
[`AGENTS.md`](skills/dbt-martmaker/AGENTS.md#configuration-optional).

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |
| [`skills/dbt-martmaker/AGENTS.md`](skills/dbt-martmaker/AGENTS.md) | The full spec this skill follows, step by step. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, release by release. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Local development setup, the branch strategy, and how a release is tagged. |

## License

MIT — see [LICENSE](LICENSE).
