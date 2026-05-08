"""Unit tests for hooks/trace_logger.py

Covers: basic write, field completeness, best-effort error handling,
rotation, concurrent safety, JSON format correctness.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def trace_logger():
    """Import trace_logger.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "trace_logger",
        HOOKS_DIR / "trace_logger.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def trace_dir(tmp_path):
    """Return tmp_path as an ECW project root for trace logging."""
    ecw_dir = tmp_path / ".claude" / "ecw"
    ecw_dir.mkdir(parents=True)
    (ecw_dir / "ecw.yml").write_text("project:\n  name: test\n")
    return tmp_path


def _trace_path(project_root):
    """Return the expected trace file path for a given project root."""
    return project_root / ".claude" / "ecw" / "state" / "hook-trace.jsonl"


# ══════════════════════════════════════════════════════
# Basic Write
# ══════════════════════════════════════════════════════

class TestBasicWrite:
    """Calling log_trace creates the file and appends a valid record."""

    def test_file_created(self, trace_logger, trace_dir):
        """After log_trace, the JSONL file should exist."""
        trace_logger.log_trace(str(trace_dir), "test-hook", "TestEvent")
        assert _trace_path(trace_dir).exists()

    def test_record_written(self, trace_logger, trace_dir):
        """After log_trace, the file contains exactly one line."""
        trace_logger.log_trace(str(trace_dir), "test-hook", "TestEvent")
        lines = _trace_path(trace_dir).read_text().strip().split("\n")
        assert len(lines) == 1

    def test_multiple_writes_append(self, trace_logger, trace_dir):
        """Multiple calls append, not overwrite."""
        trace_logger.log_trace(str(trace_dir), "hook-a", "Event1")
        trace_logger.log_trace(str(trace_dir), "hook-b", "Event2")
        lines = _trace_path(trace_dir).read_text().strip().split("\n")
        assert len(lines) == 2


# ══════════════════════════════════════════════════════
# Field Completeness
# ══════════════════════════════════════════════════════

class TestFieldCompleteness:
    """Required fields (ts, hook, event) are always present; kwargs are included."""

    def test_required_fields(self, trace_logger, trace_dir):
        """ts, hook, event must always be present."""
        trace_logger.log_trace(str(trace_dir), "dispatcher", "PreToolUse")
        line = _trace_path(trace_dir).read_text().strip()
        record = json.loads(line)
        assert "ts" in record
        assert record["hook"] == "dispatcher"
        assert record["event"] == "PreToolUse"

    def test_kwargs_written(self, trace_logger, trace_dir):
        """Extra keyword arguments are included in the record."""
        trace_logger.log_trace(
            str(trace_dir), "auto-continue", "PostToolUse",
            skill="ecw:writing-plans", action="inject_system_message"
        )
        line = _trace_path(trace_dir).read_text().strip()
        record = json.loads(line)
        assert record["skill"] == "ecw:writing-plans"
        assert record["action"] == "inject_system_message"

    def test_ts_is_iso_format(self, trace_logger, trace_dir):
        """Timestamp should be ISO 8601 format."""
        trace_logger.log_trace(str(trace_dir), "hook", "Event")
        line = _trace_path(trace_dir).read_text().strip()
        record = json.loads(line)
        # ISO format: YYYY-MM-DDTHH:MM:SS
        ts = record["ts"]
        assert "T" in ts
        assert len(ts) >= 19  # At least YYYY-MM-DDTHH:MM:SS

    def test_list_and_dict_kwargs(self, trace_logger, trace_dir):
        """Complex kwargs (lists, dicts) are serialized correctly."""
        trace_logger.log_trace(
            str(trace_dir), "dispatcher", "PreToolUse",
            sub_hooks_fired=["gateguard-fact-force", "secret-scan"],
            fields_updated={"Current Phase": "plan"}
        )
        line = _trace_path(trace_dir).read_text().strip()
        record = json.loads(line)
        assert record["sub_hooks_fired"] == ["gateguard-fact-force", "secret-scan"]
        assert record["fields_updated"] == {"Current Phase": "plan"}


# ══════════════════════════════════════════════════════
# Best-Effort: Never Raises
# ══════════════════════════════════════════════════════

class TestBestEffort:
    """log_trace should never raise exceptions."""

    def test_invalid_cwd_no_error(self, trace_logger):
        """Invalid (nonexistent) cwd should not raise."""
        # This path almost certainly doesn't exist
        trace_logger.log_trace("/nonexistent/path/abc123", "hook", "Event")

    def test_empty_cwd_no_error(self, trace_logger):
        """Empty cwd string should not raise."""
        trace_logger.log_trace("", "hook", "Event")

    def test_none_cwd_no_error(self, trace_logger):
        """None cwd should not raise."""
        trace_logger.log_trace(None, "hook", "Event")

    def test_empty_cwd_no_file_created(self, trace_logger, trace_dir):
        """Empty cwd should result in no file being created anywhere."""
        trace_logger.log_trace("", "hook", "Event")
        # Should not create the file
        assert not _trace_path(trace_dir).exists()

    def test_unserializable_kwarg_no_error(self, trace_logger, trace_dir):
        """Non-serializable kwargs should not raise (best-effort)."""
        trace_logger.log_trace(
            str(trace_dir), "hook", "Event",
            bad_value=object()
        )
        # Should not raise; file may or may not be created


# ══════════════════════════════════════════════════════
# Rotation
# ══════════════════════════════════════════════════════

class TestRotation:
    """File should be truncated when exceeding 512KB."""

    def test_rotation_triggers_at_512kb(self, trace_logger, trace_dir):
        """When file exceeds 512KB, it should be truncated to roughly half."""
        trace_file = _trace_path(trace_dir)
        trace_file.parent.mkdir(parents=True, exist_ok=True)

        # Write >512KB of data — each line ~80 bytes, need ~7000 lines
        lines = []
        for i in range(8000):
            record = {"ts": "2026-01-01T00:00:00", "hook": "test", "event": "E", "i": i, "pad": "x" * 20}
            lines.append(json.dumps(record) + "\n")
        trace_file.write_text("".join(lines))

        original_size = trace_file.stat().st_size
        assert original_size > 512 * 1024  # Confirm we're over the limit

        # Next log_trace should trigger rotation
        trace_logger.log_trace(str(trace_dir), "trigger", "Rotation")

        new_size = trace_file.stat().st_size
        assert new_size < original_size
        # Should keep roughly the second half plus the new record
        assert new_size > 0

    def test_rotation_preserves_valid_json_lines(self, trace_logger, trace_dir):
        """After rotation, all remaining lines should be valid JSON."""
        trace_file = _trace_path(trace_dir)
        trace_file.parent.mkdir(parents=True, exist_ok=True)

        # Write >512KB
        lines = []
        for i in range(8000):
            record = {"ts": "2026-01-01T00:00:00", "hook": "test", "event": "E", "i": i, "pad": "x" * 20}
            lines.append(json.dumps(record) + "\n")
        trace_file.write_text("".join(lines))

        trace_logger.log_trace(str(trace_dir), "trigger", "Rotation")

        for line in trace_file.read_text().strip().split("\n"):
            record = json.loads(line)  # Should not raise
            assert "hook" in record

    def test_no_rotation_under_512kb(self, trace_logger, trace_dir):
        """File under 512KB should not be truncated."""
        trace_file = _trace_path(trace_dir)
        trace_file.parent.mkdir(parents=True, exist_ok=True)

        # Write a small file
        for i in range(10):
            trace_logger.log_trace(str(trace_dir), "test", "Event", i=i)

        line_count_before = len(trace_file.read_text().strip().split("\n"))

        # Write one more
        trace_logger.log_trace(str(trace_dir), "test", "Event", i=10)

        line_count_after = len(trace_file.read_text().strip().split("\n"))
        assert line_count_after == line_count_before + 1


# ══════════════════════════════════════════════════════
# Concurrent Safety
# ══════════════════════════════════════════════════════

class TestConcurrentSafety:
    """Multiple sequential calls should not lose data."""

    def test_sequential_writes_no_data_loss(self, trace_logger, trace_dir):
        """100 sequential writes should produce exactly 100 lines."""
        for i in range(100):
            trace_logger.log_trace(str(trace_dir), "test", "Event", i=i)

        lines = _trace_path(trace_dir).read_text().strip().split("\n")
        assert len(lines) == 100

    def test_sequential_writes_all_valid_json(self, trace_logger, trace_dir):
        """All lines from sequential writes should be valid JSON."""
        for i in range(50):
            trace_logger.log_trace(str(trace_dir), "test", "Event", i=i)

        for line in _trace_path(trace_dir).read_text().strip().split("\n"):
            record = json.loads(line)
            assert "i" in record


# ══════════════════════════════════════════════════════
# JSON Format Correctness
# ══════════════════════════════════════════════════════

class TestJsonFormat:
    """Every line in the trace file must be valid JSON."""

    def test_each_line_valid_json(self, trace_logger, trace_dir):
        """Each line should parse as valid JSON."""
        trace_logger.log_trace(str(trace_dir), "hook-a", "Event1", key="val1")
        trace_logger.log_trace(str(trace_dir), "hook-b", "Event2", key="val2")

        content = _trace_path(trace_dir).read_text()
        for line in content.strip().split("\n"):
            json.loads(line)  # Should not raise

    def test_unicode_in_kwargs(self, trace_logger, trace_dir):
        """Unicode content in kwargs should be handled correctly."""
        trace_logger.log_trace(
            str(trace_dir), "post-edit-check", "PostToolUse",
            warning="空 catch 块 — 异常被吞没"
        )
        line = _trace_path(trace_dir).read_text().strip()
        record = json.loads(line)
        assert "空" in record["warning"]

    def test_newline_terminated(self, trace_logger, trace_dir):
        """File should end with a newline."""
        trace_logger.log_trace(str(trace_dir), "hook", "Event")
        content = _trace_path(trace_dir).read_text()
        assert content.endswith("\n")
