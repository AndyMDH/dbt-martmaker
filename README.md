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

**First time:** `cd` into your dbt project and ask your agent:

> Set up a dbt-martsmith metric sheet for churn metrics, then run it.

It scaffolds `.dbt-martsmith/sheets/churn-metrics.csv` — one row per metric,
filled in with you (the stakeholder's own words, not SQL):

| Column | Required | Example |
|---|---|---|
| `metric` | yes | Payment count |
| `definition` | yes | Number of payments processed |
| `calculation` | yes | just a count of payments |
| `source_tables` | yes | payments |
| `importance` | yes (`low`/`medium`/`high`) | low |

**Every time after:** edit that sheet, or ask for a new one, and tell your
agent to run it.

**Under the hood:** each source is checked against `target/manifest.json` —
**matched**, **ambiguous**, or **blocked**, never guessed. The skill then
**stops and shows you a proposal** (summary table + per-metric detail) —
nothing is built until you approve it. Once approved, draft SQL/schema.yml
land in `.dbt-martsmith/drafts/`, tests scaled to each metric's
`importance`, for you to review and promote into `models/marts/` yourself.

[Example sheet](examples/churn-metrics.csv) ·
[Sample output](examples/proposal.md)

## Repo layout

| Path | What it is |
|---|---|
| `skills/dbt-martsmith/AGENTS.md` | The actual spec — every step the skill follows, in full |
| `skills/dbt-martsmith/SKILL.md`, `CLAUDE.md` | One-line imports of `AGENTS.md`, so different agent tools can discover it |
| `skills/dbt-martsmith/scripts/` | The deterministic parts: grounding + naming-convention detection |
| `examples/` | A filled-in sheet, sample output, and the workflow diagram |
| `tests/` | pytest suite for `scripts/` (the skill's own logic is verified by running it, not unit tested) |
| `install.sh` | Copies `skills/dbt-martsmith/` into your agent's skill folder |

## License

MIT
