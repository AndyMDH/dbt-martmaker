# dbt-martsmith

Turns a structured metric requirements sheet into a draft dbt mart model
(`dim_`/`fct_`/`rpt_`) for human review. Never writes to a real `models/`
directory, never runs `dbt build`/`run`/`test`, never guesses a match it
can't confirm — and never generates draft files without explicit approval
of the proposal first.

Project root is the directory containing `dbt_project.yml`. All paths below
are relative to it unless stated otherwise.

## Scope

**Mart layer only.** This tool builds `dim_`/`fct_`/`rpt_` models by
combining models that already exist in `models/staging/` and
`models/intermediate/`. It does not create new staging models and does not
declare new `source()` blocks. If a metric needs raw data that isn't staged
yet anywhere in the project, that row is **BLOCKED** — flag it and move on,
never attempt it.

## Input: the metric sheet

The sheet is meant to be filled out by the stakeholder who wants the
metric, not just an engineer — keep that in mind if you're helping someone
draft one conversationally. It lives at `.dbt-martsmith/sheets/<slug>.csv`,
with columns: `metric`, `description`, `reasoning`, `importance`.

- `metric` — a short name, e.g. "Marketing ROI".
- `description` — one line, plain language, what it means.
- `reasoning` — the stakeholder's own free-form explanation of what they're
  thinking: what data it probably involves, roughly how they'd calculate
  it, why they need it. **This is not a formula and not a table name** —
  it's the raw material *you* (the agent) mine in Steps 1 and 3 to figure
  out which real columns/tables are involved and what the actual
  calculation should be. The stakeholder should never have to already know
  SQL or your project's schema to fill this in.
- `importance` — one of `low`/`medium`/`high`, set by the stakeholder based
  on how critical the metric is. Drives how much test rigor gets drafted in
  Step 5. If blank, treat as `medium` rather than erroring — don't make a
  stakeholder think hard about this column to use the tool.

## Two-phase flow: propose, then build on approval

This skill never jumps straight from a sheet to draft SQL files. It always
stops after Step 4 and shows the stakeholder/human a proposal to approve
first — only after they confirm does Step 5 actually write any files. This
matters more now than it would for a literal input: `reasoning` is
deliberately vague, so what Step 3/4 propose as the matched column and
calculation is a genuine inference on your part, not a transcription of
what the stakeholder wrote — they need to see and confirm it before
anything gets built.

State lives in `.dbt-martsmith/drafts/<slug>/meta.json`, with a `status`
field of `proposed` or `built`:

- **No `meta.json`, or its `sheet_checksum` doesn't match the current
  sheet**: this is a fresh (re-)proposal. Run Steps 0–4, write
  `meta.json` with `status: proposed`, then **stop** — do not run Step 5.
  End your turn by asking something like: *"Here's the proposal — want me
  to build the draft SQL/schema.yml files for the matched rows?"*
- **`meta.json` exists, checksum matches, `status: proposed`, and the
  human has just approved** (in this conversation, or by asking you to
  build it in a new one): run Step 5, then update `meta.json` to
  `status: built` and `proposal.md`'s frontmatter to match.
- **`meta.json` exists, checksum matches, `status: built`**: no-op. Print
  `SKIPPED: <slug>.csv already built (<drafts_dir>)` and stop.

If the sheet changed since the last proposal (checksum mismatch), always
re-ground and re-propose from scratch — never build from stale grounding
results.

## Step 0 — Locate & checksum

Walk upward from the current working directory until a `dbt_project.yml` is
found; that's the project root. If none is found within a reasonable number
of parent directories, **ERROR**: `No dbt_project.yml found — dbt-martsmith
must be run from inside a dbt project.` Stop; do not guess a root.

Compute a checksum (e.g. sha256) of the sheet's contents.

Derive `<slug>` from the sheet's filename (without extension).

## Step 1 — Parse sheet rows and read the reasoning

Read the CSV. Required columns: `metric`, `description`, `reasoning`,
`importance`. If any are missing, **ERROR**: `Sheet is missing required
column(s): <list>` and stop — do not try to proceed with partial columns.

For each row, read the `reasoning` text and identify what it implies:
candidate entities/tables it's talking about (these become the reference
strings you pass to `ground.py` in Step 3), and a rough shape of the
calculation (this becomes your **Proposed calculation** in Step 4 — an
inference, not something lifted verbatim from the sheet, since the
stakeholder never wrote a formula). Working item per row: metric name,
description text, reasoning text (kept verbatim for the proposal), your
extracted candidate reference(s), your proposed calculation, and importance
(`low`/`medium`/`high`, defaulting to `medium` if blank).

## Step 2 — Detect mart-layer conventions

Run `scripts/detect_conventions.py <project_root>`. It returns the naming
pattern for `models/marts` (from `dbt-bouncer.yml` if present, else sampled
from existing filenames), the materialization default for marts (from
`dbt_project.yml`), and the property-file naming pattern sampled from
whichever marts subdirectory already has files in it.

If the marts folder is empty and nothing can be sampled, do not invent a
convention — note it as an open question in the proposal instead
(`No existing marts to sample a naming convention from — confirm the
prefix/materialization convention to use.`).

Cache the result at `.dbt-martsmith/conventions.cache.json`, keyed on the
mtime of `dbt-bouncer.yml` and `dbt_project.yml`; re-run detection only if
either has changed since the cache was written.

## Step 3 — Ground each row

For each row, run `scripts/ground.py <project_root> "<candidate references
from Step 1>"`. It reads `target/manifest.json` (and `target/catalog.json`
if present) and returns one of:

- **`matched`**: one confident hit — a real staging/intermediate model
  name and its columns.
- **`ambiguous`**: a shortlist of up to 10 candidates, none confident
  enough to pick automatically.
- **`blocked`**: no candidates at all.

Treat `ground.py`'s output as ground truth over your own reading of the
reasoning text — do not override a `blocked` result with a guess about
what the stakeholder probably meant, and do not silently pick one shortlist
candidate over another. For `ambiguous`, you may reason about which
shortlist candidate is the better fit given the row's `reasoning`, but if
it's still not clear, put it in Open Questions rather than picking.

If `ground.py` reports that `dbt-mcp` is configured and reachable
(see its own output), you may additionally call its `get_lineage_dev` /
`get_node_details_dev` tools on a matched model for richer detail
(contract/constraints, adapter tags) to include in the proposal. Treat this
purely as enrichment — never required, never a substitute for the
manifest-based match.

If the dbt project has no `target/manifest.json` at all, **ERROR**:
`No target/manifest.json found — run 'dbt parse' in this project first.`
Do not fall back to guessing from the sheet's prose alone.

**Never call `dbt build`, `dbt run`, or `dbt test`** — grounding is always
read-only.

## Step 4 — Draft the proposal (stop here for approval)

Using `templates/proposal.md.tmpl`, write
`.dbt-martsmith/drafts/<slug>/proposal.md` with `status: proposed` in its
frontmatter. Start with a **Summary table** (Metric | Column used |
Description | Proposed calculation | Importance | Status), one row per
metric in the same order as the sheet — "Column used" is the matched model
name (or blank for Ambiguous/Blocked), "Proposed calculation" is your
inference from Step 1, not the raw sheet text. This is the artifact the
stakeholder actually approves, so it needs to show what they'll recognize,
not just an engineering status code.

Then one section per metric row with the full detail: description, the
stakeholder's **reasoning** (verbatim, never edited), your **proposed
calculation** (clearly labeled as your inference, not theirs), importance,
grounding result and status (Matched/Ambiguous/Blocked), and — for
Matched/resolved rows — the proposed new mart file path and a one-line
grain statement.

Every row that is `ambiguous` (and unresolved) or `blocked` becomes an Open
Questions checklist line. Never omit a row because it was hard to resolve.

This is where you stop (see "Two-phase flow" above) — do not proceed to
Step 5 in the same turn unless the human has already told you to build it.

## Step 5 — Draft skeleton model files (only after approval)

Only for rows that ended up Matched or resolved-Ambiguous. For each:

- Write `.dbt-martsmith/drafts/<slug>/models/draft__<name>.sql` using
  `templates/model.sql.tmpl`, with the detected marts naming convention
  applied to `<name>` (still prefixed with `draft__` ahead of it — the
  `draft__` prefix is never dropped by this skill, only by the human when
  promoting it).
- Add an entry to a shared
  `.dbt-martsmith/drafts/<slug>/models/draft___<group>__models.yml` (schema
  file, using `templates/schema.yml.tmpl`) with:
  - `description:` populated from the row's `description` column, verbatim
    or lightly cleaned up.
  - `meta: {source_sheet: <slug>.csv, requested_by: <if known>,
    date: <today, ISO 8601>}`.
  - Tests calibrated by the row's `importance`:
    - **high**: `not_null` on the columns your proposed calculation clearly
      depends on, `accepted_values` if the reasoning implies an enumerable
      set, and a `freshness:` block if any timeliness requirement was
      stated. Note in the proposal that a contract may be worth
      considering.
    - **medium**: `not_null` only on a column the reasoning *explicitly*
      says can't be null (e.g. "revenue can't be null") — never inferred
      speculatively.
    - **low**: description only, no drafted tests — leave a comment
      inviting the human to add tests themselves if they turn out to
      matter more than the sheet suggested.
  - Never invent a test that isn't grounded in something the reasoning
    actually said, regardless of importance — `high` raises how hard you
    look for explicit signals in the text, it doesn't license guessing.

Never create a new file for a metric that the grounding step recommends
extending an existing mart instead — put an inline "extend `<model>` at
`<original_file_path>` with `<column>`" suggestion in the proposal instead.

## Step 6 — Write state

Write/update `.dbt-martsmith/drafts/<slug>/meta.json`:
```json
{
  "sheet_checksum": "<sha256>",
  "generated_at": "<ISO 8601>",
  "status": "proposed | built",
  "rows": [
    {"metric": "...", "status": "matched|ambiguous|blocked", "target": "...", "importance": "low|medium|high"}
  ]
}
```

## Step 7 — Summary

Print a short summary: how many rows were matched/ambiguous/blocked, where
the proposal (and, once built, draft files) were written, and a reminder
that nothing was committed or built against the warehouse.

## Rules of engagement

- Never write outside `.dbt-martsmith/`.
- Never call a dbt command that mutates a warehouse (`build`/`run`/`test`/
  `seed`/`snapshot`) — only read-only introspection.
- Never invent a `ref()`/model match that `ground.py` didn't confirm.
- Never run Step 5 without an explicit approval of the Step 4 proposal.
- Always keep the stakeholder's `reasoning` verbatim and visually distinct
  from your own proposed calculation — never blend them into one line that
  looks like something the stakeholder wrote.
- If `.dbt-martsmith/` isn't already in the project's `.gitignore`, mention it
  in the summary as a suggestion — do not edit `.gitignore` yourself.
- Process one metric sheet fully before starting another if asked to handle
  multiple.
