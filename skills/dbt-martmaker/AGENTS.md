# dbt-martmaker

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
`models/intermediate/` — plus, when configured, public models from a
sibling dbt Mesh project (see Configuration). It does not create new
staging models and does not declare new `source()` blocks. If a metric
needs raw data that isn't staged yet anywhere reachable, that row is
**BLOCKED** — flag it and move on, never attempt it.

It also never duplicates a metric a project's dbt Semantic Layer already
serves live — see Step 4.

## Input: the metric sheet

The sheet is meant to be filled out by the stakeholder who wants the
metric, not just an engineer — keep that in mind if you're helping someone
draft one conversationally. It lives at `.dbt-martmaker/sheets/<slug>.csv`,
with columns: `metric`, `description`, `reasoning`, `importance`.

- `metric` — a short name, e.g. "Marketing ROI".
- `description` — one line, plain language, what it means.
- `reasoning` — the stakeholder's own free-form explanation of **why they
  want this metric**: the decision it feeds, the question it answers, who's
  asking. It's motivation, not specification — data or calculation hints
  usually show up only incidentally ("should be in our subscriptions
  data", "refunds have skewed it before"), and those incidental hints plus
  the `description` are exactly the raw material *you* (the agent) mine in
  Steps 1 and 5 to figure out which real columns/tables are involved and
  what the actual calculation should be. **This is not a formula and not a
  table name** — if a reasoning cell reads like a computation recipe, the
  stakeholder is doing your job; they should never need SQL or your
  project's schema to fill this in.
- `importance` — one of `low`/`medium`/`high`, set by the stakeholder based
  on how critical the metric is. Drives how much test rigor gets drafted in
  Step 6. If blank, treat as `medium` rather than erroring — don't make a
  stakeholder think hard about this column to use the tool.

## Two-phase flow: propose, then build on approval

This skill never jumps straight from a sheet to draft SQL files. It always
stops after Step 5 and shows the stakeholder/human a proposal to approve
first — only after they confirm does Step 6 actually write any files. This
matters more now than it would for a literal input: `reasoning` is
deliberately vague, so what Step 3–5 propose as the matched column,
calculation, and **the assertions that will get tested** is a genuine
inference on your part, not a transcription of what the stakeholder wrote —
they need to see and confirm it before anything gets built. Think of the
approved proposal as the agreed seam: Step 6 builds against exactly what
was confirmed there, nothing more.

State lives in `.dbt-martmaker/drafts/<slug>/meta.json`, with a `status`
field of `proposed` or `built`:

- **No `meta.json`, or its `sheet_checksum` doesn't match the current
  sheet**: this is a fresh (re-)proposal. Run Steps 0–5, write
  `meta.json` with `status: proposed`, then **stop** — do not run Step 6.
  End your turn by asking something like: *"Here's the proposal — want me
  to build the draft SQL/schema.yml files for the matched rows?"*
- **`meta.json` exists, checksum matches, `status: proposed`, and the
  human has just approved** (in this conversation, or by asking you to
  build it in a new one): run Step 6, then update `meta.json` to
  `status: built` and `proposal.md`'s frontmatter to match.
- **`meta.json` exists, checksum matches, `status: built`**: no-op. Print
  `SKIPPED: <slug>.csv already built (<drafts_dir>)` and stop.

If the sheet changed since the last proposal (checksum mismatch), always
re-ground and re-propose from scratch — never build from stale grounding
results.

## Utilities (on demand)

Two scripts outside the main flow, for a status check rather than running
Steps 0–8:

- `scripts/doctor.py [start_dir]` — readiness check. Run this first
  whenever it's unclear if the project has what this skill needs: finds
  `dbt_project.yml` walking upward from `start_dir` (default cwd), then
  reports whether `target/manifest.json` exists, whether PyYAML is
  importable, and whether `target/catalog.json` /
  `target/semantic_manifest.json` / `dbt-bouncer.yml` are present — the
  latter three are enrichment and never block readiness. `ready: false`
  means Step 0 will fail; its `messages` list says exactly what to fix.
- `scripts/list_sheets.py <project_root>` — status of every sheet already
  in `.dbt-martmaker/sheets/`: `no proposal yet`, `proposed`, `built`, or
  `stale (sheet changed since last proposal)`, with matched/ambiguous/
  blocked row counts once a proposal exists. Use this when more than one
  metric sheet is in flight, or when picking a project back up after a
  break, instead of reading `.dbt-martmaker/drafts/` by hand.

Both are read-only status checks — neither writes anything or is part of
the approval flow.

## Step 0 — Locate & checksum

Walk upward from the current working directory until a `dbt_project.yml` is
found; that's the project root. If none is found within a reasonable number
of parent directories, **ERROR**: `No dbt_project.yml found — dbt-martmaker
must be run from inside a dbt project.` Stop; do not guess a root.

Compute a checksum (e.g. sha256) of the sheet's contents.

Derive `<slug>` from the sheet's filename (without extension).

## Step 1 — Parse sheet rows and read the reasoning

Read the CSV. Required columns: `metric`, `description`, `reasoning`,
`importance`. If any are missing, **ERROR**: `Sheet is missing required
column(s): <list>` and stop — do not try to proceed with partial columns.

For each row, read the `reasoning` text and identify what it implies:
candidate entities/tables it's talking about (these become the reference
strings you pass to `ground.py` in Step 3), a rough shape of the
calculation (this becomes your **Proposed calculation** in Step 5 — an
inference, not something lifted verbatim from the sheet, since the
stakeholder never wrote a formula), and the **grain** the stakeholder is
picturing. Grain signals are usually already in the text — "monthly",
"each payment", "per customer", "which customers", "this month", "a trend
over time" — so mine them the same way you mine table candidates:

- Signals present and consistent → commit to that grain as your inference.
- Signals absent or conflicting → mark the grain **undecided**; Step 5
  turns it into a multiple-choice question rather than a silent guess.

Express every grain inference in "one row per ___" language ("one row per
payment", "one row per customer per month", "one row total") — that's the
phrasing a stakeholder can actually verify, and it's used verbatim in the
proposal. Working item per row: metric name, description text, reasoning
text (kept verbatim for the proposal), your extracted candidate
reference(s), your proposed calculation, your inferred grain (or
"undecided"), and importance (`low`/`medium`/`high`, defaulting to
`medium` if blank).

## Step 2 — Detect mart-layer conventions

Run `scripts/detect_conventions.py <project_root>`. It returns the naming
pattern for `models/marts` (from `dbt-bouncer.yml` if present, else sampled
from existing filenames), the materialization default for marts (from
`dbt_project.yml`), the property-file naming pattern sampled from whichever
marts subdirectory already has files in it, and `existing_tests`: every
generic test already used anywhere in the project's manifest, split into
`builtin` (`not_null`/`unique`/`accepted_values`/`relationships`),
`package` (e.g. a `dbt_expectations` or `dbt_utils` test, with namespace),
and `custom` (a project-defined generic test with no namespace that isn't
one of the 4 built-ins — e.g. a `not_negative` test). Use this in Step 6:
if an existing custom or package test already fits what a metric's
`reasoning` implies, propose reusing *that* instead of reaching for a
generic default — it's what the project's own convention already is.

If the marts folder is empty and nothing can be sampled, do not invent a
convention — note it as an open question in the proposal instead
(`No existing marts to sample a naming convention from — confirm the
prefix/materialization convention to use.`).

Cache the result at `.dbt-martmaker/conventions.cache.json`, keyed on the
mtime of `dbt-bouncer.yml` and `dbt_project.yml`; re-run detection only if
either has changed since the cache was written.

## Step 3 — Ground each row

For each row, run `scripts/ground.py <project_root> "<candidate references
from Step 1>" "<metric name>"`. It reads `target/manifest.json` and, when
present, `target/catalog.json`, any sibling dbt Mesh manifests configured
in `.dbt-martmaker/mesh_manifests.yml`, a project's own
`.dbt-martmaker/glossary.yml`, and any remembered corrections in
`.dbt-martmaker/corrections.jsonl` (see Configuration, below). It returns
one `results` entry per reference plus a `semantic_layer` section (used in
Step 4). Each `results` entry is one of:

- **`matched`**: one confident hit — a real staging/intermediate model
  name, its columns, and (when `target/catalog.json` exists)
  `column_types`: each matched column's real warehouse data type. A match
  that came from a remembered correction carries `matched_via:
  "correction"` instead of a `score` you need to weigh.
- **`ambiguous`**: a shortlist of up to 10 candidates, none confident
  enough to pick automatically — each also carries `columns` and
  `column_types` when available, so you can weigh candidates by more than
  name alone. A candidate token overlap missed entirely, but that
  embeddings surfaced (see below), carries `matched_via: "embedding"` and
  a `score` of `0.0` — treat that as the weakest tier of evidence here,
  never as good as a real token-overlap candidate in the same shortlist.
- **`blocked`**: no candidates at all.

Every candidate also carries `source_project`: `null` for a model in this
project's own manifest, or a project name when the candidate is a public
model from a sibling dbt Mesh project. **A mesh-sourced match changes how
Step 6 must write the `ref()`** — see Step 6.

Treat `ground.py`'s output as ground truth over your own reading of the
reasoning text — do not override a `blocked` result with a guess about
what the stakeholder probably meant, and do not silently pick one shortlist
candidate over another. For `ambiguous`, weigh each candidate's
`embedding_score` (when present) alongside your own reading of its
description and columns given the row's `reasoning` — the embedding score
is one more input to your judgment, never a rule that picks for you. If
it's still not clear, put it in Open Questions rather than picking.

`column_types` is enrichment, not a gate: a missing `target/catalog.json`
(`catalog_available: false` in the output) never blocks or downgrades a
match made from the manifest. When it is available, use it in Step 6 to
sanity-check a proposed test against reality — e.g. never propose a
numeric range/comparison test on a column whose catalog type is a string.

If `ground.py` reports that `dbt-mcp` is configured and reachable
(see its own output), you may additionally call its `get_lineage_dev` /
`get_node_details_dev` tools on a matched model for richer detail
(contract/constraints, adapter tags) to include in the proposal, or to
look up a public model in a sibling dbt Cloud project this script has no
local manifest for (`.dbt-martmaker/mesh_manifests.yml` only covers
projects reachable on disk). Treat this purely as enrichment — never
required, never a substitute for the manifest-based match.

If the dbt project has no `target/manifest.json` at all, **ERROR**:
`No target/manifest.json found — run 'dbt parse' in this project first.`
Do not fall back to guessing from the sheet's prose alone.

**Never call `dbt build`, `dbt run`, or `dbt test`** — grounding is always
read-only.

## Configuration (optional)

None of these are required. Grounding works the same without any of them
— each is a way for a project or team to make matching sharper over time,
never a prerequisite to using the skill at all.

- **`.dbt-martmaker/glossary.yml`** — a project's own synonym pairs, on
  top of the small built-in list (customer/client, order/purchase, and a
  few others). Format:
  ```yaml
  synonyms:
    - [signups, registrations]
    - [members, subscribers]
  ```
  Add a pair here when a real stakeholder term keeps reading as `blocked`
  or `ambiguous` against a model whose name uses different words for the
  same thing.
- **`.dbt-martmaker/mesh_manifests.yml`** — sibling dbt Mesh projects
  reachable on disk, so their **public** models (`access: public` in
  their own manifest) become grounding candidates too:
  ```yaml
  projects:
    - name: shared_models
      manifest: ../shared-models-repo/target/manifest.json
  ```
  A project not listed here, or not on disk, is invisible to grounding —
  use the `dbt-mcp` path above for a project that only exists in dbt
  Cloud.
- **`.dbt-martmaker/corrections.jsonl`** — one JSON object per line,
  append-only, written by you (see Rules of engagement) whenever a human
  tells you a match was wrong: `{"reference": "...", "correct_candidate":
  "..."}`. Checked before scoring on every future run of that exact
  reference — this is the only way a correction, once given, is never
  asked again.
- **`VOYAGE_API_KEY`** environment variable — enables embedding-based
  matching via the Voyage AI API (Anthropic's recommended embeddings
  provider). Absent, or the API call fails for any reason: grounding
  behaves exactly as it does with no network access at all.
  `VOYAGE_MODEL` optionally overrides the default model
  (`voyage-4-lite`).

## Step 4 — Check the dbt Semantic Layer

The same `ground.py` call from Step 3 also returns a `semantic_layer`
section — no second invocation needed. `available` is `true` when the
project has a `target/semantic_manifest.json` (i.e. it runs, or has run,
dbt's Semantic Layer / MetricFlow). `match` is `null` unless the row's
metric name confidently overlaps an existing Semantic Layer metric.

A `match` is never a silent block. It changes what Step 5 proposes for
that row: instead of (or alongside) a drafted mart, the proposal states
that the metric already appears to exist as a live MetricFlow metric —
name it, and suggest querying it (e.g. `mf query --metrics <name>`) rather
than building a duplicate. Add the row to Open Questions asking the
stakeholder to confirm whether a materialized copy is still wanted, and
why (a BI tool that can't query the Semantic Layer directly is a real
reason; "wasn't aware it already existed" means the answer is probably no).

The match is scored against both the metric's internal `name` and its
human-readable `label` when the Semantic Layer defines one — a
stakeholder's own phrasing ("Marketing ROI") often matches a metric's
`label` even where it shares no tokens with an abbreviated snake_case
`name` like `mktg_roi_pct`. Refer to whichever one `ground.py` reports as
the closer match when naming the metric back to the stakeholder.

If `available` is `false`, this project doesn't run a Semantic Layer —
skip this step's proposal language entirely and proceed as if it doesn't
exist. Most projects will be in this state; that's expected, not an error.

## Step 5 — Draft the proposal (stop here for approval)

Using `templates/proposal.md.tmpl`, write
`.dbt-martmaker/drafts/<slug>/proposal.md` with `status: proposed` in its
frontmatter. Start with a **Summary table** (Metric | Column used |
Description | Proposed calculation | Grain | Importance | Status), one row
per metric in the same order as the sheet — "Column used" is the matched
model name (or blank for Ambiguous/Blocked), "Proposed calculation" is
your inference from Step 1, not the raw sheet text, and "Grain" is your
Step 1 grain inference in "one row per ___" form (or "undecided — see
open questions"). This is the artifact the stakeholder actually approves,
so it needs to show what they'll recognize, not just an engineering status
code.

Then one section per metric row with the full detail: description, the
stakeholder's **reasoning** (verbatim, never edited), your **proposed
calculation** (clearly labeled as your inference, not theirs), the
**grain** ("one row per ___", labeled as your inference), importance,
grounding result and status (Matched/Ambiguous/Blocked), a Semantic Layer
note when Step 4 found a match, and — for Matched/resolved rows — the
proposed new mart file path.

**Ground the calculation in real columns, never a guess wrapped in a
TODO.** Before stating a Proposed calculation for a Matched or
resolved-Ambiguous row, check every column name it references against
that row's `columns` (or `column_types`) list from Step 3. A calculation
that needs a column not on that list is not confirmed — never state it
with a "TODO: confirm the column name" placeholder and move on. Instead,
move the row to Open Questions, naming the model's real available columns
as candidates, so the mismatch gets resolved before Step 6 ever runs. A
row with an unconfirmed column reference is not buildable, the same way
an undecided grain or an unresolved Semantic Layer match isn't.

Quote the short fragment of `reasoning` that most directly justifies the
Proposed calculation, e.g. `— based on "refunds have skewed it negative
before"`. This is what makes the inference auditable: a reviewer can trace
the calculation back to the exact words that produced it instead of
re-reading the whole `reasoning` text and re-deriving your reasoning
themselves.

**Assertions this draft will encode (required for every Matched/resolved
row).** State plainly, as its own line, exactly which tests Step 6 will
add if this row is approved as written — column names and test types, not
just "some tests." This is the seam the stakeholder is actually agreeing
to: approval fixes what gets asserted, the same way it fixes the
calculation and the grain. Never leave this implicit in the summary table
alone.

**Preview table (required for every Matched/resolved row).** Under the
metric's detail section, render a small markdown table — 3–5 rows of
*fake but realistic* data — showing exactly what the output would look
like: real column names from the grounded model, plausible invented
values, the actual shape implied by your grain inference. Mark it clearly
as illustrative (e.g. a "(fake data — shape only)" caption). A stakeholder
who can't read SQL can still recognize whether this is the table they
pictured — the preview is what makes their approval mean something. Never
use real warehouse data here: grounding is metadata-only and the preview
must not imply a query was run. The preview's values are invented for
illustration, never derived by actually running the proposed calculation —
a preview that quietly reproduces the calculation's own arithmetic proves
nothing to the stakeholder reading it.

**Grain-undecided rows: show alternatives, don't ask an abstract
question.** If Step 1 left the grain undecided for an otherwise Matched
row, render two or three candidate preview tables side by side — e.g.
(a) one row total, (b) one row per customer, (c) one row per month — each
a 2–3 row fake-data table, and add an Open Questions line asking the
stakeholder to pick one: *"Which of these is the table you pictured for
<metric>?"* Picking between concrete tables is a question anyone can
answer; "what granularity do you want?" is not. Only do this when the
reasoning genuinely doesn't settle it — if the text already says
"monthly", infer monthly and state it; don't ask about things the
stakeholder already answered. If you're running interactively and have a
question tool available (e.g. AskUserQuestion), you may additionally ask
the grain choice directly with the candidate tables as previews — but the
proposal file must still contain the alternatives and the Open Questions
line, so the choice survives outside the conversation.

**Escalate to a real conversation, not another round, when the sheet has
already tried.** For every row, run `scripts/escalation.py <project_root>
<slug> "<metric>" <status> <sheet_checksum>` after Step 3 — matched rows
too, not just Ambiguous/Blocked ones, so a later regression is judged
against accurate history. It reads
`.dbt-martmaker/drafts/<slug>/history.json` (this metric's outcome on
every prior revision of this exact sheet) and reports `escalate: true`
once a row has stayed unresolved for two consecutive revisions — never on
a first attempt, and never for a row that's already matched. Default to
the sheet every time; a stakeholder revising an Open Question in writing
is the cheap path, and it stays the cheap path unless it has genuinely
already failed once.

When `escalate` is `true`, that row's Open Questions line is different in
kind, not just degree: instead of asking the stakeholder to revise the
sheet again, recommend a short conversation and say plainly why — *"This
has stayed `<status>` for `<total_attempts>` revisions; a quick
conversation will likely resolve it faster than a third round on the
sheet."* Never phrase an escalated row as an ordinary Open Question the
stakeholder is expected to answer by revising the sheet again — that
repeats a channel that has already been tried and has already failed.

Every row that is `ambiguous` (and unresolved) or `blocked`, every grain
left undecided, and every Semantic Layer match from Step 4 becomes an Open
Questions checklist line — an escalated row as a distinct, clearly marked
line, never an ordinary one. Never omit a row because it was hard to
resolve. A row with an undecided grain is not buildable in Step 6, even if
approved wholesale — the grain choice is part of what approval means.

This is where you stop (see "Two-phase flow" above) — do not proceed to
Step 6 in the same turn unless the human has already told you to build it.

## Step 6 — Draft skeleton model files (only after approval)

Only for rows that ended up Matched or resolved-Ambiguous **and** have a
decided grain (inferred in Step 1 or picked by the stakeholder from the
Step 5 alternatives) **and** were not left as an unresolved Semantic Layer
Open Question from Step 4 **and** had every column their calculation
references confirmed against Step 3's grounding, per Step 5. Build
**one metric at a time, fully, before
starting the next** — its SQL and its own schema.yml entry together —
rather than drafting all SQL first and all schema.yml entries after; a
sheet with several matched metrics reviews as a sequence of independent
slices this way, not one undifferentiated batch. For each row:

- Write `.dbt-martmaker/drafts/<slug>/models/draft__<name>.sql` using
  `templates/model.sql.tmpl`, with the detected marts naming convention
  applied to `<name>` (still prefixed with `draft__` ahead of it — the
  `draft__` prefix is never dropped by this skill, only by the human when
  promoting it). The SQL exists to satisfy the assertions the proposal
  already stated in Step 5 — write it as delivering on that stated
  contract, not as a fresh, unrelated pass over the row. If the matched
  row's `source_project` is set (a dbt Mesh public model, not a local
  one), the `ref()` must be the two-argument cross-project form —
  `{{ ref('<source_project>', '<model>') }}` — never the local
  single-argument form, which would resolve to the wrong model or fail to
  resolve at all.
- Add an entry to a shared
  `.dbt-martmaker/drafts/<slug>/models/draft___<group>__models.yml` (schema
  file, using `templates/schema.yml.tmpl`) with:
  - `description:` populated from the row's `description` column, verbatim
    or lightly cleaned up.
  - `meta: {source_sheet: <slug>.csv, requested_by: <if known>,
    date: <today, ISO 8601>}`.
  - Exactly the assertions named in the approved proposal's "Assertions
    this draft will encode" line — never more, never fewer — calibrated
    by the row's `importance`, and **checked against `existing_tests`
    from Step 2 before picking one**:
    - **high**: `not_null` on the columns your proposed calculation clearly
      depends on, `accepted_values` if the reasoning implies an enumerable
      set, and a `freshness:` block if any timeliness requirement was
      stated. If a value must be positive/non-negative/within a range and
      the project already has a custom or package test for that (like
      `not_negative`), propose that instead of a generic substitute. Note
      in the proposal that a contract may be worth considering.
    - **medium**: `not_null` only on a column the reasoning *explicitly*
      says can't be null (e.g. "revenue can't be null") — same
      existing-test-first check as above, never inferred speculatively.
    - **low**: description only, no drafted tests — leave a comment
      inviting the human to add tests themselves if they turn out to
      matter more than the sheet suggested.
  - Before picking a test's shape, check the matched column's
    `column_types` from Step 3 when available — e.g. don't propose an
    `accepted_values` test against a column typed as a numeric/float; that
    is a signal the match or the calculation needs a second look, not
    something to test around silently.
  - Never introduce a new package dependency (e.g. `dbt_expectations`) the
    project doesn't already use just to get a slightly better test — reuse
    what's in `existing_tests`, or fall back to a built-in, rather than
    proposing a new dependency as a side effect of one metric.
  - Never invent a test that isn't grounded in something the reasoning
    actually said, regardless of importance — `high` raises how hard you
    look for explicit signals in the text, it doesn't license guessing.

Never create a new file for a metric that the grounding step recommends
extending an existing mart instead — put an inline "extend `<model>` at
`<original_file_path>` with `<column>`" suggestion in the proposal instead.

Promoting a draft — dropping the `draft__` prefix, moving it into the real
`models/marts/...` directory, reconciling it with `dbt-bouncer` or other
lint rules, running `dbt parse` — is deliberately **not** part of this
step. That is refactoring work, and it belongs to the human doing the
promotion, after this step, never blended into drafting itself.

## Step 7 — Write state

Write/update `.dbt-martmaker/drafts/<slug>/meta.json`:
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

## Step 8 — Summary

Print a short summary: how many rows were matched/ambiguous/blocked, how
many carried a Semantic Layer match from Step 4, how many matched via a
remembered correction or a sibling dbt Mesh project, how many were
escalated (see Step 5) and so need a conversation rather than another
sheet revision, where the proposal (and, once built, draft files) were
written, and a reminder that nothing was committed or built against the
warehouse.

## Rules of engagement

- Never write outside `.dbt-martmaker/`.
- Never call a dbt command that mutates a warehouse (`build`/`run`/`test`/
  `seed`/`snapshot`) — only read-only introspection.
- Never invent a `ref()`/model match that `ground.py` didn't confirm.
- Never draft SQL, or state a Proposed calculation, referencing a column
  Step 3's grounding didn't confirm exists on the matched model — an
  unconfirmed column is an Open Question, never a TODO comment left for
  later.
- Never draft SQL for a row Step 4 flagged as a confident Semantic Layer
  match unless the stakeholder has explicitly said, in response to that
  Open Question, that a materialized duplicate is still wanted.
- Never run Step 6 without an explicit approval of the Step 5 proposal.
  The proposal is the agreed seam — nothing gets built against a seam
  that was never confirmed.
- Build one metric fully — SQL plus its own schema.yml entry — before
  starting the next, per Step 6. Never draft all SQL first and all tests
  after; a human reviewing several metrics at once needs to tell which
  change belongs to which promise.
- Always keep the stakeholder's `reasoning` verbatim and visually distinct
  from your own proposed calculation — never blend them into one line that
  looks like something the stakeholder wrote.
- If `.dbt-martmaker/` isn't already in the project's `.gitignore`, mention it
  in the summary as a suggestion — do not edit `.gitignore` yourself.
- Process one metric sheet fully before starting another if asked to handle
  multiple.
- When a human tells you, in conversation, that a match Step 3 produced
  was wrong, append one line to `.dbt-martmaker/corrections.jsonl` before
  proceeding: `{"reference": "<the exact reference text>",
  "correct_candidate": "<the real model name>"}`. This is the only
  mechanism that makes a correction stick for future runs — without it,
  the same reference makes the same mistake again next time.
- Default to the sheet, every time, for every row — it is the cheap
  channel and it gets a real first try. Escalate to a conversation (see
  Step 5) only when `scripts/escalation.py` reports `escalate: true`.
  Never suggest a conversation on a row's first unresolved appearance,
  and never keep silently re-asking the same unresolved question round
  after round once escalation has fired — say plainly that the sheet has
  already been tried.
