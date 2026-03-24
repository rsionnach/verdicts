"""Verdict CLI — query verdict stores from the command line."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

from nthlayer_learn.sqlite_store import SQLiteVerdictStore
from nthlayer_learn.store import AccuracyFilter, VerdictFilter

_DURATION_RE = re.compile(r"^(\d+)(s|m|h|d|w)$")

_DURATION_UNITS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}


def _parse_window(window: str) -> timedelta:
    match = _DURATION_RE.match(window)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{window}'. Use format: 30d, 24h, 7d, etc."
        )
    value, unit = int(match.group(1)), match.group(2)
    return timedelta(seconds=value * _DURATION_UNITS[unit])


def _cmd_accuracy(args: argparse.Namespace) -> None:
    store = SQLiteVerdictStore(args.db)
    try:
        from_time = None
        if args.window:
            from_time = datetime.now(timezone.utc) - _parse_window(args.window)

        report = store.accuracy(AccuracyFilter(
            producer_system=args.producer,
            from_time=from_time,
        ))

        print(f"Accuracy Report: {report.producer}")
        print(f"  Total verdicts:    {report.total}")
        print(f"  Resolved:          {report.total_resolved}")
        print(f"  Confirmation rate: {report.confirmation_rate * 100:.1f}%")
        print(f"  Override rate:     {report.override_rate * 100:.1f}%")
        print(f"  Partial rate:      {report.partial_rate * 100:.1f}%")
        print(f"  Pending rate:      {report.pending_rate * 100:.1f}%")
        print(f"  Mean confidence (confirmed):  {report.mean_confidence_on_confirmed:.3f}")
        print(f"  Mean confidence (overridden): {report.mean_confidence_on_overridden:.3f}")
    finally:
        store.close()


def _cmd_list(args: argparse.Namespace) -> None:
    store = SQLiteVerdictStore(args.db)
    try:
        verdicts = store.query(VerdictFilter(
            producer_system=args.producer,
            status=args.status,
            limit=args.limit,
        ))

        if not verdicts:
            print("No verdicts found.")
            return

        for v in verdicts:
            ts = v.timestamp.strftime("%Y-%m-%d %H:%M")
            status = v.outcome.status
            conf = f"{v.judgment.confidence:.2f}"
            print(
                f"{v.id}  {ts}  {status:<12}  "
                f"conf={conf}  {v.producer.system}  {v.subject.ref}"
            )
    finally:
        store.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nthlayer-learn", description="Query verdict stores")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    # accuracy
    acc = sub.add_parser("accuracy", help="Show accuracy report for a producer")
    acc.add_argument("--producer", required=True, help="Producer system name")
    acc.add_argument("--window", default=None, help="Time window (e.g. 30d, 24h)")
    acc.add_argument("--db", default="verdicts.db", help="Path to SQLite store")

    # list
    lst = sub.add_parser("list", help="List verdicts")
    lst.add_argument("--producer", default=None, help="Filter by producer")
    lst.add_argument("--status", default=None, help="Filter by outcome status")
    lst.add_argument("--limit", type=int, default=20, help="Max results (default 20)")
    lst.add_argument("--db", default="verdicts.db", help="Path to SQLite store")

    args = parser.parse_args(argv)

    if args.command == "accuracy":
        _cmd_accuracy(args)
    elif args.command == "list":
        _cmd_list(args)
