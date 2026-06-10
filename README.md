# i66tolls

Command-line tool for checking current tolls on I-66 inside the Capital Beltway (between I-495 and the Theodore Roosevelt Bridge).

Data comes from VDOT's official toll calculator at [vai66tolls.com](https://vai66tolls.com/).

## Requirements

- Python 3.10+
- No third-party dependencies

## Install

```bash
pip install -e .
```

Or run without installing:

```bash
python -m i66tolls list-entries
```

## Usage

### List entry points

```bash
i66tolls list-entries
```

Shows eastbound (AM) and westbound (PM) entry interchanges with their IDs.

### List exits for an entry

```bash
i66tolls list-exits "I-66 West"
i66tolls list-exits 1
```

Entry can be an ID or a partial name (case-insensitive).

### Get the current toll

```bash
i66tolls toll "I-66 West" Westmoreland
i66tolls toll 16 1 --west
```

Exit can also be an ID or partial name.

### Direction flags

Some IDs and names exist in both directions (e.g. `4` / Route 7). Use `--east` or `--west` to disambiguate:

```bash
i66tolls list-exits 4 --east
i66tolls toll 4 10 --east
```

## Toll hours

Tolls are only charged during peak periods on weekdays:

| Direction | Hours |
|-----------|-------|
| Eastbound (toward DC) | 5:30–9:30 AM |
| Westbound (toward Beltway) | 3:00–7:00 PM |

Outside these windows, tolls show as `$0.00`. Federal holidays are also toll-free.

## Data source

This tool queries the same backend API used by [vai66tolls.com](https://vai66tolls.com/). Toll amounts are estimates and can change before you reach the road.

The `reference/tolls.py` file is the original [Alexa skill](https://www.mcgurrin.info/robots/570/) that used a different SmarterRoads XML feed. That public endpoint is no longer available; this CLI uses the vai66tolls API instead.
