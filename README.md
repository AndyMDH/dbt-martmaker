# dbt-martsmith

Turn a metric requirements sheet into a draft dbt mart model
(`dim_`/`fct_`/`rpt_`), grounded against models that already exist in your
project. Draft-only — never commits, never runs `dbt build`/`run`/`test`.

![workflow](examples/workflow.svg)

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

## Install

Requires: a dbt project with `target/manifest.json` (run `dbt parse` once),
and an AI agent that reads Claude Code skills or `AGENTS.md`.

```bash
git clone https://github.com/AndyMDH/dbt-martsmith.git
cd dbt-martsmith
./install.sh              # ~/.claude/skills/dbt-martsmith (global)
# or: ./install.sh --project
```

## Usage

```bash
cd your-dbt-project
mkdir -p .dbt-martsmith/sheets
cp ~/.claude/skills/dbt-martsmith/templates/metric_sheet.csv.tmpl \
   .dbt-martsmith/sheets/churn-metrics.csv
# fill in your metrics
```

Then ask your agent: *"Run dbt-martsmith on
.dbt-martsmith/sheets/churn-metrics.csv"*

Output lands in `.dbt-martsmith/drafts/churn-metrics/`. Nothing is committed
or built automatically — review, resolve open questions, then promote the
draft files into `models/marts/` yourself.

See [`docs/requirements-meeting-checklist.md`](docs/requirements-meeting-checklist.md)
for what makes a good Definition/Calculation entry.

## License

MIT — see [LICENSE](LICENSE).
