"""Command-line interface for I-66 toll lookups."""

from __future__ import annotations

import argparse
import sys
from typing import Literal, Optional

from i66tolls.api import get_toll, list_entries, list_exits, resolve_entry, resolve_exit

DIRECTION_LABELS = {
    "eastbound": "Eastbound (AM, 5:30–9:30)",
    "westbound": "Westbound (PM, 3:00–7:00)",
}


def _parse_direction(args: argparse.Namespace) -> Optional[Literal["eastbound", "westbound"]]:
    if args.east and args.west:
        print("error: use only one of --east or --west", file=sys.stderr)
        sys.exit(1)
    if args.east:
        return "eastbound"
    if args.west:
        return "westbound"
    return None


def cmd_list_entries(_: argparse.Namespace) -> None:
    by_direction: dict[str, list] = {"eastbound": [], "westbound": []}
    for entry in list_entries():
        by_direction[entry.direction].append(entry)

    for direction in ("eastbound", "westbound"):
        print(DIRECTION_LABELS[direction])
        for entry in by_direction[direction]:
            print(f"  {entry.id:>2}  {entry.name}")
        print()


def cmd_list_exits(args: argparse.Namespace) -> None:
    try:
        entry = resolve_entry(args.entry, _parse_direction(args))
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"Exits from {entry.name} ({entry.direction}):")
    for exit_id, name in list_exits(entry):
        print(f"  {exit_id:>2}  {name}")


def cmd_toll(args: argparse.Namespace) -> None:
    try:
        entry = resolve_entry(args.entry, _parse_direction(args))
        exit_id, exit_name = resolve_exit(entry, args.exit)
        amount = get_toll(entry, exit_id)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"{entry.name} → {exit_name}: ${amount:.2f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="i66tolls", description="I-66 inside-the-Beltway toll lookup")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-entries", help="list toll entry points")

    exits_parser = subparsers.add_parser("list-exits", help="list exits for an entry")
    exits_parser.add_argument("entry", help="entry name or ID")
    exits_parser.add_argument("--east", action="store_true", help="only match eastbound entries")
    exits_parser.add_argument("--west", action="store_true", help="only match westbound entries")

    toll_parser = subparsers.add_parser("toll", help="current toll for an entry/exit pair")
    toll_parser.add_argument("entry", help="entry name or ID")
    toll_parser.add_argument("exit", help="exit name or ID")
    toll_parser.add_argument("--east", action="store_true", help="only match eastbound entries")
    toll_parser.add_argument("--west", action="store_true", help="only match westbound entries")

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-entries":
        cmd_list_entries(args)
    elif args.command == "list-exits":
        cmd_list_exits(args)
    elif args.command == "toll":
        cmd_toll(args)


if __name__ == "__main__":
    main()
