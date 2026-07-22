<div align="center">
  <img src="assets/logo.svg" alt="dbt-martsmith" width="380">
</div>

<p align="center">
  Draft dbt mart models from a metric sheet — grounded in what already
  exists, never guessed. It's just a Claude Code skill.
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

## License

MIT
