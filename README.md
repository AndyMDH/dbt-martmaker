<div align="center">
  <img src="assets/logo.svg" alt="dbt-martsmith" width="420">
</div>

<p align="center">
  Turn a metric requirements sheet into a draft dbt mart model
  (<code>dim_</code>/<code>fct_</code>/<code>rpt_</code>), grounded against
  models that already exist in your project. Draft-only — never commits,
  never runs <code>dbt build</code>/<code>run</code>/<code>test</code>.
</p>

<p align="center">
  <img src="examples/workflow.svg" alt="workflow" width="720">
</p>

## How it works

1. Fill out a small CSV: one row per metric — **metric, definition,
   calculation, source table(s)**. See [`examples/churn-metrics.csv`](examples/churn-metrics.csv).
2. It checks each source against your project's `target/manifest.json`.
   Outcome is always one of: matched, ambiguous (short candidate list), or
   blocked (nothing found) — never a guess.
3. It writes a proposal (`proposal.md`) plus skeleton mart SQL/schema.yml
   into an untracked draft folder, for you to review and promote yourself.
   See [`examples/proposal.md`](examples/proposal.md) for a sample.

Only builds from what's already staged (`models/staging`/`models/intermediate`).
A metric needing genuinely new source data comes back **blocked**, not guessed.

## Install (one time)

Requires a dbt project with `target/manifest.json` (run `dbt parse` once),
and an AI agent that reads Claude Code skills or `AGENTS.md`.

```bash
git clone https://github.com/AndyMDH/dbt-martsmith.git && ./dbt-martsmith/install.sh
```

## Usage

`cd` into your dbt project and just ask your agent:

> Set up a dbt-martsmith metric sheet for churn metrics, then run it.

The agent scaffolds the sheet with you, fills it in from the conversation,
grounds it, and writes the proposal + draft models — no manual file
juggling needed. Already have a sheet? *"Run dbt-martsmith on
.dbt-martsmith/sheets/churn-metrics.csv"* works too.

Output lands in `.dbt-martsmith/drafts/<name>/`. Nothing is committed or
built automatically — review, resolve open questions, then promote the
draft files into `models/marts/` yourself.

See [`docs/requirements-meeting-checklist.md`](docs/requirements-meeting-checklist.md)
for what makes a good Definition/Calculation entry.

## License

MIT — see [LICENSE](LICENSE).
