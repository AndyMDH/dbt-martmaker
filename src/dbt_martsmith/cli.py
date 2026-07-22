"""
dbt-martsmith CLI. Fully deterministic -- no LLM in the loop. Reads a metric
sheet, grounds each source reference against the target dbt project's own
target/manifest.json, and writes a plain-text proposal plus skeleton mart
SQL/schema.yml for rows that resolved cleanly. Everything else (ambiguous,
blocked) is reported, never guessed.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dbt_martsmith import detect_conventions, ground

REQUIRED_COLUMNS = {"metric", "definition", "calculation", "source_tables"}
TEMPLATES_DIR = Path(__file__).parent / "templates"


def find_project_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / "dbt_project.yml").exists():
            return candidate
    print(
        f"ERROR: no dbt_project.yml found walking up from {start} -- "
        "dbt-martsmith must be run from inside a dbt project."
    )
    sys.exit(1)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def pick_default_prefix(naming_pattern: str | None) -> str:
    if not naming_pattern:
        return "mart_"
    return naming_pattern.split("|")[0].lstrip("^")


def load_sheet_rows(sheet_path: Path) -> list[dict]:
    with sheet_path.open(newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            print(f"ERROR: sheet is missing required column(s): {sorted(missing)}")
            sys.exit(1)
        return list(reader)


def render(template_text: str, **tokens) -> str:
    for key, value in tokens.items():
        template_text = template_text.replace(f"%%{key.upper()}%%", str(value))
    return template_text


def ground_row(row: dict, candidates: list[dict]) -> dict:
    source_refs = [s.strip() for s in row["source_tables"].split(",") if s.strip()]
    groundings = [ground.ground_one(ref, candidates) for ref in source_refs]
    statuses = {g["status"] for g in groundings}
    if "blocked" in statuses:
        overall = "blocked"
    elif "ambiguous" in statuses:
        overall = "ambiguous"
    else:
        overall = "matched"
    return {
        "metric": row["metric"].strip(),
        "definition": row["definition"].strip(),
        "calculation": row["calculation"].strip(),
        "groundings": groundings,
        "status": overall,
    }


def build_proposal(sheet_name: str, generated_at: str, conventions: dict, results: list[dict]) -> str:
    naming = conventions["naming"]
    lines = [
        "---",
        "status: proposed",
        f"source_sheet: {sheet_name}",
        f"generated_at: {generated_at}",
        f"naming_convention_detected_from: {naming['source'] if naming else 'none'}",
        "---",
        "",
        "# Mart Proposal",
        "",
    ]
    open_questions = []
    for row in results:
        lines.append(f"## {row['metric']}")
        lines.append(f"- Definition: {row['definition']}")
        lines.append(f"- Calculation: {row['calculation']}")
        for g in row["groundings"]:
            if g["status"] == "matched":
                lines.append(
                    f"- Grounding: matched `{g['model']}` ({g['original_file_path']}) "
                    f"— confirmed via manifest, score {g['score']}"
                )
            elif g["status"] == "ambiguous":
                candidate_names = ", ".join(f"`{c['model']}`" for c in g["candidates"])
                lines.append(f"- Grounding: ambiguous for \"{g['reference']}\" — candidates: {candidate_names}")
                open_questions.append(f"Confirm which of [{candidate_names}] is correct for \"{g['reference']}\" ({row['metric']})")
            else:
                lines.append(f"- Grounding: blocked — no matching staging/intermediate model found for \"{g['reference']}\"")
                open_questions.append(f"\"{g['reference']}\" ({row['metric']}) needs a new source staged first — out of scope for this tool")
        lines.append(f"- Status: {row['status'].capitalize()}")
        lines.append("")

    lines.append("## Open questions")
    if open_questions:
        for q in open_questions:
            lines.append(f"- [ ] {q}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Next steps for human review")
    lines.append("1. Resolve open questions above (bring to the next meeting if needed).")
    lines.append("2. Review the draft SQL/schema.yml under `models/`.")
    lines.append("3. Rename (drop the `draft__` prefix), move into the real `models/marts/...`")
    lines.append("   directory, and run `dbt parse`/`dbt-bouncer` locally.")
    return "\n".join(lines) + "\n"


def cmd_init(args) -> None:
    project_root = find_project_root(Path.cwd())
    sheets_dir = project_root / ".dbt-martsmith" / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    dest = sheets_dir / f"{args.name}.csv"
    if dest.exists():
        print(f"ERROR: {dest} already exists -- not overwriting.")
        sys.exit(1)
    dest.write_text((TEMPLATES_DIR / "metric_sheet.csv.tmpl").read_text())
    rel = dest.relative_to(project_root)
    print(f"Created {rel}")
    print(f"Fill it in, then run: dbt-martsmith run {rel}")


def cmd_run(args) -> None:
    project_root = find_project_root(Path.cwd())
    sheet_path = Path(args.sheet).resolve()

    if not sheet_path.exists():
        print(f"ERROR: {sheet_path} does not exist.")
        sys.exit(1)
    if sheet_path.name.endswith(".draft.csv"):
        print(
            f"ERROR: {sheet_path.name} is an unconfirmed draft sheet -- review it, "
            "correct it, and rename to <name>.csv before running dbt-martsmith on it."
        )
        sys.exit(1)

    rows = load_sheet_rows(sheet_path)
    checksum = hashlib.sha256(sheet_path.read_bytes()).hexdigest()
    slug = sheet_path.stem
    drafts_dir = project_root / ".dbt-martsmith" / "drafts" / slug
    meta_path = drafts_dir / "meta.json"

    if meta_path.exists():
        existing_meta = json.loads(meta_path.read_text())
        if existing_meta.get("sheet_checksum") == checksum:
            print(f"SKIPPED: {sheet_path.name} unchanged since last run ({drafts_dir})")
            return

    manifest = ground.load_manifest(project_root)  # exits with a clear error if missing
    candidates = ground.staging_and_intermediate_models(manifest)

    naming = detect_conventions.detect_naming_from_bouncer(project_root) or detect_conventions.sample_naming_from_files(project_root)
    conventions = {
        "naming": naming,
        "materialization": detect_conventions.detect_materialization(project_root),
        "property_files": detect_conventions.sample_property_file_pattern(project_root),
    }

    results = [ground_row(row, candidates) for row in rows]

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    drafts_dir.mkdir(parents=True, exist_ok=True)
    models_dir = drafts_dir / "models"
    models_dir.mkdir(exist_ok=True)

    prefix = pick_default_prefix(naming["pattern"] if naming else None)
    model_tmpl = (TEMPLATES_DIR / "model.sql.tmpl").read_text()
    schema_tmpl = (TEMPLATES_DIR / "schema.yml.tmpl").read_text()

    meta_rows = []
    for row in results:
        target = None
        if row["status"] == "matched":
            matched_model = row["groundings"][0]["model"]
            draft_name = f"draft__{prefix}{slugify(row['metric'])}"
            target = draft_name

            sql_content = render(
                model_tmpl,
                sheet_name=sheet_path.name,
                generated_at=generated_at,
                metric=row["metric"],
                definition=row["definition"],
                calculation=row["calculation"],
                matched_model=matched_model,
            )
            (models_dir / f"{draft_name}.sql").write_text(sql_content)

            yml_content = render(
                schema_tmpl,
                sheet_name=sheet_path.name,
                generated_at=generated_at,
                draft_model_name=draft_name,
                definition=row["definition"],
                calculation=row["calculation"],
            )
            (models_dir / f"{draft_name}.yml").write_text(yml_content)

        meta_rows.append({"metric": row["metric"], "status": row["status"], "target": target})

    proposal = build_proposal(sheet_path.name, generated_at, conventions, results)
    (drafts_dir / "proposal.md").write_text(proposal)

    meta_path.write_text(
        json.dumps(
            {"sheet_checksum": checksum, "generated_at": generated_at, "rows": meta_rows},
            indent=2,
        )
    )

    counts = Counter(r["status"] for r in results)
    print(f"Wrote {drafts_dir / 'proposal.md'}")
    print(f"matched={counts['matched']} ambiguous={counts['ambiguous']} blocked={counts['blocked']}")
    print("Nothing committed or built -- review the proposal, then promote drafts yourself.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="dbt-martsmith")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="scaffold a new metric sheet")
    init_parser.add_argument("name", nargs="?", default="metrics")
    init_parser.set_defaults(func=cmd_init)

    run_parser = subparsers.add_parser("run", help="ground a metric sheet and draft mart models")
    run_parser.add_argument("sheet", help="path to a confirmed metric sheet CSV")
    run_parser.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
