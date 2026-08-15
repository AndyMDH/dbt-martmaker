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
claude plugin validate . --strict
```

`ruff`, `pytest`, and `claude plugin validate` all run in CI
(`.github/workflows/ci.yml`) on every push and PR.

## Releasing

`.claude-plugin/plugin.json`'s `version` and `pyproject.toml`'s
`[project] version` must always match — bump both together. Claude Code
uses the plugin's `version` to decide when an installed user sees an
update. After merging to `main`, tag the release with:

```bash
claude plugin tag --push
```
