# dbt-martsmith

Turn a metric requirements sheet into a draft dbt mart model
(`dim_`/`fct_`/`rpt_`), grounded against models that already exist in your
project. A plain CLI — no LLM, no agent, fully deterministic.

![workflow](examples/workflow.svg)

## Install

Requires a dbt project with `target/manifest.json` present (run `dbt parse`
once).

```bash
pip install git+https://github.com/AndyMDH/dbt-martsmith.git
```

## Usage

```bash
cd your-dbt-project
dbt-martsmith init churn-metrics
# fill in .dbt-martsmith/sheets/churn-metrics.csv — see examples/churn-metrics.csv
dbt-martsmith run .dbt-martsmith/sheets/churn-metrics.csv
```

Each row is checked against your project's `target/manifest.json`. Outcome
is always one of: **matched**, **ambiguous** (short candidate list), or
**blocked** (nothing found) — never a guess.

Output lands in `.dbt-martsmith/drafts/churn-metrics/`:
- `proposal.md` — one section per metric, grounding result, open questions.
  See [`examples/proposal.md`](examples/proposal.md) for a sample.
- `models/draft__*.sql` + `.yml` — skeleton mart files, matched rows only.

Nothing is committed or run automatically. Review the proposal, resolve
open questions, then promote the draft files into `models/marts/` yourself.

Only builds from what's already staged (`models/staging`/`models/intermediate`).
A metric needing genuinely new source data comes back **blocked**, not guessed.

See [`docs/requirements-meeting-checklist.md`](docs/requirements-meeting-checklist.md)
for what makes a good Definition/Calculation entry.

## License

MIT — see [LICENSE](LICENSE).
