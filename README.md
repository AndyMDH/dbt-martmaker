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

`cd` into your dbt project and ask your agent:

> Set up a dbt-martsmith metric sheet for churn metrics, then run it.

The sheet is one row per metric:

| Column | Required | Example |
|---|---|---|
| `metric` | yes | Payment count |
| `definition` | yes | Number of payments processed |
| `calculation` | yes | just a count of payments |
| `source_tables` | yes | payments |

Every source gets checked against `target/manifest.json` — **matched**,
**ambiguous**, or **blocked**, never guessed. Output lands in
`.dbt-martsmith/drafts/`: a proposal (starts with a summary table, same
shape as the input) + draft SQL/schema.yml for you to review and promote
into `models/marts/` yourself.

[Example sheet](examples/churn-metrics.csv) ·
[Sample output](examples/proposal.md) ·
[Meeting checklist](docs/requirements-meeting-checklist.md)

## Repo layout

| Path | What it is |
|---|---|
| `skills/dbt-martsmith/AGENTS.md` | The actual spec — every step the skill follows, in full |
| `skills/dbt-martsmith/SKILL.md`, `CLAUDE.md` | One-line imports of `AGENTS.md`, so different agent tools can discover it |
| `skills/dbt-martsmith/scripts/` | The deterministic parts: grounding + naming-convention detection |
| `examples/` | A filled-in sheet, sample output, and the workflow diagram |
| `docs/` | The requirements-meeting checklist |
| `tests/` | pytest suite for `scripts/` (the skill's own logic is verified by running it, not unit tested) |
| `install.sh` | Copies `skills/dbt-martsmith/` into your agent's skill folder |

## License

MIT
