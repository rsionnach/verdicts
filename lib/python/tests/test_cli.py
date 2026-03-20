"""Tests for the verdict CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from nthlayer_learn import SQLiteVerdictStore, create


def _seed_store(db_path: str) -> None:
    """Seed a SQLite store with sample verdicts for CLI testing."""
    store = SQLiteVerdictStore(db_path)

    # 3 confirmed, 1 overridden, 1 pending — all from "arbiter"
    v1 = create(
        subject={"type": "agent_output", "ref": "pr-101", "summary": "Code review"},
        judgment={"action": "approve", "confidence": 0.92},
        producer={"system": "arbiter"},
    )
    store.put(v1)
    store.resolve(v1.id, "confirmed")

    v2 = create(
        subject={"type": "agent_output", "ref": "pr-102", "summary": "Security scan"},
        judgment={"action": "reject", "confidence": 0.85},
        producer={"system": "arbiter"},
    )
    store.put(v2)
    store.resolve(v2.id, "confirmed")

    v3 = create(
        subject={"type": "agent_output", "ref": "pr-103", "summary": "Lint check"},
        judgment={"action": "approve", "confidence": 0.78},
        producer={"system": "arbiter"},
    )
    store.put(v3)
    store.resolve(v3.id, "overridden")

    v4 = create(
        subject={"type": "agent_output", "ref": "pr-104", "summary": "Dep audit"},
        judgment={"action": "approve", "confidence": 0.95},
        producer={"system": "arbiter"},
    )
    store.put(v4)
    store.resolve(v4.id, "confirmed")

    v5 = create(
        subject={"type": "correlation", "ref": "snap-001", "summary": "Latency spike"},
        judgment={"action": "flag", "confidence": 0.60},
        producer={"system": "sitrep"},
    )
    store.put(v5)
    # v5 stays pending

    store.close()


@pytest.fixture()
def seeded_db(tmp_path: Path) -> str:
    db_path = str(tmp_path / "test.db")
    _seed_store(db_path)
    return db_path


# ---------------------------------------------------------------------------
# verdict accuracy
# ---------------------------------------------------------------------------


class TestAccuracyCommand:
    def test_accuracy_basic(self, seeded_db: str) -> None:
        """accuracy --producer arbiter shows confirmation/override rates."""

        out = _run_cli(["accuracy", "--producer", "arbiter", "--db", seeded_db])
        assert "arbiter" in out
        # 3 confirmed / 4 resolved = 75%
        assert "75.0%" in out
        # 1 overridden / 4 resolved = 25%
        assert "25.0%" in out

    def test_accuracy_no_data(self, tmp_path: Path) -> None:
        """accuracy for an unknown producer shows zeros gracefully."""
        db_path = str(tmp_path / "empty.db")
        SQLiteVerdictStore(db_path).close()
        out = _run_cli(["accuracy", "--producer", "ghost", "--db", db_path])
        assert "ghost" in out
        assert "0" in out

    def test_accuracy_requires_producer(self, seeded_db: str) -> None:
        """accuracy without --producer exits with error."""
        with pytest.raises(SystemExit):
            _run_cli(["accuracy", "--db", seeded_db])

    def test_accuracy_with_window(self, seeded_db: str) -> None:
        """accuracy --window 30d filters to recent verdicts."""
        out = _run_cli(
            ["accuracy", "--producer", "arbiter", "--window", "30d", "--db", seeded_db]
        )
        # All test verdicts are recent, so same result
        assert "75.0%" in out


# ---------------------------------------------------------------------------
# verdict list
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_by_producer(self, seeded_db: str) -> None:
        """list --producer arbiter shows only arbiter verdicts."""
        out = _run_cli(["list", "--producer", "arbiter", "--db", seeded_db])
        assert "arbiter" in out
        # Should show 4 arbiter verdicts
        assert "pr-101" in out
        assert "pr-104" in out
        # Should NOT show sitrep verdict
        assert "snap-001" not in out

    def test_list_by_status(self, seeded_db: str) -> None:
        """list --status pending shows only pending verdicts."""
        out = _run_cli(["list", "--status", "pending", "--db", seeded_db])
        assert "snap-001" in out
        assert "pr-101" not in out

    def test_list_with_limit(self, seeded_db: str) -> None:
        """list --limit 2 shows at most 2 verdicts."""
        out = _run_cli(["list", "--limit", "2", "--db", seeded_db])
        # Count verdict ID lines (vrd- prefix)
        vrd_lines = [line for line in out.splitlines() if "vrd-" in line]
        assert len(vrd_lines) == 2

    def test_list_all(self, seeded_db: str) -> None:
        """list with no filters shows all verdicts."""
        out = _run_cli(["list", "--db", seeded_db])
        vrd_lines = [line for line in out.splitlines() if "vrd-" in line]
        assert len(vrd_lines) == 5

    def test_list_empty_store(self, tmp_path: Path) -> None:
        """list on empty store shows no verdicts message."""
        db_path = str(tmp_path / "empty.db")
        SQLiteVerdictStore(db_path).close()
        out = _run_cli(["list", "--db", db_path])
        assert "no verdicts" in out.lower() or len(out.strip().splitlines()) <= 1


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


class TestCLIEdgeCases:
    def test_no_subcommand(self) -> None:
        """Running with no subcommand shows help."""
        with pytest.raises(SystemExit):
            _run_cli([])

    def test_invalid_db_path(self) -> None:
        """Non-existent db path is handled gracefully."""
        # Should still work — SQLite creates the file
        out = _run_cli(["list", "--db", "/tmp/verdict_test_nonexistent.db"])
        assert "no verdicts" in out.lower() or len(out.strip().splitlines()) <= 1

    def test_window_parsing(self, seeded_db: str) -> None:
        """Window flag parses duration strings: 7d, 24h, 90d."""
        # Should not crash on any valid duration
        for window in ["7d", "24h", "90d", "1h"]:
            out = _run_cli(
                ["accuracy", "--producer", "arbiter", "--window", window, "--db", seeded_db]
            )
            assert "arbiter" in out


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


class TestEntryPoint:
    def test_module_invocable(self, seeded_db: str) -> None:
        """python -m verdict works as an entry point."""
        result = subprocess.run(
            [sys.executable, "-m", "nthlayer_learn", "list", "--db", seeded_db],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


def _run_cli(args: list[str]) -> str:
    """Invoke the CLI main() and capture stdout."""
    import io
    import contextlib

    from nthlayer_learn.cli import main

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(args)
    return buf.getvalue()
