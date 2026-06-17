# i66tolls

Vibe coded command-line tool for checking tolls on I-66 inside the Capital Beltway (between I-495 and the Theodore Roosevelt Bridge).

Run it with no arguments for an interactive wizard, or pass entry/exit IDs and flags for a quick lookup.

Data comes from VDOT's official toll calculator at [vai66tolls.com](https://vai66tolls.com/).

DISCLAIMER: I am not affiliated with i66 or VDOT in any way. I'm just some guy who doesnt like using the website. So I can't make any assurances you will pay what you see in this CLI, it's just relaying what it gets from the (undocumented) API.

![Demo](assets/demo.gif)

## How the toll works (in my understanding)
There are 3-4 tolling segments in each direction. The price you pay for driving on a segment is locked in when you enter that segment. This may give you the impression your toll price is locked in when you enter i66. In fact, if you enter on segment 1 the toll for segment 2 can still change while you're driving on segment 1. This is why it's impossible to know your entire toll before you enter i66. And why, in my view, this tolling system should be illegal. The tills provided by the website and this command line tool can only be estimates because it’s physically impossible to enter all 3-4 segments at the same time. 

There are more exits and entries than segments. The 3 segments are shown in this graphic


[![I-66 toll segments](docs/i-66-customer-map-v4.png)](https://ride66express.com/wp-content/uploads/2023/09/i-66-customer-map-v4.pdf)


Eastbound segments (AM commute):
- **Segment 1:** From I-495 to the Dulles Connector Road (Exit 67).
- **Segment 2:** From the Dulles Connector Road to Fairfax Drive (Exit 71).
- **Segment 3:** From Fairfax Drive to US 29 in Rosslyn.

Westbound segments (PM commute):
- **Segment 1A:** From US 29 in Rosslyn to Glebe Road (Exit 72).
- **Segment 1B:** From Glebe Road to the Dulles Connector Road (Exit 67).
- **Segment 2:** From the Dulles Connector Road to Sycamore Street.
- **Segment 3:** From Sycamore Street to I-495.

They are supposed to show you your toll before you enter each segment, but as we all know the signs are broken half the time. So there's often no way for you to know how much you're paying before or during your commute.

## Requirements

- Python 3.10+
- [Typer](https://typer.tiangolo.com/) for the CLI
- [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/) and [its-a-dt](https://pypi.org/project/its-a-dt/) for interactive prompts

## Install

From PyPI:

```bash
pip install i66tolls
```

From source:

```bash
pip install -e .
```

## Interactive mode

```bash
i66tolls
```

1. **Direction** — current, eastbound, or westbound
   - current uses the system clock. If no toll period is active, prints a message and exits.
   - Eastbound/westbound continues to entry selection for that direction.
2. **Entry** — choose an entry interchange
3. **Exit** — choose an exit interchange
4. **When** — `current estimate` or `historic` (skipped if you already chose `current estimate` in step 1)
5. **Date/time** — for historic lookups, an interactive date/time picker ([its-a-dt](https://pypi.org/project/its-a-dt/))

Use **↑/↓** and **Enter** to select. Press **←** to go back to the previous step (even for values pre-filled from the command line).

## Provide arguments to skip interactive steps

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

The old public endpoint you might see in other projects is no longer available. Maybe they were hitting it too hard, who knows.
