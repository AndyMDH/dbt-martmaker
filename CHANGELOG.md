# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.1] - 2026-08-16

Re-ran `doctor.py` and `list_sheets.py` against the same sandbox project
right after 0.5.0 and found one more thing: `doctor.py`'s own marts check
still only looked at `models/marts/` -- it never got 0.5.0's fallback fix,
because it had its own, separate, now out-of-sync copy of that check.

### Fixed
- `doctor.py` now reuses `detect_conventions.py`'s `sample_naming_from_files()`
  for its marts check, instead of a second, independent
  `models/marts/`-only check that could drift out of sync with the first
  one -- which is exactly what had just happened.
- `detect_conventions.py` used to call `sys.exit(1)` at *import time* if
  PyYAML wasn't installed, which made the whole module impossible to
  import from anywhere else -- including by `doctor.py`, to reuse a
  function that never touched YAML in the first place. The missing-PyYAML
  exit now happens only in `detect_conventions.py`'s own `main()`; the
  individual functions degrade to `None` instead, exactly like a missing
  `dbt-bouncer.yml` or `dbt_project.yml` already did.

### Added
- 3 new tests (80 total) locking in that `doctor.py` and
  `detect_conventions.py` never disagree about marts again, and that the
  PyYAML-independent functions survive PyYAML actually being absent.

## [0.5.0] - 2026-08-16

Fixes three real bugs found by running the skill end to end, by hand,
against a real multi-metric sheet in `martmaker-sandbox` -- the exact
kind of orchestration issue unit tests structurally cannot catch, since
every prior test used hand-built fixtures where column lists meant
whatever the test wanted them to mean.

### Fixed
- **`target/manifest.json`'s column list is documentation, not reality.**
  dbt only lists a column there if someone wrote a `columns:` entry for
  it in a schema.yml -- real projects usually document only a subset
  (whichever columns carry a test). Grounding was treating that list as
  exhaustive, so a real, undocumented column (confirmed by reading the
  actual model SQL) would fail the "ground the calculation in real
  columns" check added in 0.2.0, forcing a wrong Open Question. Two-part
  fix: `columns` now comes from `target/catalog.json` (every real column)
  when it's available, since `ground.py` was already reading catalog.json
  for `column_types` and just wasn't using it for the column list itself.
  A new `columns_complete` flag tells the calling agent which case it's
  in; `AGENTS.md`'s column-verification rule now blocks only when
  `columns_complete: true` and treats an undocumented column as a stated
  assumption, not a false "doesn't exist."
- **`doctor.py` recommended `dbt docs generate`, which doesn't exist on
  dbt-fusion.** The message now names both the classic-dbt command and
  that other engines have their own equivalent, instead of assuming one
  specific engine.
- **Convention sampling only ever looked in `models/marts/`.** A project
  that keeps its marts at the top level of `models/` instead (dbt's own
  jaffle-shop starter is shaped this way) reported "no marts to sample
  from" despite genuinely having marts. `detect_conventions.py` now falls
  back to scanning `models/` itself, excluding staging/intermediate/
  seeds/snapshots, when `models/marts/` is empty or missing. Also now
  distinguishes "no files found" from "files found, but no shared name
  prefix" -- the latter is itself a real, reportable convention.

### Added
- 8 new tests (77 total) covering `columns_complete` end to end and the
  marts-fallback sampling, plus regression guards for the exact cases
  found in the real project.


### Added
- **Escalation trigger** (`scripts/escalation.py`) — the tool's answer to
  "when does a metric need an actual conversation, not another sheet
  revision?" Tracks each metric's status across sheet revisions in
  `.dbt-martmaker/drafts/<slug>/history.json`. A row that stays
  `ambiguous`/`blocked` for two consecutive revisions gets a distinct
  "needs a conversation" marker in the proposal — never on a first
  attempt, and never for an already-matched row. Philosophy: default to
  the cheap, async channel (the sheet) every time; escalate to the
  expensive one only once the cheap one has demonstrably already failed.

## [0.3.0] - 2026-08-16

### Added
- **Project glossary** (`.dbt-martmaker/glossary.yml`) — a project's own
  synonym pairs, merged on top of the built-in list. Solves the case a
  built-in pair can never cover: a term specific to one project's own
  vocabulary.
- **Embedding-based matching** via the Voyage AI API (Anthropic's
  recommended embeddings provider), enabled by setting `VOYAGE_API_KEY`.
  Enrichment only — it can attach a confidence signal to an existing
  match, and it can lift a `blocked` reference to `ambiguous` when
  embeddings find a plausible candidate token overlap missed entirely,
  but nothing above the embedding floor is ever auto-matched. Absent the
  key, or on any API failure, grounding behaves exactly as it does
  offline.
- **Corrections log** (`.dbt-martmaker/corrections.jsonl`) — once a human
  corrects a match, it is remembered and applied deterministically to
  every future run of that exact reference.
- **dbt Mesh awareness** — public models (`access: public`) from sibling
  projects listed in `.dbt-martmaker/mesh_manifests.yml` become grounding
  candidates too, tagged with `source_project`. Step 6 now writes the
  correct two-argument cross-project `ref()` for a mesh-sourced match.
  `dbt-mcp`, when configured, is now also documented as a fallback path
  for a project that only exists in dbt Cloud, not on local disk.
- Ambiguous-case guidance in `AGENTS.md` now explicitly asks the agent to
  weigh each candidate's `embedding_score` alongside its own reading of
  the columns and description — not a rule that picks, one more input to
  judgment.

### Changed
- `ground.py`'s candidate pool now includes sibling dbt Mesh public
  models alongside local staging/intermediate models; a `blocked` result
  now genuinely means "not found anywhere reachable," not just "not found
  locally."
- Step 8's summary now also reports how many rows matched via a
  remembered correction or a sibling Mesh project.
- Grounding now checks a project's dbt Semantic Layer
  (`target/semantic_manifest.json`, when present): a metric that already
  exists as a live MetricFlow metric is surfaced as an Open Question
  instead of silently drafted as a duplicate physical mart. Matching
  checks both a metric's internal `name` and its human-readable `label`.
- `target/catalog.json`, when present, is read for real — matched and
  ambiguous grounding candidates now carry each column's actual warehouse
  data type (`column_types`), used to sanity-check a proposed test against
  reality (e.g. never propose `accepted_values` on a numeric column).
- `scripts/doctor.py` — a readiness check to run before Step 0: reports
  whether the project has `target/manifest.json`, PyYAML, and (as
  enrichment, never blocking) `catalog.json`/`semantic_manifest.json`/
  `dbt-bouncer.yml`.
- `scripts/list_sheets.py` — status overview of every metric sheet in
  `.dbt-martmaker/sheets/`: no proposal yet / proposed / built / stale,
  with matched/ambiguous/blocked row counts.
- Installable as a real Claude Code plugin: `.claude-plugin/plugin.json`
  and `marketplace.json`, so `/plugin marketplace add
  AndyMDH/dbt-martmaker` then `/plugin install dbt-martmaker` replaces
  clone-and-script as the primary install path. `install.sh --project`
  remains for a single-repo or non-plugin install.
- `CHANGELOG.md` (this file).
- A small synonym map in `ground.py` (`SYNONYM_GROUPS`) so common
  analytics-engineering term pairs — "clients"/"customers",
  "orders"/"purchases", "revenue"/"sales" — no longer score zero overlap
  and read as `blocked` just because the stakeholder's word choice
  differs from the project's table names. Not general NLP synonymy —
  a documented, extensible list of the pairs that come up constantly.
  The four matching thresholds are now also named/commented with why
  each exists, instead of bare magic numbers.

### Changed
- The propose-then-build flow now states, per metric, exactly which
  assertions a build will encode ("Assertions this draft will encode") as
  an explicit, approved contract — not an implicit "Proposed tests"
  summary line.
- A proposed calculation must now be grounded in columns Step 3's
  grounding actually confirmed exist, and must quote the fragment of
  `reasoning` that justifies it. A calculation needing an unconfirmed
  column becomes an Open Question, never a `TODO: confirm the column`
  comment left in drafted SQL.
- Step 6 (drafting) now builds one metric fully — SQL plus its own
  schema.yml entry — before starting the next, reviewable as a sequence of
  independent slices rather than one undifferentiated batch. Promoting a
  draft into `models/marts/` is now explicitly named as a separate,
  human-only step, never blended into drafting.
- `AGENTS.md`'s steps are renumbered 0–8 to make room for the new
  Semantic Layer check (Step 4).

### Fixed
- `ground.py` keyed a candidate's real column types off a manifest node's
  own (often absent) `unique_id` field instead of the manifest's `nodes`
  dict key, which is the authoritative id — column types silently never
  attached. Fixed at the source.
- `AGENTS.md` claimed grounding read `target/catalog.json`; the code never
  did. It now actually does.
- `.ruff_cache/` was untracked only via a global gitignore rule on one
  machine, not the repo's own — added to `.gitignore` directly.

## [0.1.0] - 2026-07-27

Initial release. Turns a stakeholder metric requirements sheet into a
draft dbt mart model (`dim_`/`fct_`/`rpt_`), grounded against
`target/manifest.json`, with a two-phase propose-then-approve flow, mart-
layer-only scope, and project-convention detection (naming,
materialization, existing generic tests).
