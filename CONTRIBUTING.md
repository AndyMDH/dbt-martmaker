# Contributing to dbt-martmaker

## Branch strategy

- **`main`** is always installable — anyone cloning the repo or running
  `install.sh` off `main` gets a working skill. Nothing lands here except
  by merging `dev` in.
- **`dev`** is the integration branch for day-to-day work. Feature branches
  and fixes branch off `dev` and merge back into `dev` via PR.
- Feature branches: `feature/<short-name>` or `fix/<short-name>`, branched
  from `dev`.

```
feature/x ─┐
fix/y      ├──> dev ──(periodic merge)──> main
feature/z ─┘
```

There's no build step or package registry here, so there's no separate
release/tag process — merging `dev` into `main` *is* the release.

## Local development

```bash
pip install -r requirements-dev.txt
ruff check skills/ tests/
pytest
```

Both `ruff` and `pytest` run in CI (`.github/workflows/ci.yml`) on every
push and PR.
