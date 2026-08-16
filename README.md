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
`python skills/dbt-martmaker/scripts/doctor.py` first (path relative to
this repo; a plugin/skill install has `scripts/doctor.py` inside the
installed skill directory instead). It checks for `target/manifest.json`,
PyYAML, and a few optional extras, and tells you exactly what is missing.

## Quickstart

Six steps, start to finish:

1. `cd` into your dbt project and ask your agent:

   > Set up a dbt-martmaker metric sheet for churn metrics, then run it.

   This creates `.dbt-martmaker/sheets/churn-metrics.csv`. Each row holds
   one metric, described in the stakeholder's own words, not SQL
   ([full file](examples/churn-metrics.csv)):

   <p align="center">
     <img src="examples/sheet-preview.svg" alt="example metric sheet" width="780">
   </p>

2. Have the stakeholder fill in each row, or fill it in yourself from what
   they told you. No SQL required — just what the metric means and why
   they want it.
3. Ask your agent to run dbt-martmaker on the sheet (or say so in the same
   message as step 1). It checks every candidate table and column against
   your real project, and writes a proposal. **Nothing is built yet.**
4. Read the proposal. This is the summary table
   ([full file](examples/proposal.md)):

   <p align="center">
     <img src="examples/proposal-preview.svg" alt="example proposal summary table" width="900">
   </p>

   Resolve anything listed under Open Questions.
5. Reply to approve. Only now does the agent draft SQL and schema.yml
   files, into `.dbt-martmaker/drafts/`.
6. Review the drafted files. Drop the `draft__` prefix and move them into
   your real `models/marts/` yourself. dbt-martmaker never does this step
   for you.

Working with more than one sheet at once?
`python skills/dbt-martmaker/scripts/list_sheets.py <project_root>` shows
each one's status: no proposal yet, proposed, built, or stale.

For how grounding actually decides matched/ambiguous/blocked, and how the
glossary, corrections, embeddings, dbt Mesh, and escalation each fit into
that: [`AGENTS.md`](skills/dbt-martmaker/AGENTS.md#configuration-optional)
documents it step by step. [`docs/USAGE.md`](docs/USAGE.md) has the full
worked example, including the drafted SQL/schema.yml from step 6.

## How it works

Nine steps. Steps 0-5 run every time. Step 6 runs only after you approve
the proposal step 5 writes.

| Step | What happens | What runs |
|---|---|---|
| 0 | Find `dbt_project.yml` above the current directory. Checksum the sheet. | — |
| 1 | Read the sheet. For each row, mine the `reasoning` text for candidate tables, a proposed calculation, and the grain. | — (the agent reads the text itself) |
| 2 | Detect the mart naming pattern, the materialization default, and which generic tests the project already uses. | `scripts/detect_conventions.py <project_root>` |
| 3 | Match each candidate reference against real models in `target/manifest.json` — plus `target/catalog.json`, dbt Mesh manifests, your glossary, and past corrections, when present. | `scripts/ground.py <project_root> "<references>" "<metric>"` |
| 4 | Check whether the metric already exists as a live dbt Semantic Layer metric. | same `ground.py` call, its `semantic_layer` field |
| 5 | Check whether this row has already stayed unresolved for two sheet revisions in a row. Write `proposal.md`. **Stop and wait for approval.** | `scripts/escalation.py <project_root> <slug> "<metric>" <status> <checksum>` |
| 6 | Write `draft__<name>.sql` and its schema.yml entry. One metric at a time — SQL and tests together — for matched rows with a decided grain only. | — (runs only after you approve) |
| 7 | Write `meta.json`: the sheet's checksum and every row's status. | — |
| 8 | Print a summary: matched/ambiguous/blocked counts, and where the files went. | — |

Two read-only checks you can run any time, outside this flow:

- `scripts/doctor.py [start_dir]` — is this project ready? Checks for
  `target/manifest.json`, PyYAML, and a few optional extras.
- `scripts/list_sheets.py <project_root>` — status of every sheet already
  in `.dbt-martmaker/sheets/`.

Script paths above are relative to the installed skill directory. The
agent resolves them on its own; a human running one by hand needs the
full path — see [Install](#install).

## Documentation

| | |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Full walkthrough — example sheet, proposal, drafted SQL/schema.yml, and the under-the-hood steps. |
| [`skills/dbt-martmaker/AGENTS.md`](skills/dbt-martmaker/AGENTS.md) | The full spec this skill follows, step by step. |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, release by release. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Local development setup, the branch strategy, and how a release is tagged. |

## License

MIT — see [LICENSE](LICENSE).
