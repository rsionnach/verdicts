"""Verdict — The Atomic Unit of AI Judgment.

A transport library for creating, linking, resolving, and querying verdicts.
No model calls. No judgment. Just structured decision records.
"""

from nthlayer_learn.core import create, link, resolve, supersede
from nthlayer_learn.models import AccuracyReport, Verdict
from nthlayer_learn.serialise import from_dict, from_json, to_dict, to_json
from nthlayer_learn.sqlite_store import SQLiteVerdictStore
from nthlayer_learn.store import AccuracyFilter, MemoryStore, VerdictFilter, VerdictStore

__all__ = [
    "create",
    "link",
    "resolve",
    "supersede",
    "Verdict",
    "AccuracyReport",
    "VerdictStore",
    "MemoryStore",
    "SQLiteVerdictStore",
    "VerdictFilter",
    "AccuracyFilter",
    "to_dict",
    "to_json",
    "from_dict",
    "from_json",
]
