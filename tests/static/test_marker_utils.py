"""Unit tests for hooks/marker_utils.py

Tests the shared marker-based idempotent update utilities:
- make_markers: correct marker format
- update_marker_section: replace existing / append new
- read_marker_section: extract inner content
- find_session_state: path resolution
- update_session_state_section: end-to-end file update
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def marker_utils():
    """Import marker_utils.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "marker_utils",
        HOOKS_DIR / "marker_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# make_markers
# ══════════════════════════════════════════════════════

class TestMakeMarkers:
    def test_standard_format(self, marker_utils):
        start, end = marker_utils.make_markers("LEDGER")
        assert start == "<!-- ECW:LEDGER:START -->"
        assert end == "<!-- ECW:LEDGER:END -->"

    def test_stop_marker(self, marker_utils):
        start, end = marker_utils.make_markers("STOP")
        assert start == "<!-- ECW:STOP:START -->"
        assert end == "<!-- ECW:STOP:END -->"


# ══════════════════════════════════════════════════════
# update_marker_section
# ══════════════════════════════════════════════════════

class TestUpdateMarkerSection:
    def test_append_when_no_markers(self, marker_utils):
        """Appends marker section when markers don't exist."""
        content = "# ECW Session State\n- **Risk Level**: P1\n"
        result = marker_utils.update_marker_section(content, "STOP", "- new data")
        assert "<!-- ECW:STOP:START -->" in result
        assert "<!-- ECW:STOP:END -->" in result
        assert "- new data" in result
        assert "Risk Level" in result  # original preserved

    def test_replace_existing_markers(self, marker_utils):
        """Replaces content between existing markers."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:STOP:START -->\n"
            "- old data\n"
            "<!-- ECW:STOP:END -->\n"
            "## Ledger\n"
        )
        result = marker_utils.update_marker_section(content, "STOP", "- new data")
        assert "old data" not in result
        assert "- new data" in result
        assert "## Ledger" in result  # content after marker preserved

    def test_multiple_markers_independent(self, marker_utils):
        """Updating one marker section doesn't affect others."""
        content = (
            "<!-- ECW:STATUS:START -->\n- status info\n<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:LEDGER:START -->\n| table |\n<!-- ECW:LEDGER:END -->\n"
        )
        result = marker_utils.update_marker_section(content, "STATUS", "- updated status")
        assert "- updated status" in result
        assert "| table |" in result  # LEDGER untouched

    def test_multiline_inner_content(self, marker_utils):
        """Handles multi-line content between markers."""
        content = "# Header\n"
        inner = "line1\nline2\nline3"
        result = marker_utils.update_marker_section(content, "TEST", inner)
        assert "line1\nline2\nline3" in result


# ══════════════════════════════════════════════════════
# read_marker_section
# ══════════════════════════════════════════════════════

class TestReadMarkerSection:
    def test_reads_existing_section(self, marker_utils):
        content = (
            "# ECW\n"
            "<!-- ECW:STATUS:START -->\n"
            "- **Risk Level**: P0\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        inner = marker_utils.read_marker_section(content, "STATUS")
        assert inner == "- **Risk Level**: P0"

    def test_returns_none_when_missing(self, marker_utils):
        content = "# ECW\nno markers here\n"
        assert marker_utils.read_marker_section(content, "STATUS") is None

    def test_reads_correct_section_among_multiple(self, marker_utils):
        content = (
            "<!-- ECW:STATUS:START -->\nstatus data\n<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:LEDGER:START -->\nledger data\n<!-- ECW:LEDGER:END -->\n"
        )
        assert marker_utils.read_marker_section(content, "STATUS") == "status data"
        assert marker_utils.read_marker_section(content, "LEDGER") == "ledger data"


# ══════════════════════════════════════════════════════
# find_session_state
# ══════════════════════════════════════════════════════

class TestFindSessionState:
    def test_finds_state_dir_path(self, marker_utils, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text("# ECW")

        result = marker_utils.find_session_state(str(tmp_path))
        assert result is not None
        assert "session-state.md" in result

    def test_finds_legacy_path(self, marker_utils, tmp_path):
        legacy_dir = tmp_path / ".claude" / "ecw"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / "session-state.md").write_text("# ECW")

        result = marker_utils.find_session_state(str(tmp_path))
        assert result is not None

    def test_returns_none_when_missing(self, marker_utils, tmp_path):
        assert marker_utils.find_session_state(str(tmp_path)) is None


# ══════════════════════════════════════════════════════
# update_session_state_section
# ══════════════════════════════════════════════════════

class TestUpdateSessionStateSection:
    def test_updates_existing_file(self, marker_utils, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "# ECW\n"
            "<!-- ECW:STATUS:START -->\n- old\n<!-- ECW:STATUS:END -->\n"
        )

        result = marker_utils.update_session_state_section(
            str(tmp_path), "STATUS", "- new"
        )
        assert result is True
        updated = state_file.read_text()
        assert "- new" in updated
        assert "old" not in updated

    def test_returns_false_when_no_file(self, marker_utils, tmp_path):
        result = marker_utils.update_session_state_section(
            str(tmp_path), "STATUS", "- data"
        )
        assert result is False


class TestMarkerUtilsModuleExists:
    def test_module_exists(self):
        assert (HOOKS_DIR / "marker_utils.py").exists()
