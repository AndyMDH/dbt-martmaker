# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
