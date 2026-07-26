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
`models/intermediate/`. It does not create new staging models and does not
declare new `source()` blocks. If a metric needs raw data that isn't staged
yet anywhere in the project, that row is **BLOCKED** — flag it and move on,
never attempt it.

## Input: the metric sheet

The sheet is meant to be filled out by the stakeholder who wants the
metric, not just an engineer — keep that in mind if you're helping someone
draft one conversationally. It lives at `.dbt-martmaker/sheets/<slug>.csv`,
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

State lives in `.dbt-martmaker/drafts/<slug>/meta.json`, with a `status`
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
calculation (this becomes your **Proposed calculation** in Step 4 — an
inference, not something lifted verbatim from the sheet, since the
stakeholder never wrote a formula), and the **grain** the stakeholder is
picturing. Grain signals are usually already in the text — "monthly",
"each payment", "per customer", "which customers", "this month", "a trend
over time" — so mine them the same way you mine table candidates:

- Signals present and consistent → commit to that grain as your inference.
- Signals absent or conflicting → mark the grain **undecided**; Step 4
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
one of the 4 built-ins — e.g. a `not_negative` test). Use this in Step 5:
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
grounding result and status (Matched/Ambiguous/Blocked), and — for
Matched/resolved rows — the proposed new mart file path.

**Preview table (required for every Matched/resolved row).** Under the
metric's detail section, render a small markdown table — 3–5 rows of
*fake but realistic* data — showing exactly what the output would look
like: real column names from the grounded model, plausible invented
values, the actual shape implied by your grain inference. Mark it clearly
as illustrative (e.g. a "(fake data — shape only)" caption). A stakeholder
who can't read SQL can still recognize whether this is the table they
pictured — the preview is what makes their approval mean something. Never
use real warehouse data here: grounding is metadata-only and the preview
must not imply a query was run.

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

Every row that is `ambiguous` (and unresolved) or `blocked`, and every
grain left undecided, becomes an Open Questions checklist line. Never omit
a row because it was hard to resolve. A row with an undecided grain is not
buildable in Step 5, even if approved wholesale — the grain choice is part
of what approval means.

This is where you stop (see "Two-phase flow" above) — do not proceed to
Step 5 in the same turn unless the human has already told you to build it.

## Step 5 — Draft skeleton model files (only after approval)

Only for rows that ended up Matched or resolved-Ambiguous **and** have a
decided grain (inferred in Step 1 or picked by the stakeholder from the
Step 4 alternatives). For each:

- Write `.dbt-martmaker/drafts/<slug>/models/draft__<name>.sql` using
  `templates/model.sql.tmpl`, with the detected marts naming convention
  applied to `<name>` (still prefixed with `draft__` ahead of it — the
  `draft__` prefix is never dropped by this skill, only by the human when
  promoting it).
- Add an entry to a shared
  `.dbt-martmaker/drafts/<slug>/models/draft___<group>__models.yml` (schema
  file, using `templates/schema.yml.tmpl`) with:
  - `description:` populated from the row's `description` column, verbatim
    or lightly cleaned up.
  - `meta: {source_sheet: <slug>.csv, requested_by: <if known>,
    date: <today, ISO 8601>}`.
  - Tests calibrated by the row's `importance`, and **checked against
    `existing_tests` from Step 2 before picking one**:
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

## Step 6 — Write state

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

## Step 7 — Summary

Print a short summary: how many rows were matched/ambiguous/blocked, where
the proposal (and, once built, draft files) were written, and a reminder
that nothing was committed or built against the warehouse.

## Rules of engagement

- Never write outside `.dbt-martmaker/`.
- Never call a dbt command that mutates a warehouse (`build`/`run`/`test`/
  `seed`/`snapshot`) — only read-only introspection.
- Never invent a `ref()`/model match that `ground.py` didn't confirm.
- Never run Step 5 without an explicit approval of the Step 4 proposal.
- Always keep the stakeholder's `reasoning` verbatim and visually distinct
  from your own proposed calculation — never blend them into one line that
  looks like something the stakeholder wrote.
- If `.dbt-martmaker/` isn't already in the project's `.gitignore`, mention it
  in the summary as a suggestion — do not edit `.gitignore` yourself.
- Process one metric sheet fully before starting another if asked to handle
  multiple.
