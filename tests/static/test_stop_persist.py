"""Unit tests for hooks/stop-persist.py

Tests the Stop hook's state persistence behavior:
- Marker-based idempotent updates
- Activity summary extraction
- Graceful handling when no session state exists
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def stop_persist():
    """Import stop-persist.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "stop_persist",
        HOOKS_DIR / "stop-persist.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Activity Summary
# ══════════════════════════════════════════════════════

class TestExtractActivitySummary:
    """Tests for _extract_activity_summary function."""

    def test_no_tool_calls(self, stop_persist):
        summary = stop_persist._extract_activity_summary({})
        assert "No tool calls" in summary

    def test_counts_tools(self, stop_persist):
        input_data = {
            "tool_calls": [
                {"tool_name": "Edit", "tool_input": {"file_path": "/a/b.py"}},
                {"tool_name": "Edit", "tool_input": {"file_path": "/a/c.py"}},
                {"tool_name": "Read", "tool_input": {}},
            ]
        }
        summary = stop_persist._extract_activity_summary(input_data)
        assert "Edit(2)" in summary
        assert "Read(1)" in summary

    def test_tracks_modified_files(self, stop_persist):
        input_data = {
            "tool_calls": [
                {"tool_name": "Write", "tool_input": {"file_path": "/a/test.py"}},
            ]
        }
        summary = stop_persist._extract_activity_summary(input_data)
        assert "test.py" in summary


# ══════════════════════════════════════════════════════
# Marker-Based Updates
# ══════════════════════════════════════════════════════

class TestMarkerUpdates:
    """Tests for _update_with_markers function (delegates to marker_utils)."""

    def test_appends_when_no_markers(self, stop_persist):
        content = "# ECW Session State\n- **Risk Level**: P1\n"
        result = stop_persist._update_with_markers(content, "- **Last Updated**: now")
        assert "ECW:STOP:START" in result
        assert "Risk Level" in result  # Original content preserved

    def test_replaces_existing_markers(self, stop_persist):
        content = (
            "# ECW Session State\n"
            "<!-- ECW:STOP:START -->\n- **Last Updated**: old\n<!-- ECW:STOP:END -->\n"
            "## Ledger\n"
        )
        result = stop_persist._update_with_markers(content, "- **Last Updated**: new")
        assert "old" not in result
        assert "new" in result
        assert "Ledger" in result  # Content after marker preserved


# ══════════════════════════════════════════════════════
# Main Function
# ══════════════════════════════════════════════════════

class TestStopPersistMain:
    """Tests for the main() function."""

    def test_no_state_file_returns_continue(self, stop_persist, tmp_path):
        """No session-state.md → just return continue."""
        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                stop_persist.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"

    def test_updates_existing_state(self, stop_persist, tmp_path):
        """With session-state.md → updates with markers."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text("# ECW Session State\n- **Risk Level**: P0\n")

        input_data = {
            "cwd": str(tmp_path),
            "tool_calls": [{"tool_name": "Read", "tool_input": {}}],
        }
        with patch("json.load", return_value=input_data):
            with patch("builtins.print"):
                stop_persist.main()

        updated = state_file.read_text()
        assert "ECW:STOP:START" in updated
        assert "Last Updated" in updated
        assert "Risk Level" in updated  # Original preserved

    def test_skips_ended_session(self, stop_persist, tmp_path):
        """Session with Status: ended → no update."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        original = "# ECW\n- **Status**: ended\n"
        state_file.write_text(original)

        input_data = {"cwd": str(tmp_path), "tool_calls": []}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print"):
                stop_persist.main()

        assert state_file.read_text() == original  # Unchanged

    def test_empty_cwd_returns_continue(self, stop_persist):
        input_data = {"cwd": ""}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                stop_persist.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"


class TestStopPersistScriptExists:
    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "stop-persist.py").exists()
