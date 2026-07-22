import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))


def make_model(name: str, layer: str, description: str = "", columns=None, group: str = "jaffle_shop") -> dict:
    """Build a manifest node shaped like a real dbt staging/intermediate model."""
    columns = columns or {}
    return {
        f"model.test_project.{name}": {
            "resource_type": "model",
            "name": name,
            "original_file_path": f"models/{layer}/{group}/{name}.sql",
            "description": description,
            "columns": {col: {} for col in columns},
        }
    }


@pytest.fixture
def dbt_project(tmp_path: Path):
    """A minimal dbt project directory: dbt_project.yml + target/manifest.json."""

    def _build(nodes: dict, extra_files: dict | None = None) -> Path:
        project_root = tmp_path
        (project_root / "dbt_project.yml").write_text("name: test_project\nversion: '1.0'\n")
        target_dir = project_root / "target"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "manifest.json").write_text(json.dumps({"nodes": nodes}))
        for rel_path, content in (extra_files or {}).items():
            full_path = project_root / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        return project_root

    return _build
