# dbt-scribe

Turn a structured metric requirements sheet into a draft dbt mart model
(`dim_`/`fct_`/`rpt_`) — grounded against the models that already exist in
your project, never guessed. Draft-only: it never commits, never runs
`dbt build`/`run`/`test`, and never touches your warehouse.

## What it does

1. You fill out a small CSV — one row per metric: **metric, definition,
   calculation, source table(s)**. (Or hand it a meeting transcript first
   and let it draft a candidate sheet for you to review — see below.)
2. It checks each source reference against your project's own
   `target/manifest.json` — does a matching staging/intermediate model
   already exist? Confident match, short list of candidates, or genuinely
   nothing found are the only three outcomes. It never invents a match.
3. It writes a proposal (grain, keys, what's grounded vs. still open) plus
   skeleton mart SQL/schema.yml — into an untracked draft folder, for you to
   review, edit, and promote yourself.

## Why a metric sheet, not a meeting transcript

Extracting structure from a rambling meeting transcript is the least
reliable part of this kind of tool — ambiguous phrasing, missing context,
an LLM having to get every extraction step right in one pass. A structured
sheet sidesteps that. If you do have a transcript, dbt-scribe can still
draft a *candidate* sheet from it — but that draft (`<slug>.draft.csv`) is
never used directly. You review and confirm it (rename off `.draft`) before
anything gets built from it. The risky step only ever produces something
low-stakes and editable.

## Why mart layer only

In a reasonably mature dbt project, staging and intermediate models already
cover raw sources 1:1. A new business ask is almost always "combine what's
already modeled into a new mart," not "wire up a brand-new raw source." So
dbt-scribe only builds `dim_`/`fct_`/`rpt_` models from what's already
staged. If a metric needs data that genuinely isn't staged anywhere yet,
that row comes back **blocked** — flagged, not guessed at. Building new
staging models/sources is out of scope for this tool.

## Install

Prerequisites:
- A dbt project where `dbt parse` has been run at least once (so
  `target/manifest.json` exists).
- PyYAML available in whatever environment runs the skill's scripts
  (already a dbt dependency in virtually every dbt project).
- An AI coding agent that supports either Claude Code's skill format or
  reads `AGENTS.md`/`CLAUDE.md` (Claude Code, Claude Desktop, Cursor, etc.).

```bash
git clone https://github.com/<you>/dbt-scribe.git
cd dbt-scribe
./install.sh              # symlinks into ~/.claude/skills/dbt-scribe (global)
# or: ./install.sh --project   (current project's .claude/skills/ only)
```

## Usage

```bash
cd your-dbt-project
mkdir -p .dbt-scribe/sheets
cp ~/.claude/skills/dbt-scribe/templates/metric_sheet.csv.tmpl \
   .dbt-scribe/sheets/churn-metrics.csv
# edit churn-metrics.csv with your actual metrics
```

Then, in your agent: *"Run dbt-scribe on .dbt-scribe/sheets/churn-metrics.csv"*

Output lands in `.dbt-scribe/drafts/churn-metrics/proposal.md` plus draft
model files under `.dbt-scribe/drafts/churn-metrics/models/`. Nothing is
committed or built automatically — review the proposal, resolve any open
questions, then manually promote the draft files into `models/marts/`.

If you have a transcript instead of a filled sheet, ask your agent: *"Draft
a dbt-scribe metric sheet from this transcript: <path>"* — review the
resulting `.draft.csv`, correct it, rename off `.draft`, then run it as
above.

See [`docs/requirements-meeting-checklist.md`](docs/requirements-meeting-checklist.md)
for what makes a good Definition/Calculation entry — useful to bring into
the meeting itself, before you ever open the sheet.

## Why this exists (design rationale)

**Why a skill, not a dbt package.** A dbt package (`dbt_utils`,
`dbt_expectations`, `dbt-codegen`, `dbt-erd`) is Jinja/SQL executed by dbt's
own deterministic engine — it has no capacity for the judgment calls this
tool makes (which existing model a metric should extend, how to phrase an
open question). That requires language understanding, so this ships as an
agent skill: instructions run by whatever LLM/agent you already have open.
No server to host, no API key to manage.

**Why grounding is mandatory, never optional.** A wrong guess here is a
schema decision baked into your warehouse, not a mistagged note. If
`target/manifest.json` doesn't exist, the skill errors out rather than
drafting from the sheet's prose alone. Matched, Ambiguous, or Blocked are
the only three outcomes — never a silent guess.

**Why conventions are detected, not assumed.** Naming, materialization, and
property-file conventions differ per project — sometimes even
inconsistently *within* one project. dbt-scribe reads your `dbt-bouncer.yml`
if you have one, or samples your existing marts files, rather than
hardcoding one house style.

**Why manual-trigger and draft-only.** No file watcher, no auto-commit, no
auto-PR. Every artifact lands in an untracked `.dbt-scribe/` folder for a
human to review and promote. Blast radius stays near zero while the tool
earns trust.

**Why it doesn't do ERD/graph visualization.**
[dbt-erd](https://github.com/) already solves that well — no need to
duplicate it here.

## Out of scope (for now)

- Building staging models or declaring new `source()`s for genuinely new
  raw data — explicitly punted; a `blocked` row is the correct behavior,
  not a gap.
- Semantic Layer / `metrics.yml` drafting (most valuable on dbt Cloud
  projects with the Semantic Layer wired up).
- Multi-sheet continuity (merging a revised sheet into an existing draft).
- Full contract-diffing and adapter-gating awareness beyond flagging that
  they're present.

## License

MIT — see [LICENSE](LICENSE).
