"""Unit tests for hooks/session-end.py

Tests the SessionEnd hook's cleanup behavior:
- Marks session-state.md as ended
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

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


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

class TestMarkSessionEnded:
    """Tests for _mark_session_ended function."""

    def test_updates_existing_status(self, session_end, tmp_path):
        """Updates existing Status field to 'ended'."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "# ECW\n- **Risk Level**: P1\n- **Status**: active\n"
        )

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()
        assert "ended" in content
        assert "active" not in content

    def test_adds_status_after_current_phase(self, session_end, tmp_path):
        """Adds Status field after Current Phase when no Status exists."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "# ECW\n- **Current Phase**: phase2-complete\n"
        )

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()
        assert "**Status**: ended" in content
        assert "Current Phase" in content

    def test_appends_status_when_no_phase(self, session_end, tmp_path):
        """Appends Status field when neither Status nor Current Phase exist."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text("# ECW\n- **Risk Level**: P2\n")

        session_end._mark_session_ended(str(state_file))
        content = state_file.read_text()
        assert "**Status**: ended" in content


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
        """Full flow: marks ended + cleans up modified-files.txt."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text("# ECW\n- **Risk Level**: P1\n- **Status**: active\n")
        mf = state_dir / "modified-files.txt"
        mf.write_text("foo.py\n")

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
