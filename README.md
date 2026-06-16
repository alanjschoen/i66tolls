# i66tolls

Vibe coded command-line tool for checking tolls on I-66 inside the Capital Beltway (between I-495 and the Theodore Roosevelt Bridge).

Run it with no arguments for an interactive wizard, or pass entry/exit IDs and flags for a quick lookup.

Data comes from VDOT's official toll calculator at [vai66tolls.com](https://vai66tolls.com/).

![Demo](demo.gif)

## Requirements

- Python 3.10+
- [Typer](https://typer.tiangolo.com/) for the CLI
- [InquirerPy](https://inquirerpy.readthedocs.io/) for interactive prompts

## Install

From PyPI:

```bash
pip install i66tolls
```

From source:

```bash
pip install -e .
```

## Publishing (maintainers)

### One-time PyPI setup

1. Create an account at [pypi.org](https://pypi.org/) and register the project name `i66tolls`.
2. On the PyPI project page, add a **trusted publisher**:
   - PyPI project name: `i66tolls`
   - Owner: `alanjschoen`
   - Repository: `i66tolls`
   - Workflow: `publish.yml`
   - Environment: `pypi` (optional but recommended)
3. In GitHub repo **Settings → Environments**, create an environment named `pypi` (used by the publish workflow).

### Release a new version

1. Bump `version` in `pyproject.toml`.
2. Commit, tag, and push:

```bash
git tag v0.1.0
git push origin main --tags
```

The [Publish](.github/workflows/publish.yml) workflow builds the package and uploads it to PyPI.

### Local build test

```bash
pip install -e ".[dev]"
python -m build
python -m twine check dist/*
```

Manual upload (if needed):

```bash
python -m twine upload dist/*
```

## Interactive mode

```bash
i66tolls
```

1. **Direction** — `current`, eastbound, or westbound
   - `current` uses the system clock. If no toll period is active, prints a message and exits.
   - Eastbound/westbound continues to entry selection for that direction.
2. **Entry** — choose an entry interchange
3. **Exit** — choose an exit interchange
4. **When** — `current` or `historic` (skipped if you already chose `current` in step 1)
5. **Date/time** — for historic lookups (Typer has no datetime picker; InquirerPy prompts for `MM/DD/YYYY HH:MM AM/PM`)

Use **↑/↓** and **Enter** to select. Press **←** to go back to the previous step (even for values pre-filled from the command line).

## Non-interactive mode

Provide entry and exit IDs (and any other options) to skip prompts:

```bash
i66tolls 1 10 -c
i66tolls 1 10 --current
i66tolls 16 1 -w -c
i66tolls 1 10 -t "06/10/2026 08:00 AM"
```

When both entry and exit are given, direction is inferred automatically.

### Options

| Flag | Description |
|------|-------------|
| `-e`, `--eastbound` | Eastbound route |
| `-w`, `--westbound` | Westbound route |
| `-c`, `--current` | Use the current toll rate |
| `-t`, `--time` | Historic date/time (`MM/DD/YYYY HH:MM AM/PM`, US/Eastern) |

### Conflicts

- `--eastbound` and `--westbound` cannot be used together
- `--current` and `--time` cannot be used together
- Provide both entry and exit IDs, or neither

Partial arguments (e.g. only entry) require a TTY for the interactive wizard.

## Toll hours

| Direction | Hours |
|-----------|-------|
| Eastbound (toward DC) | Weekdays 5:30–9:30 AM |
| Westbound (toward Beltway) | Weekdays 3:00–7:00 PM |

Outside these windows, current tolls show as unavailable. Federal holidays are also toll-free.

## Entry and exit IDs

Run `i66tolls` and browse the interactive lists, or query the API directly:

```bash
curl -s "https://vai66tolls.com/Index?handler=BeginIntPartial&rbEastVal=true" | grep option
curl -s "https://vai66tolls.com/Index?handler=ExitIntPartial&bIntId=1&rbEastVal=true" | grep option
```

## Data source

This tool uses the same backend API as [vai66tolls.com](https://vai66tolls.com/). Amounts are estimates and can change before you reach the road.

`reference/tolls.py` is the original Alexa skill that used a SmarterRoads XML feed. That public endpoint is no longer available.
