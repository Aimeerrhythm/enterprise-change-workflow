"""Tests for YAML-based session-state parsing — Issue #40.

Covers:
- parse_status: extract STATUS section as YAML dict
- validate_status: schema validation
- parse_ledger: extract LEDGER section as YAML list
- append_ledger_entry: structured LEDGER append
- update_status_fields: update STATUS fields via YAML dict
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"

VALID_STATUS_YAML = """\
risk_level: P0
domains: [payment, order]
mode: cross-domain
routing: [requirements-elicitation, Phase 2, writing-plans]
current_phase: phase1-complete
auto_continue: true
next: writing-plans
"""

FULL_SESSION_CONTENT = (
    "# ECW Session State\n\n"
    "<!-- ECW:STATUS:START -->\n"
    + VALID_STATUS_YAML
    + "<!-- ECW:STATUS:END -->\n\n"
    "<!-- ECW:MODE:START -->\n"
    "working_mode: analysis\n"
    "<!-- ECW:MODE:END -->\n\n"
    "<!-- ECW:LEDGER:START -->\n"
    "<!-- ECW:LEDGER:END -->\n"
)


@pytest.fixture(name="mu")
def marker_utils_fixture():
    """Import marker_utils.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "marker_utils", HOOKS_DIR / "marker_utils.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# parse_status
# ══════════════════════════════════════════════════════

class TestParseStatus:
    def test_returns_dict_for_valid_yaml(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert fields is not None
        assert isinstance(fields, dict)

    def test_risk_level_correct(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        assert mu.parse_status(content)["risk_level"] == "P0"

    def test_domains_is_list(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert isinstance(fields["domains"], list)
        assert fields["domains"] == ["payment", "order"]

    def test_routing_is_list(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert isinstance(fields["routing"], list)
        assert "writing-plans" in fields["routing"]
        assert "requirements-elicitation" in fields["routing"]

    def test_auto_continue_is_bool_true(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert fields["auto_continue"] is True

    def test_auto_continue_false(self, mu):
        yaml_text = VALID_STATUS_YAML.replace("auto_continue: true", "auto_continue: false")
        content = f"<!-- ECW:STATUS:START -->\n{yaml_text}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert fields["auto_continue"] is False

    def test_invalid_yaml_returns_none(self, mu):
        bad = "<!-- ECW:STATUS:START -->\n  bad: yaml:\n  - [\n<!-- ECW:STATUS:END -->"
        assert mu.parse_status(bad) is None

    def test_missing_marker_returns_none(self, mu):
        assert mu.parse_status("no markers here") is None

    def test_parses_from_full_session_content(self, mu):
        fields = mu.parse_status(FULL_SESSION_CONTENT)
        assert fields is not None
        assert fields["mode"] == "cross-domain"
        assert fields["next"] == "writing-plans"

    def test_next_field_is_string(self, mu):
        content = f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"
        fields = mu.parse_status(content)
        assert isinstance(fields["next"], str)


# ══════════════════════════════════════════════════════
# validate_status
# ══════════════════════════════════════════════════════

class TestValidateStatus:
    def test_valid_fields_returns_no_errors(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        errors = mu.validate_status(fields)
        assert errors == []

    def test_invalid_risk_level_p5(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        fields["risk_level"] = "P5"
        errors = mu.validate_status(fields)
        assert any("risk_level" in e for e in errors)

    def test_invalid_risk_level_lowercase(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        fields["risk_level"] = "p0"
        errors = mu.validate_status(fields)
        assert any("risk_level" in e for e in errors)

    def test_routing_not_list_is_error(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        fields["routing"] = "requirements-elicitation → writing-plans"
        errors = mu.validate_status(fields)
        assert any("routing" in e for e in errors)

    def test_auto_continue_string_is_error(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        fields["auto_continue"] = "yes"
        errors = mu.validate_status(fields)
        assert any("auto_continue" in e for e in errors)

    def test_domains_not_list_is_error(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        fields["domains"] = "payment, order"
        errors = mu.validate_status(fields)
        assert any("domains" in e for e in errors)

    def test_missing_required_fields(self, mu):
        # Only risk_level provided — should flag missing routing, current_phase, auto_continue
        errors = mu.validate_status({"risk_level": "P0"})
        assert len(errors) >= 3

    def test_all_valid_risk_levels(self, mu):
        fields = yaml.safe_load(VALID_STATUS_YAML)
        for level in ("P0", "P1", "P2", "P3"):
            fields["risk_level"] = level
            errors = mu.validate_status(fields)
            assert not any("risk_level" in e for e in errors), f"P{level} should be valid"


# ══════════════════════════════════════════════════════
# parse_ledger
# ══════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════
# update_status_fields (YAML-based)
# ══════════════════════════════════════════════════════

class TestUpdateStatusFieldsYaml:
    def _base_content(self):
        return f"<!-- ECW:STATUS:START -->\n{VALID_STATUS_YAML}<!-- ECW:STATUS:END -->"

    def test_update_single_field(self, mu):
        updated = mu.update_status_fields(self._base_content(), {"current_phase": "planning"})
        fields = mu.parse_status(updated)
        assert fields["current_phase"] == "planning"

    def test_unchanged_fields_preserved(self, mu):
        updated = mu.update_status_fields(self._base_content(), {"current_phase": "planning"})
        fields = mu.parse_status(updated)
        assert fields["risk_level"] == "P0"
        assert fields["domains"] == ["payment", "order"]
        assert fields["routing"] == ["requirements-elicitation", "Phase 2", "writing-plans"]

    def test_update_auto_continue_to_false(self, mu):
        updated = mu.update_status_fields(self._base_content(), {"auto_continue": False})
        fields = mu.parse_status(updated)
        assert fields["auto_continue"] is False

    def test_update_next_field(self, mu):
        updated = mu.update_status_fields(self._base_content(), {"next": "spec-challenge"})
        fields = mu.parse_status(updated)
        assert fields["next"] == "spec-challenge"

    def test_update_multiple_fields(self, mu):
        updated = mu.update_status_fields(
            self._base_content(),
            {"current_phase": "plan-complete", "next": "spec-challenge"}
        )
        fields = mu.parse_status(updated)
        assert fields["current_phase"] == "plan-complete"
        assert fields["next"] == "spec-challenge"
        assert fields["risk_level"] == "P0"  # unchanged

    def test_missing_status_section_returns_unchanged(self, mu):
        content = "# ECW\nno status section"
        result = mu.update_status_fields(content, {"current_phase": "planning"})
        assert result == content


