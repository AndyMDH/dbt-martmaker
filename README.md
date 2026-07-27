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
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-7C3AED"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/AndyMDH/dbt-martmaker?color=7C3AED&label=version"></a>
  <a href="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/AndyMDH/dbt-martmaker/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/AndyMDH/dbt-martmaker?color=7C3AED">
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

## Quickstart

`cd` into your dbt project and ask your agent:

> Set up a dbt-martmaker metric sheet for churn metrics, then run it.

It scaffolds `.dbt-martmaker/sheets/churn-metrics.csv` and fills it in with
you — one row per metric, in the stakeholder's own words, not SQL:

<p align="center">
  <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
</p>

From there it grounds every candidate table/column against your project's
own `target/manifest.json` (matched, ambiguous, or blocked — never
guessed) and writes a proposal for you to approve before anything is
drafted. Full walkthrough, including the proposal and drafted SQL/schema.yml:
[`docs/USAGE.md`](docs/USAGE.md).

## How it works, briefly

- **Mart layer only** — combines models that already exist in
  `models/staging/`/`models/intermediate/`; a metric needing a genuinely
  new raw source is flagged **blocked**, never attempted.
- **Grounds, never guesses** — every table/column reference is checked
  against `target/manifest.json`.
- **Stops for approval** — a proposal is written first; nothing is drafted
  into `.dbt-martmaker/drafts/` until you approve it.
- **Reuses your conventions** — naming/materialization and existing
  generic tests are detected from your project, not assumed.

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |

## License

MIT — see [LICENSE](LICENSE).
