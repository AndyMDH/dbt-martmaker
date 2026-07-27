<div align="center">
  <img src="assets/logo.svg" alt="dbt-martmaker" width="380">
</div>

<p align="center">
  Describe the metrics you need in plain language — dbt-martmaker checks
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
git clone https://github.com/AndyMDH/dbt-martmaker.git && ./dbt-martmaker/install.sh
```

This isn't a published package (no PyPI/npm equivalent for Claude Code
skills) — `install.sh` just automates getting `skills/dbt-martmaker/` into
`~/.claude/skills/` (or a project's `.claude/skills/`). You can just as
well skip cloning and copy that one folder there by hand; the only thing
you lose is `install.sh`'s symlink mode, which keeps the skill in sync
with a `git pull`.

Requires a dbt project with `target/manifest.json` (`dbt parse`), and an
agent that reads Claude Code skills or `AGENTS.md`.

## Usage

**First time setup:** `cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

It scaffolds `.dbt-martmaker/sheets/churn-metrics.csv` and fills it in with
you. After that: edit that sheet, or start a new one, and tell your agent
to run it.

**Example sheet** — one row per metric, in the stakeholder's own words, not
SQL:

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

`reasoning` is the stakeholder's *why* — the decision the metric feeds,
who's asking — not a formula. No SQL, no table names required: the skill
mines the incidental hints ("from our subscriptions data") to *propose*
the matched columns and calculation, which you then approve or correct. Full file:
[`examples/churn-metrics.csv`](examples/churn-metrics.csv)

**Output** — a proposal (this is the Summary table; full detail plus open
questions below it):

<p align="center">
  <img src="examples/proposal-preview.svg" alt="example proposal summary table" width="900">
</p>

Each proposed metric also gets a small **fake-data preview table** showing
exactly what the output would look like — and when the grain is unclear
("a sense of volume"… total ever? per month?), the proposal shows 2–3
example tables to pick from instead of asking "what granularity do you
want?". Full file: [`examples/proposal.md`](examples/proposal.md)

**Once approved** — draft SQL + schema.yml, tests scaled to importance and
reusing an existing custom test where one fits:
[`draft__rpt_avg_payment_amount.sql`](examples/draft__rpt_avg_payment_amount.sql) ·
[`draft___payments__models.yml`](examples/draft___payments__models.yml)

**Under the hood:**
1. Parses the sheet, reading `reasoning` for candidate tables/columns and a
   rough shape of the calculation.
2. Detects your project's naming/materialization conventions
   (`dbt-bouncer.yml`, or sampled from existing marts) and surveys generic
   tests already in use — built-in, package, and custom — so it can reuse
   your project's own conventions instead of a generic default.
3. Grounds each candidate against `target/manifest.json` — **matched**,
   **ambiguous**, or **blocked**, never guessed.
4. Writes a proposal (summary table + per-metric detail, `reasoning` shown
   verbatim next to its own proposed calculation, a "one row per ___"
   grain statement, tests, and a fake-data preview of the output table —
   with 2–3 alternative shapes to pick from when the grain is unclear)
   and **stops for your approval** — nothing is built yet.
5. Once approved: writes draft SQL/schema.yml into `.dbt-martmaker/drafts/`,
   tests scaled to each metric's `importance` and reusing an existing
   custom/package test where one already fits.
6. You review, then promote the drafts into `models/marts/` yourself.

## License

MIT
