"""Unit tests for hooks/compact-suggest.py

Tests the proactive compaction suggestion sub-hook:
- Counter file read/write
- Threshold logic (first trigger + repeat interval)
- check() sub-hook interface
- Environment variable override
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def compact_suggest():
    """Import compact-suggest.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "compact_suggest",
        HOOKS_DIR / "compact-suggest.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Counter File I/O
# ══════════════════════════════════════════════════════

class TestCounterIO:
    def test_read_returns_zero_when_missing(self, compact_suggest, tmp_path):
        path = tmp_path / "counter.txt"
        assert compact_suggest._read_counter(str(path)) == 0

    def test_write_and_read_roundtrip(self, compact_suggest, tmp_path):
        path = tmp_path / "counter.txt"
        compact_suggest._write_counter(str(path), 42)
        assert compact_suggest._read_counter(str(path)) == 42

    def test_read_handles_corrupt_file(self, compact_suggest, tmp_path):
        path = tmp_path / "counter.txt"
        path.write_text("not-a-number")
        assert compact_suggest._read_counter(str(path)) == 0

    def test_write_creates_parent_dirs(self, compact_suggest, tmp_path):
        path = tmp_path / "deep" / "nested" / "counter.txt"
        compact_suggest._write_counter(str(path), 10)
        assert compact_suggest._read_counter(str(path)) == 10


# ══════════════════════════════════════════════════════
# Threshold Logic
# ══════════════════════════════════════════════════════

class TestShouldSuggest:
    def test_below_threshold_no_suggest(self, compact_suggest):
        assert compact_suggest._should_suggest(10, 50, 25) is False
        assert compact_suggest._should_suggest(49, 50, 25) is False

    def test_at_first_threshold(self, compact_suggest):
        assert compact_suggest._should_suggest(50, 50, 25) is True

    def test_after_threshold_at_interval(self, compact_suggest):
        assert compact_suggest._should_suggest(75, 50, 25) is True
        assert compact_suggest._should_suggest(100, 50, 25) is True

    def test_after_threshold_between_intervals(self, compact_suggest):
        assert compact_suggest._should_suggest(60, 50, 25) is False
        assert compact_suggest._should_suggest(80, 50, 25) is False


class TestGetThresholds:
    def test_defaults(self, compact_suggest):
        with patch.dict(os.environ, {}, clear=True):
            first, repeat = compact_suggest._get_thresholds()
            assert first == 50
            assert repeat == 25

    def test_env_override(self, compact_suggest):
        with patch.dict(os.environ, {"ECW_COMPACT_THRESHOLD": "30"}):
            first, repeat = compact_suggest._get_thresholds()
            assert first == 30
            assert repeat == 15  # half of 30

    def test_env_invalid_uses_default(self, compact_suggest):
        with patch.dict(os.environ, {"ECW_COMPACT_THRESHOLD": "abc"}):
            first, repeat = compact_suggest._get_thresholds()
            assert first == 50

    def test_env_zero_uses_default(self, compact_suggest):
        with patch.dict(os.environ, {"ECW_COMPACT_THRESHOLD": "0"}):
            first, repeat = compact_suggest._get_thresholds()
            assert first == 50


# ══════════════════════════════════════════════════════
# check() Sub-Hook Interface
# ══════════════════════════════════════════════════════

class TestCheck:
    def _setup_counter(self, tmp_path, count):
        """Set up state dir with a pre-set counter."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        counter_file = state_dir / "tool-call-count.txt"
        counter_file.write_text(str(count))
        return state_dir

    def test_no_suggest_below_threshold(self, compact_suggest, tmp_path):
        self._setup_counter(tmp_path, 5)
        action, msg = compact_suggest.check(
            {"cwd": str(tmp_path), "tool_name": "Read"}, {}
        )
        assert action == "continue"
        assert msg == ""

    def test_suggest_at_threshold(self, compact_suggest, tmp_path):
        self._setup_counter(tmp_path, 49)  # will become 50 after increment
        action, msg = compact_suggest.check(
            {"cwd": str(tmp_path), "tool_name": "Read"}, {}
        )
        assert action == "continue"
        assert "Compaction suggested" in msg
        assert "50" in msg

    def test_no_block_ever(self, compact_suggest, tmp_path):
        """Compact suggest never blocks — always returns 'continue'."""
        self._setup_counter(tmp_path, 49)
        action, _ = compact_suggest.check(
            {"cwd": str(tmp_path), "tool_name": "Read"}, {}
        )
        assert action == "continue"

    def test_increments_counter(self, compact_suggest, tmp_path):
        self._setup_counter(tmp_path, 10)
        compact_suggest.check({"cwd": str(tmp_path), "tool_name": "Read"}, {})
        # Verify counter was incremented
        counter_file = tmp_path / ".claude" / "ecw" / "state" / "tool-call-count.txt"
        assert int(counter_file.read_text().strip()) == 11

    def test_empty_cwd_returns_continue(self, compact_suggest):
        action, msg = compact_suggest.check({"cwd": "", "tool_name": "Read"}, {})
        assert action == "continue"
        assert msg == ""

    def test_suggest_at_repeat_interval(self, compact_suggest, tmp_path):
        self._setup_counter(tmp_path, 74)  # will become 75 after increment
        action, msg = compact_suggest.check(
            {"cwd": str(tmp_path), "tool_name": "Read"}, {}
        )
        assert action == "continue"
        assert "Compaction suggested" in msg
        assert "75" in msg


class TestCompactSuggestScriptExists:
    def test_script_exists(self):
        assert (HOOKS_DIR / "compact-suggest.py").exists()
