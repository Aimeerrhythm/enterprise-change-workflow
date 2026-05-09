"""Unit tests for hooks/stop-persist.py

Tests the Stop hook's context health advisory behavior:
- Phase transition detection
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

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


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
# Main Function
# ══════════════════════════════════════════════════════

class TestStopPersistMain:
    """Tests for the main() function."""

    def test_no_state_file_returns_continue(self, stop_persist, tmp_path):
        """No session-state.json → just return continue."""
        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                stop_persist.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"

    def test_skips_ended_session(self, stop_persist, tmp_path):
        """Session with session_status: ended → no update."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.json"
        import json as _json
        original = _json.dumps({"risk_level": "P1", "session_status": "ended"})
        state_file.write_text(original)

        input_data = {"cwd": str(tmp_path), "tool_calls": [{"type": "tool_use"}]}
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

    def test_skips_update_when_no_tool_calls(self, stop_persist, tmp_path):
        """Pure text responses (no tool calls) must not update session-state.json.

        Updating on every assistant turn creates noise that masks real phase transitions.
        """
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260429-ab12"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.json"
        import json as _json
        original = _json.dumps({"risk_level": "P1"})
        state_file.write_text(original)

        input_data = {"cwd": str(tmp_path), "tool_calls": []}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print"):
                stop_persist.main()

        assert state_file.read_text() == original, (
            "stop-persist must not modify session-state.json when tool_calls is empty"
        )


# ══════════════════════════════════════════════════════
# _extract_current_phase
# ══════════════════════════════════════════════════════

class TestExtractCurrentPhase:
    """Tests for _extract_current_phase from session-state content."""

    def test_extracts_phase(self, stop_persist):
        import json
        content = json.dumps({"current_phase": "implementation", "risk_level": "P0"})
        assert stop_persist._extract_current_phase(content) == "implementation"

    def test_returns_none_when_missing(self, stop_persist):
        assert stop_persist._extract_current_phase("no phase here") is None


# ══════════════════════════════════════════════════════
# _update_context_advisory
# ══════════════════════════════════════════════════════

class TestUpdateContextAdvisory:
    """Tests for phase transition detection and context health advisory."""

    def test_no_phase_in_content_does_nothing(self, stop_persist, tmp_path):
        """No phase field → no advisory written."""
        advisory_path = tmp_path / ".claude" / "ecw" / "state" / "context-health.txt"
        stop_persist._update_context_advisory(str(tmp_path), "no phase here")
        assert not advisory_path.exists()


class TestStopPersistScriptExists:
    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "stop-persist.py").exists()
