"""Unit tests for hooks/marker_utils.py

Tests the session state utilities:
- find_session_state: path resolution (JSON only)
- parse_status: JSON parsing
- update_status_fields: JSON updates
- validate_status: field validation
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


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
# find_session_state
# ══════════════════════════════════════════════════════

class TestFindSessionState:
    def test_finds_json_file(self, marker_utils, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260417-1606"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.json").write_text('{"risk_level": "P2"}')

        result = marker_utils.find_session_state(str(tmp_path))
        assert result is not None
        assert result.endswith("session-state.json")

    def test_returns_none_when_missing(self, marker_utils, tmp_path):
        assert marker_utils.find_session_state(str(tmp_path)) is None


# ══════════════════════════════════════════════════════
# parse_status
# ══════════════════════════════════════════════════════

class TestParseStatus:
    def test_reads_json_file(self, marker_utils, tmp_path):
        state_file = tmp_path / "session-state.json"
        state_file.write_text(json.dumps({
            "risk_level": "P1",
            "routing": ["writing-plans", "impl-verify"],
            "current_phase": "plan-complete",
            "auto_continue": True,
        }))
        result = marker_utils.parse_status(str(state_file))
        assert result["risk_level"] == "P1"
        assert result["routing"] == ["writing-plans", "impl-verify"]

    def test_returns_none_for_missing_file(self, marker_utils, tmp_path):
        result = marker_utils.parse_status(str(tmp_path / "nonexistent.json"))
        assert result is None

    def test_returns_none_for_invalid_json(self, marker_utils, tmp_path):
        state_file = tmp_path / "session-state.json"
        state_file.write_text("not json {{{")
        result = marker_utils.parse_status(str(state_file))
        assert result is None


# ══════════════════════════════════════════════════════
# update_status_fields (JSON mode)
# ══════════════════════════════════════════════════════

class TestUpdateStatusFieldsJson:
    def test_updates_existing_json(self, marker_utils, tmp_path):
        state_file = tmp_path / "session-state.json"
        state_file.write_text(json.dumps({
            "risk_level": "P2",
            "current_phase": "plan-complete",
            "auto_continue": True,
        }))
        marker_utils.update_status_fields(str(state_file), {"current_phase": "tdd-loaded"})
        data = json.loads(state_file.read_text())
        assert data["current_phase"] == "tdd-loaded"
        assert data["risk_level"] == "P2"  # preserved


# ══════════════════════════════════════════════════════
# validate_status
# ══════════════════════════════════════════════════════

class TestValidateStatus:
    def test_valid_fields(self, marker_utils):
        fields = {
            "risk_level": "P1",
            "routing": ["a", "b"],
            "current_phase": "test",
            "auto_continue": True,
        }
        assert marker_utils.validate_status(fields) == []

    def test_missing_required(self, marker_utils):
        errors = marker_utils.validate_status({})
        assert len(errors) == 4

    def test_invalid_risk_level(self, marker_utils):
        fields = {
            "risk_level": "P5",
            "routing": [],
            "current_phase": "x",
            "auto_continue": True,
        }
        errors = marker_utils.validate_status(fields)
        assert any("P5" in e for e in errors)


class TestMarkerUtilsModuleExists:
    def test_module_exists(self):
        assert (HOOKS_DIR / "marker_utils.py").exists()
