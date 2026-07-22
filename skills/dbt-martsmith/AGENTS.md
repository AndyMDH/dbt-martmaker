# dbt-martsmith

Turns a structured metric requirements sheet into a draft dbt mart model
(`dim_`/`fct_`/`rpt_`) for human review. Never writes to a real `models/`
directory, never runs `dbt build`/`run`/`test`, never guesses a match it
can't confirm.

Vault/project root is the directory containing `dbt_project.yml`. All paths
below are relative to it unless stated otherwise.

## Scope

**Mart layer only.** This tool builds `dim_`/`fct_`/`rpt_` models by
combining models that already exist in `models/staging/` and
`models/intermediate/`. It does not create new staging models and does not
declare new `source()` blocks. If a metric needs raw data that isn't staged
yet anywhere in the project, that row is **BLOCKED** — flag it and move on,
never attempt it.

## Input: the metric sheet

The only input this skill acts on is a metric sheet at
`.dbt-martsmith/sheets/<slug>.csv`, with columns: `metric`, `definition`,
`calculation`, `source_tables`. The user fills this in themselves (or asks
you to help draft one directly, in the same conversation, before running the
skill on it) — either way, treat what's in the file as the actual input once
you're asked to run against it.

## Idempotency guard

Before doing anything else: if `.dbt-martsmith/drafts/<slug>/meta.json` exists
and its `sheet_checksum` matches the current confirmed sheet's checksum,
this is a no-op. Print `SKIPPED: <slug>.csv unchanged since last run` and
stop.

## Step 0 — Locate & checksum

Walk upward from the current working directory until a `dbt_project.yml` is
found; that's the project root. If none is found within a reasonable number
of parent directories, **ERROR**: `No dbt_project.yml found — dbt-martsmith
must be run from inside a dbt project.` Stop; do not guess a root.

Compute a checksum (e.g. sha256) of the sheet's contents.

Derive `<slug>` from the sheet's filename (without extension).

## Step 1 — Parse sheet rows

Read the CSV. Required columns: `metric`, `definition`, `calculation`,
`source_tables`. If any are missing, **ERROR**: `Sheet is missing required
column(s): <list>` and stop — do not try to proceed with partial columns.

Each row becomes one working item carrying: metric name, definition text,
calculation text, and one or more source table references (a
`source_tables` cell may contain multiple names, comma-separated).

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

For each row, run `scripts/ground.py <project_root> "<source_tables>"` for
each source reference in that row. It reads `target/manifest.json` (and
`target/catalog.json` if present) and returns one of:

- **`matched`**: one confident hit — a real staging/intermediate model
  name and its columns.
- **`ambiguous`**: a shortlist of up to 10 candidates, none confident
  enough to pick automatically.
- **`blocked`**: no candidates at all.

Treat `ground.py`'s output as ground truth over the sheet's wording — do
not override a `blocked` result with your own guess about what the user
probably meant, and do not silently pick one shortlist candidate over
another. For `ambiguous`, you may reason about which shortlist candidate is
the better fit given the row's `definition`/`calculation` text, but if it's
still not clear, put it in Open Questions rather than picking.

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

## Step 4 — Draft the proposal

Using `templates/proposal.md.tmpl`, write
`.dbt-martsmith/drafts/<slug>/proposal.md` with one section per metric row,
each showing: definition, calculation, grounding result and status
(Matched/Ambiguous/Blocked), and — for Matched/resolved rows — the proposed
new mart file path and a one-line grain statement inferred from the
calculation/definition text.

Every row that is `ambiguous` (and unresolved) or `blocked` becomes an Open
Questions checklist line. Never omit a row because it was hard to resolve.

## Step 5 — Draft skeleton model files

Only for rows that ended up Matched or resolved-Ambiguous. For each:

- Write `.dbt-martsmith/drafts/<slug>/models/draft__<name>.sql` using
  `templates/model.sql.tmpl`, with the detected marts naming convention
  applied to `<name>` (still prefixed with `draft__` ahead of it — the
  `draft__` prefix is never dropped by this skill, only by the human when
  promoting it).
- Add an entry to a shared
  `.dbt-martsmith/drafts/<slug>/models/draft___<group>__models.yml` (schema
  file, using `templates/schema.yml.tmpl`) with:
  - `description:` populated from the row's `definition` column, verbatim
    or lightly cleaned up — never invented beyond what the sheet says.
  - `meta: {source_sheet: <slug>.csv, requested_by: <if known>,
    date: <today, ISO 8601>}`.
  - A generic `not_null` test on any column the `calculation` text
    explicitly implies must never be null (e.g. "revenue can't be null") —
    only from an explicit statement, never inferred speculatively.
  - A `freshness:` or a plain note in the description if the sheet
    explicitly states a refresh/timeliness requirement.

Never create a new file for a metric that the grounding step recommends
extending an existing mart instead — put an inline "extend `<model>` at
`<original_file_path>` with `<column>`" suggestion in the proposal instead.

## Step 6 — Write state

Write `.dbt-martsmith/drafts/<slug>/meta.json`:
```json
{
  "sheet_checksum": "<sha256>",
  "generated_at": "<ISO 8601>",
  "rows": [
    {"metric": "...", "status": "matched|ambiguous|blocked", "target": "..."}
  ]
}
```

## Step 7 — Summary

Print a short summary: how many rows were matched/ambiguous/blocked, where
the proposal and draft files were written, and a reminder that nothing was
committed or built.

## Rules of engagement

- Never write outside `.dbt-martsmith/`.
- Never call a dbt command that mutates a warehouse (`build`/`run`/`test`/
  `seed`/`snapshot`) — only read-only introspection.
- Never invent a `ref()`/model match that `ground.py` didn't confirm.
- If `.dbt-martsmith/` isn't already in the project's `.gitignore`, mention it
  in the summary as a suggestion — do not edit `.gitignore` yourself.
- Process one metric sheet fully before starting another if asked to handle
  multiple.
