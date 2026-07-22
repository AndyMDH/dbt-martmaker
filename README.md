<div align="center">
  <img src="assets/logo.svg" alt="dbt-martsmith" width="380">
</div>

<p align="center">
  Describe the metrics you need in plain language — dbt-martsmith checks
  what already exists in your dbt project and drafts a mart model for you
  to review. It's an <b>agent skill</b>: instructions your AI coding
  assistant (Claude Code, etc.) follows directly, not a program you install
  or a server you run.
</p>

<p align="center">
  <img src="examples/workflow.svg" alt="workflow" width="720">
</p>

## Install

```bash
git clone https://github.com/AndyMDH/dbt-martsmith.git && ./dbt-martsmith/install.sh
```

Requires a dbt project with `target/manifest.json` (`dbt parse`), and an
agent that reads Claude Code skills or `AGENTS.md`.

## Usage

**First time setup:** `cd` into your dbt project and ask your agent:

> Set up a dbt-martsmith metric sheet for churn metrics, then run it.

It scaffolds `.dbt-martsmith/sheets/churn-metrics.csv` and fills it in with
you. After that: edit that sheet, or start a new one, and tell your agent
to run it.

**Example sheet** — one row per metric, in the stakeholder's own words, not
SQL: [`examples/churn-metrics.csv`](examples/churn-metrics.csv)

| Column | Required | Example |
|---|---|---|
| `metric` | yes | Marketing ROI |
| `description` | yes | How efficient our marketing spend is |
| `reasoning` | yes | compare what we spent on ads against the revenue it brought in - probably need ad spend and revenue numbers |
| `importance` | yes (`low`/`medium`/`high`) | medium |

`reasoning` is deliberately loose — no SQL, no table names required. It's
what the skill mines to *propose* the matched columns and calculation,
which you then approve or correct.

**Output** — a proposal, then approved draft models:
[`examples/proposal.md`](examples/proposal.md)

**Under the hood:**
1. Parses the sheet, reading `reasoning` for candidate tables/columns and a
   rough shape of the calculation.
2. Detects your project's naming/materialization conventions
   (`dbt-bouncer.yml`, or sampled from existing marts).
3. Grounds each candidate against `target/manifest.json` — **matched**,
   **ambiguous**, or **blocked**, never guessed.
4. Writes a proposal (summary table + per-metric detail, `reasoning` shown
   verbatim next to its own proposed/inferred calculation) and **stops for
   your approval** — nothing is built yet.
5. Once approved: writes draft SQL/schema.yml into `.dbt-martsmith/drafts/`,
   tests scaled to each metric's `importance`.
6. You review, then promote the drafts into `models/marts/` yourself.

## License

MIT
