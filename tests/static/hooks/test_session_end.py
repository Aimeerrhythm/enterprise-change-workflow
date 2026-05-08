"""Unit tests for hooks/session-end.py

Tests the SessionEnd hook's cleanup behavior:
- Marks session-state.md status as "ended" with timestamp (via STATUS YAML block)
- Cleans up transient state files
- Graceful handling when no state exists
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def session_end():
    """Import session-end.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "session_end",
        HOOKS_DIR / "session-end.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Mark Session Ended
# ══════════════════════════════════════════════════════

_STATUS_BLOCK = """\
# ECW Session State

<!-- ECW:STATUS:START -->
risk_level: P1
current_phase: phase2-complete
auto_continue: true
<!-- ECW:STATUS:END -->
"""


class TestMarkSessionEnded:
    """Tests for _mark_session_ended function — uses STATUS YAML block (issue #54)."""

    def test_writes_session_status_to_status_block(self, session_end, tmp_path):
        """session_status field is written into the STATUS marker block."""
        state_file = tmp_path / "session-state.md"
        state_file.write_text(_STATUS_BLOCK)

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()
        assert "session_status:" in content
        assert "ended" in content

    def test_session_status_inside_markers(self, session_end, tmp_path):
        """session_status is placed within ECW:STATUS markers, not appended at end."""
        state_file = tmp_path / "session-state.md"
        state_file.write_text(_STATUS_BLOCK)

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()

        # Find marker positions
        start_idx = content.find("<!-- ECW:STATUS:START -->")
        end_idx = content.find("<!-- ECW:STATUS:END -->")
        ended_idx = content.find("session_status:")
        assert start_idx < ended_idx < end_idx, (
            "session_status must be inside STATUS markers"
        )

    def test_existing_fields_preserved(self, session_end, tmp_path):
        """Existing STATUS fields (risk_level, etc.) are preserved after update."""
        state_file = tmp_path / "session-state.md"
        state_file.write_text(_STATUS_BLOCK)

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()
        assert "risk_level: P1" in content or "risk_level" in content
        assert "current_phase" in content

    def test_noop_when_no_status_block(self, session_end, tmp_path):
        """No STATUS block → file unchanged (update_status_fields no-ops)."""
        original = "# ECW\nsome content without markers\n"
        state_file = tmp_path / "session-state.md"
        state_file.write_text(original)

        session_end._mark_session_ended(str(state_file))
        assert state_file.read_text() == original

    def test_file_unreadable_no_exception(self, session_end, tmp_path):
        """Unreadable file path does not raise an exception."""
        session_end._mark_session_ended(str(tmp_path / "nonexistent.md"))  # Should not raise


# ══════════════════════════════════════════════════════
# State File Cleanup
# ══════════════════════════════════════════════════════

class TestCleanupStateFiles:
    """Tests for _cleanup_state_files function."""

    def test_removes_modified_files_txt(self, session_end, tmp_path):
        """Removes modified-files.txt on session end."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        mf = state_dir / "modified-files.txt"
        mf.write_text("src/main.py\nsrc/util.py\n")

        session_end._cleanup_state_files(str(tmp_path))
        assert not mf.exists()

    def test_removes_tool_call_counter(self, session_end, tmp_path):
        """Removes tool-call-count.txt so next session starts from zero."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        counter = state_dir / "tool-call-count.txt"
        counter.write_text("87")

        session_end._cleanup_state_files(str(tmp_path))
        assert not counter.exists()

    def test_no_error_when_no_state_dir(self, session_end, tmp_path):
        """No error when state directory doesn't exist."""
        session_end._cleanup_state_files(str(tmp_path))  # Should not raise


# ══════════════════════════════════════════════════════
# Main Function
# ══════════════════════════════════════════════════════

class TestSessionEndMain:
    """Tests for the main() function."""

    def test_no_state_returns_continue(self, session_end, tmp_path):
        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_end.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"

    def test_marks_state_and_cleans_up(self, session_end, tmp_path):
        """Full flow: marks ended in STATUS block + cleans up modified-files.txt."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "test-wf"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(_STATUS_BLOCK)
        mf = tmp_path / ".claude" / "ecw" / "state" / "modified-files.txt"
        mf.parent.mkdir(parents=True, exist_ok=True)
        mf.write_text("foo.py\n")

        # ecw.yml required for main() to proceed
        ecw_dir = tmp_path / ".claude" / "ecw"
        (ecw_dir / "ecw.yml").write_text("project:\n  name: test\n")

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_end.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"

        assert "ended" in state_file.read_text()
        assert not mf.exists()

    def test_empty_cwd_returns_continue(self, session_end):
        input_data = {"cwd": ""}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_end.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"


class TestSessionEndScriptExists:
    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "session-end.py").exists()
