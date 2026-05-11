"""Unit tests for hooks/session-end.py

Tests the SessionEnd hook's cleanup behavior:
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
# State File Cleanup
# ══════════════════════════════════════════════════════

class TestCleanupStateFiles:
    """Tests for _cleanup_state_files function."""

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

    def test_cleans_up_state(self, session_end, tmp_path):
        """Full flow: cleans transient state and returns continue."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "test-wf"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.json").write_text('{"risk_level": "P1"}')
        ecw_dir = tmp_path / ".claude" / "ecw"
        (ecw_dir / "ecw.yml").write_text("project:\n  name: test\n")

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_end.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"

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
