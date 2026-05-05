"""Unit tests for context_builder.py.

Verifies fixture loading, from_step resolution (dict syntax),
and session-state reconstruction from risk-classifier output.
"""
from __future__ import annotations

import json
import pytest
from pathlib import Path

CHAIN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "eval" / "chain"


class TestBuildContext:
    """Tests for build_context()."""

    def test_plain_string_value(self):
        from tests.eval.chain.context_builder import build_context
        result = build_context({"ecw_yml": "name: test"}, {})
        assert "### ecw_yml" in result
        assert "name: test" in result

    def test_fixture_yaml_loaded_as_raw_text(self):
        """fixtures/*.yaml are read as raw text, not parse-and-re-dumped."""
        from tests.eval.chain.context_builder import build_context
        # Write a temp fixture with a comment to verify raw-text preservation
        import tempfile, os
        fixtures_dir = CHAIN_DIR / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        tmp = fixtures_dir / "_test_fixture.yaml"
        tmp.write_text("# This is a comment\nkey: value\n", encoding="utf-8")
        try:
            result = build_context({"cfg": "fixtures/_test_fixture.yaml"}, {})
            assert "# This is a comment" in result
        finally:
            tmp.unlink(missing_ok=True)

    def test_fixture_md_loaded(self):
        """fixtures/*.md are read as raw text."""
        from tests.eval.chain.context_builder import build_context
        fixtures_dir = CHAIN_DIR / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        tmp = fixtures_dir / "_test_fixture.md"
        tmp.write_text("## Domain Registry\n- domain: payment\n", encoding="utf-8")
        try:
            result = build_context({"domains": "fixtures/_test_fixture.md"}, {})
            assert "## Domain Registry" in result
        finally:
            tmp.unlink(missing_ok=True)

    def test_from_step_dict_whole_tool_result(self):
        """from_step dict without field returns full tool_result."""
        from tests.eval.chain.context_builder import build_context
        prior = {
            "risk-classifier": {
                "tool_result": '{"risk_level": "P0"}',
                "text_output": "analysis",
            }
        }
        spec = {"rc_output": {"from_step": "risk-classifier"}}
        result = build_context(spec, prior)
        assert '{"risk_level": "P0"}' in result

    def test_from_step_dict_specific_field(self):
        """from_step dict with field returns that field value."""
        from tests.eval.chain.context_builder import build_context
        prior = {
            "writing-plans": {
                "field:plan_content": "# My Plan\n...",
            }
        }
        spec = {"plan": {"from_step": "writing-plans", "field": "plan_content"}}
        result = build_context(spec, prior)
        assert "# My Plan" in result

    def test_from_step_missing_step_returns_empty(self):
        """from_step referencing a step that hasn't run returns empty."""
        from tests.eval.chain.context_builder import build_context
        spec = {"x": {"from_step": "nonexistent"}}
        result = build_context(spec, {})
        assert "### x" in result
        # Value is empty — section header present but no content
        assert "### x\n\n" in result or result.strip().endswith("### x")

    def test_from_step_session_state_builds_from_rc(self):
        """When key is 'session_state' and from_step with no field, builds session-state format."""
        from tests.eval.chain.context_builder import build_context
        prior = {
            "risk-classifier": {
                "tool_result": json.dumps({
                    "risk_level": "P0",
                    "mode": "single-domain",
                    "routing": ["requirements-elicitation", "writing-plans", "spec-challenge"],
                    "domains": ["payment"],
                })
            }
        }
        spec = {"session_state": {"from_step": "risk-classifier"}}
        result = build_context(spec, prior)
        assert "ECW:STATUS:START" in result
        assert "P0" in result
        assert "payment" in result
        assert "writing-plans" in result

    def test_from_step_session_state_missing_domains(self):
        """Handles risk-classifier output missing domains field gracefully."""
        from tests.eval.chain.context_builder import build_context
        prior = {
            "risk-classifier": {
                "tool_result": json.dumps({
                    "risk_level": "P1",
                    "mode": "cross-domain",
                    "routing": ["domain-collab", "writing-plans"],
                    # domains absent
                })
            }
        }
        spec = {"session_state": {"from_step": "risk-classifier"}}
        result = build_context(spec, prior)
        assert "ECW:STATUS:START" in result
        assert "P1" in result
        # Should not crash; domains line present even if empty

    def test_from_step_parse_error_handled(self):
        """Malformed JSON in tool_result produces a parse-error placeholder."""
        from tests.eval.chain.context_builder import build_context
        prior = {"risk-classifier": {"tool_result": "NOT_JSON"}}
        spec = {"session_state": {"from_step": "risk-classifier"}}
        result = build_context(spec, prior)
        assert "parse error" in result.lower() or "ECW:STATUS:START" in result


class TestBuildSessionStateFromRc:
    """Direct tests for _build_session_state_from_rc helper."""

    def test_full_fields(self):
        from tests.eval.chain.context_builder import _build_session_state_from_rc
        payload = {
            "risk_level": "P0",
            "mode": "single-domain",
            "routing": ["requirements-elicitation", "writing-plans", "spec-challenge"],
            "domains": ["payment"],
        }
        result = _build_session_state_from_rc(json.dumps(payload))
        assert "Risk Level**: P0" in result
        assert "Domains**: payment" in result
        assert "requirements-elicitation → writing-plans → spec-challenge" in result
        assert "ECW:STATUS:END" in result

    def test_routing_arrow_separator(self):
        """Routing list is joined with ' → '."""
        from tests.eval.chain.context_builder import _build_session_state_from_rc
        payload = {"risk_level": "P1", "mode": "cross-domain", "routing": ["a", "b", "c"]}
        result = _build_session_state_from_rc(json.dumps(payload))
        assert "a → b → c" in result

    def test_bad_json_returns_placeholder(self):
        from tests.eval.chain.context_builder import _build_session_state_from_rc
        result = _build_session_state_from_rc("{{invalid")
        assert "ECW:STATUS:START" in result
        assert "parse error" in result.lower()
