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

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


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
        """Detects session-state.md in .claude/ecw/session-data/{workflow-id}/ directory."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
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
        content = (
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P0\n"
            "domains: [order, inventory]\n"
            "<!-- ECW:STATUS:END -->"
        )
        fields = session_start._extract_state_fields(content)
        assert fields["risk_level"] == "P0"
        assert "order" in fields["domains"]
        assert "inventory" in fields["domains"]

    def test_extracts_mode_and_routing(self, session_start):
        content = (
            "<!-- ECW:STATUS:START -->\n"
            "mode: cross-domain\n"
            "routing: [domain-collab, writing-plans]\n"
            "<!-- ECW:STATUS:END -->"
        )
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
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n"
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "current_phase: phase1-complete\n"
            "auto_continue: true\n"
            "routing: [ecw:writing-plans]\n"
            "<!-- ECW:STATUS:END -->\n"
        )

        input_data = {"cwd": str(tmp_path)}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                assert "additionalContext" in output
                assert "risk_level" in output["additionalContext"]
                assert "P1" in output["additionalContext"]

    def test_ended_session_no_recovery(self, session_start, tmp_path):
        """Session with auto_continue: false → no recovery hint."""
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n"
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "auto_continue: false\n"
            "current_phase: biz-impact-complete\n"
            "routing: []\n"
            "<!-- ECW:STATUS:END -->\n"
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




# ══════════════════════════════════════════════════════
# _read_instincts (v0.7+)
# ══════════════════════════════════════════════════════

class TestReadInstincts:
    """Tests for _read_instincts parsing instincts.md with INSTINCT markers."""

    def test_parses_valid_instinct(self, session_start, tmp_path):
        """Parses well-formed instinct entry above confidence threshold."""
        instincts_dir = tmp_path / ".claude" / "ecw" / "state"
        instincts_dir.mkdir(parents=True)
        (instincts_dir / "instincts.md").write_text(
            "# Instincts\n"
            "<!-- INSTINCT -->\n"
            "- **Pattern**: order cancel after payment\n"
            "- **Action**: classify as P0\n"
            "- **Confidence**: 0.85\n"
            "- **Source**: calibration-2026-04\n"
        )
        result = session_start._read_instincts(str(tmp_path))
        assert len(result) == 1
        assert result[0]["pattern"] == "order cancel after payment"
        assert result[0]["confidence"] == 0.85

    def test_filters_below_threshold(self, session_start, tmp_path):
        """Entries with confidence < 0.7 are excluded."""
        instincts_dir = tmp_path / ".claude" / "ecw" / "state"
        instincts_dir.mkdir(parents=True)
        (instincts_dir / "instincts.md").write_text(
            "# Instincts\n"
            "<!-- INSTINCT -->\n"
            "- **Pattern**: minor fix\n"
            "- **Action**: classify as P3\n"
            "- **Confidence**: 0.5\n"
            "- **Source**: test\n"
        )
        result = session_start._read_instincts(str(tmp_path))
        assert len(result) == 0

    def test_returns_empty_when_no_file(self, session_start, tmp_path):
        """No instincts.md → empty list."""
        result = session_start._read_instincts(str(tmp_path))
        assert result == []


# ══════════════════════════════════════════════════════
# _read_ecw_config (v0.7+)
# ══════════════════════════════════════════════════════

class TestReadEcwConfig:
    """Tests for _get_project_info reading ecw.yml."""

    def test_reads_project_name_and_language(self, session_start, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        (ecw_dir / "ecw.yml").write_text(
            "project:\n  name: test-wms\n  language: java\n"
        )
        cfg = session_start._get_project_info(str(tmp_path))
        assert cfg["project_name"] == "test-wms"
        assert cfg["language"] == "java"

    def test_returns_empty_when_no_file(self, session_start, tmp_path):
        cfg = session_start._get_project_info(str(tmp_path))
        assert cfg == {} or (not cfg.get("project_name") and not cfg.get("language"))


# ══════════════════════════════════════════════════════
# _check_modified_files (v0.7+)
# ══════════════════════════════════════════════════════

class TestCheckModifiedFiles:
    """Tests for _check_modified_files reading modified-files.txt."""

    def test_reads_file_list(self, session_start, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "modified-files.txt").write_text(
            "src/OrderService.java\nsrc/PaymentService.java\n"
        )
        result = session_start._check_modified_files(str(tmp_path))
        assert len(result) == 2
        assert "src/OrderService.java" in result

    def test_returns_empty_when_no_file(self, session_start, tmp_path):
        result = session_start._check_modified_files(str(tmp_path))
        assert result == []


# ══════════════════════════════════════════════════════
# _summarize_checkpoint (v0.7+)
# ══════════════════════════════════════════════════════

class TestSummarizeCheckpoint:
    """Tests for _summarize_checkpoint heading extraction."""

    def test_extracts_first_heading(self, session_start, tmp_path):
        f = tmp_path / "requirements-summary.md"
        f.write_text("# Requirements Summary\nDetail content here.\n")
        result = session_start._summarize_checkpoint(str(f), "requirements-summary.md")
        assert "requirements-summary.md" in result
        assert "Requirements Summary" in result

    def test_handles_empty_file(self, session_start, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        result = session_start._summarize_checkpoint(str(f), "empty.md")
        assert "empty.md" in result


class TestSessionStartScriptExists:
    """Guard test: the hook script file must exist."""

    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "session-start.py").exists()


# ══════════════════════════════════════════════════════
# Version Check (v0.9+)
# ══════════════════════════════════════════════════════


class TestVersionCheck:
    """Tests for _check_version_mismatch detecting plugin/config version drift."""

    def _write_ecw_yml(self, tmp_path, content):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True, exist_ok=True)
        (ecw_dir / "ecw.yml").write_text(content)

    def test_version_mismatch_detected(self, session_start, tmp_path):
        """ecw_version differs from plugin version → mismatch=True."""
        self._write_ecw_yml(tmp_path, 'ecw_version: "0.1.0"\nproject:\n  name: test\n')
        mismatch, p_ver, c_ver = session_start._check_version_mismatch(str(tmp_path))
        assert mismatch is True
        assert c_ver == "0.1.0"
        assert p_ver  # non-empty

    def test_version_match_no_warning(self, session_start, tmp_path):
        """ecw_version matches plugin version → mismatch=False."""
        from ecw_config import read_plugin_version
        plugin_ver = read_plugin_version()
        self._write_ecw_yml(tmp_path, f'ecw_version: "{plugin_ver}"\nproject:\n  name: test\n')
        mismatch, p_ver, c_ver = session_start._check_version_mismatch(str(tmp_path))
        assert mismatch is False
        assert p_ver == plugin_ver

    def test_missing_ecw_version_treated_as_mismatch(self, session_start, tmp_path):
        """ecw.yml without ecw_version field → mismatch=True."""
        self._write_ecw_yml(tmp_path, "project:\n  name: test\n")
        mismatch, p_ver, c_ver = session_start._check_version_mismatch(str(tmp_path))
        assert mismatch is True
        assert c_ver == "(missing)"

    def test_no_ecw_yml_no_mismatch(self, session_start, tmp_path):
        """No ecw.yml at all → mismatch=False (not an ECW project)."""
        mismatch, p_ver, c_ver = session_start._check_version_mismatch(str(tmp_path))
        assert mismatch is False

    def test_mismatch_output_contains_upgrade_instruction(self, session_start, tmp_path):
        """Version mismatch → main() output contains /ecw-upgrade instruction."""
        self._write_ecw_yml(tmp_path, 'ecw_version: "0.0.1"\nproject:\n  name: test\n')
        input_data = {"cwd": str(tmp_path)}
        input_json = json.dumps(input_data)
        import io
        with patch("sys.stdin", io.StringIO(input_json)):
            with patch("builtins.print") as mock_print:
                session_start.main()
                output = json.loads(mock_print.call_args[0][0])
                assert "additionalContext" in output
                ctx = output["additionalContext"]
                assert "/ecw-upgrade" in ctx
                assert "0.0.1" in ctx
