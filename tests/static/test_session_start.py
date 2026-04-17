"""Unit tests for hooks/session-start.py

Tests the SessionStart hook's context injection behavior:
- Valid JSON output with additionalContext
- Session-state.md detection and injection
- Checkpoint file summarization
- Graceful handling when no state exists
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def session_start():
    """Import session-start.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "session_start",
        HOOKS_DIR / "session-start.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# State Detection
# ══════════════════════════════════════════════════════

class TestReadSessionState:
    """Tests for _read_session_state function."""

    def test_reads_state_dir_path(self, session_start, tmp_path):
        """Detects session-state.md in .claude/ecw/state/ directory."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text("# ECW Session State\n- **Risk Level**: P1\n")

        content, path = session_start._read_session_state(str(tmp_path))
        assert content is not None
        assert "Risk Level" in content
        assert "session-state.md" in path

    def test_reads_legacy_path(self, session_start, tmp_path):
        """Falls back to .claude/ecw/session-state.md (legacy path)."""
        state_dir = tmp_path / ".claude" / "ecw"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text("# ECW Session State\n- **Risk Level**: P0\n")

        content, path = session_start._read_session_state(str(tmp_path))
        assert content is not None
        assert "P0" in content

    def test_returns_none_when_no_state(self, session_start, tmp_path):
        """Returns (None, None) when no session-state.md exists."""
        content, path = session_start._read_session_state(str(tmp_path))
        assert content is None
        assert path is None

    def test_skips_empty_file(self, session_start, tmp_path):
        """Skips session-state.md if it's empty."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text("")

        content, path = session_start._read_session_state(str(tmp_path))
        assert content is None


class TestExtractStateFields:
    """Tests for _extract_state_fields function."""

    def test_extracts_risk_level(self, session_start):
        content = "- **Risk Level**: P0\n- **Domains**: order, inventory\n"
        fields = session_start._extract_state_fields(content)
        assert fields["risk_level"] == "P0"
        assert fields["domains"] == "order, inventory"

    def test_extracts_mode_and_routing(self, session_start):
        content = "- **Mode**: cross-domain\n- **Routing**: domain-collab → writing-plans\n"
        fields = session_start._extract_state_fields(content)
        assert fields["mode"] == "cross-domain"
        assert "writing-plans" in fields["routing"]

    def test_handles_missing_fields(self, session_start):
        fields = session_start._extract_state_fields("no fields here")
        assert len(fields) == 0


# ══════════════════════════════════════════════════════
# Checkpoint Detection
# ══════════════════════════════════════════════════════

class TestGetCheckpointFiles:
    """Tests for _get_checkpoint_files function."""

    def test_lists_md_files_sorted_by_mtime(self, session_start, tmp_path):
        """Returns .md files in session-data/ sorted newest first."""
        sd_dir = tmp_path / ".claude" / "ecw" / "session-data"
        sd_dir.mkdir(parents=True)
        (sd_dir / "requirements-summary.md").write_text("# Requirements")
        (sd_dir / "phase2-assessment.md").write_text("# Phase 2")
        # Touch second file to make it newer
        os.utime(sd_dir / "phase2-assessment.md", None)

        files = session_start._get_checkpoint_files(str(tmp_path))
        assert len(files) == 2
        # Newest first
        assert files[0][2] == "phase2-assessment.md"

    def test_returns_empty_when_no_dir(self, session_start, tmp_path):
        files = session_start._get_checkpoint_files(str(tmp_path))
        assert files == []

    def test_ignores_non_md_files(self, session_start, tmp_path):
        sd_dir = tmp_path / ".claude" / "ecw" / "session-data"
        sd_dir.mkdir(parents=True)
        (sd_dir / "notes.txt").write_text("not markdown")
        (sd_dir / "data.json").write_text("{}")

        files = session_start._get_checkpoint_files(str(tmp_path))
        assert files == []


# ══════════════════════════════════════════════════════
# Main Output
# ══════════════════════════════════════════════════════

class TestSessionStartMain:
    """Tests for the main() function output."""

    def test_no_state_returns_continue(self, session_start, tmp_path):
        """No session state → result: continue, no additionalContext."""
        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"
                assert "additionalContext" not in output

    def test_active_state_injects_context(self, session_start, tmp_path):
        """Active session-state → additionalContext includes state content."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n- **Risk Level**: P1\n- **Current Phase**: phase1-complete\n"
        )

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                assert "additionalContext" in output
                assert "Risk Level" in output["additionalContext"]
                assert "P1" in output["additionalContext"]

    def test_ended_session_no_recovery(self, session_start, tmp_path):
        """Session with Status: ended → no recovery hint."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n- **Risk Level**: P1\n- **Status**: ended\n"
        )

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                ctx = output.get("additionalContext", "")
                assert "Recovery hint" not in ctx

    def test_checkpoint_files_included(self, session_start, tmp_path):
        """Checkpoint files listed in additionalContext."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n- **Risk Level**: P0\n"
        )
        sd_dir = tmp_path / ".claude" / "ecw" / "session-data"
        sd_dir.mkdir(parents=True)
        (sd_dir / "requirements-summary.md").write_text("# Requirements Summary")

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                ctx = output["additionalContext"]
                assert "requirements-summary.md" in ctx

    def test_empty_cwd_returns_continue(self, session_start):
        """Empty cwd → result: continue."""
        input_data = {"cwd": ""}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                assert output["result"] == "continue"


class TestSessionStartScriptExists:
    """Guard test: the hook script file must exist."""

    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "session-start.py").exists()
