# Publishing

## One-time PyPI setup

1. Create an account at [pypi.org](https://pypi.org/) and register the project name `i66tolls`.
2. On the PyPI project page, add a **trusted publisher**:
   - PyPI project name: `i66tolls`
   - Owner: `alanjschoen`
   - Repository: `i66tolls`
   - Workflow: `publish.yml`
   - Environment: `pypi` (optional but recommended)
3. In GitHub repo **Settings → Environments**, create an environment named `pypi` (used by the publish workflow).

## Release a new version

1. Bump `version` in `pyproject.toml`.
2. Commit, tag, and push:

```bash
git tag v0.1.0
git push origin main --tags
```

The [Publish](../.github/workflows/publish.yml) workflow builds the package and uploads it to PyPI.

## Local build test

```bash
pip install -e ".[dev]"
python -m build
python -m twine check dist/*
```

Manual upload (if needed):

```bash
python -m twine upload dist/*
```
