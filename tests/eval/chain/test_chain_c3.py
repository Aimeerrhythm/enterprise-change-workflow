"""Tests for c3_bug_debug chain YAML and debug_investigation_result tool schema.

Unit tests only — no real API calls.
c3 verifies Bug scenario RC→SD compatibility:
- RC correctly identifies change_type=bug and routes to systematic-debugging
- SD consumes session_state from RC and produces structured investigation result
Key difference from c1/c2: 2-step chain (no planning phase), uses chain-local tool schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

CHAIN_DIR = Path(__file__).parent / "chains"
CHAIN_TOOLS_DIR = Path(__file__).parent / "tools"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
EVAL_DIR = Path(__file__).parent.parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CHAIN_ID = "c3_bug_debug"
SD_TOOL_SCHEMA = "chain/tools/debug_investigation_result.json"


class TestDebugInvestigationToolSchema:
    """Validate the debug_investigation_result tool schema used by c3."""

    def test_tool_schema_file_exists(self):
        assert (CHAIN_TOOLS_DIR / "debug_investigation_result.json").exists()

    def test_tool_schema_is_valid_json(self):
        content = (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_tool_schema_has_required_top_level_fields(self):
        data = json.loads(
            (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        )
        assert "name" in data
        assert "input_schema" in data
        assert data["name"] == "debug_investigation_result"

    def test_tool_schema_has_bug_classification_enum(self):
        data = json.loads(
            (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        )
        props = data["input_schema"]["properties"]
        assert "bug_classification" in props
        assert "enum" in props["bug_classification"]
        assert "unknown" in props["bug_classification"]["enum"]

    def test_tool_schema_has_root_cause_hypothesis(self):
        data = json.loads(
            (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        )
        props = data["input_schema"]["properties"]
        assert "root_cause_hypothesis" in props
        assert props["root_cause_hypothesis"]["type"] == "string"

    def test_tool_schema_has_affected_components_array(self):
        data = json.loads(
            (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        )
        props = data["input_schema"]["properties"]
        assert "affected_components" in props
        assert props["affected_components"]["type"] == "array"

    def test_tool_schema_has_required_fields(self):
        data = json.loads(
            (CHAIN_TOOLS_DIR / "debug_investigation_result.json").read_text(encoding="utf-8")
        )
        required = data["input_schema"].get("required", [])
        assert "bug_classification" in required
        assert "root_cause_hypothesis" in required

    def test_tool_schema_resolves_from_eval_dir(self):
        """Harness resolves tool_schema relative to tests/eval/."""
        schema_path = EVAL_DIR / SD_TOOL_SCHEMA
        assert schema_path.exists(), f"Tool schema not found at {schema_path}"


class TestChainC3YAMLStructure:
    """Validate the c3 chain YAML is well-formed and compatible with harness.py."""

    def test_chain_yaml_loads(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert isinstance(chain, dict)

    def test_chain_has_name(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert chain.get("name")

    def test_chain_has_two_steps(self):
        """c3 is a 2-step chain (RC→SD), no planning phase."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert len(chain["steps"]) == 2

    def test_step_skills_are_correct_order(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        skills = [s["skill"] for s in chain["steps"]]
        assert skills == ["risk-classifier", "systematic-debugging"]

    def test_all_steps_have_input(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        for step in chain["steps"]:
            assert step.get("input"), f"Step {step['skill']} missing input"

    def test_tool_schemas_resolve_to_existing_files(self):
        from tests.eval.chain.harness import load_chain, EVAL_DIR as H_EVAL_DIR
        chain = load_chain(CHAIN_ID)
        for step in chain["steps"]:
            ref = step.get("tool_schema")
            if ref:
                p = H_EVAL_DIR / ref
                assert p.exists(), f"tool_schema '{ref}' not found at {p}"

    def test_sd_step_uses_chain_local_tool_schema(self):
        """systematic-debugging uses chain/tools/debug_investigation_result.json."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sd_step = chain["steps"][1]
        assert sd_step.get("tool_schema") == SD_TOOL_SCHEMA

    def test_sd_step_has_no_prompt_file(self):
        """systematic-debugging uses its standard SKILL.md (not agents/)."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sd_step = chain["steps"][1]
        assert "prompt_file" not in sd_step

    def test_chain_has_at_least_ten_assertions(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert len(chain.get("assertions") or []) >= 10

    def test_assertion_names_unique(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        names = [a["name"] for a in chain.get("assertions") or []]
        assert len(names) == len(set(names)), "Duplicate assertion names found"

    def test_sd_step_session_state_from_rc(self):
        """systematic-debugging must receive session_state from risk-classifier."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sd_context = chain["steps"][1].get("context") or {}
        ss = sd_context.get("session_state")
        assert isinstance(ss, dict) and ss.get("from_step") == "risk-classifier"

    def test_context_refs_use_correct_step_names(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        prior_skills: set[str] = set()
        for step in chain["steps"]:
            for _key, val in (step.get("context") or {}).items():
                if isinstance(val, dict) and "from_step" in val:
                    ref = val["from_step"]
                    assert ref in prior_skills, (
                        f"Step '{step['skill']}' references '{ref}' before it runs"
                    )
            prior_skills.add(step["skill"])

    def test_rc_input_describes_bug(self):
        """RC input must describe a bug symptom so RC classifies change_type=bug."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        rc_input = chain["steps"][0].get("input", "")
        assert any(kw in rc_input for kw in ["库存", "inventory", "超卖", "扣减"])


class TestChainC3Assertions:
    """Validate assertion definitions cover critical Bug scenario compatibility checks."""

    def _get_assertions(self):
        from tests.eval.chain.harness import load_chain
        return {a["name"]: a for a in load_chain(CHAIN_ID).get("assertions") or []}

    def test_has_rc_bug_classification_assertion(self):
        assertions = self._get_assertions()
        assert "rc_classifies_as_bug" in assertions

    def test_has_rc_routes_to_sd_assertion(self):
        assertions = self._get_assertions()
        assert "rc_routes_to_systematic_debugging" in assertions

    def test_has_sd_hypothesis_assertion(self):
        assertions = self._get_assertions()
        assert "sd_hypothesis_not_empty" in assertions

    def test_has_sd_affected_component_assertion(self):
        assertions = self._get_assertions()
        assert "sd_identifies_affected_component" in assertions

    def test_has_sd_bug_classification_assertion(self):
        assertions = self._get_assertions()
        assert "sd_bug_classification_recognized" in assertions


class TestChainC3EndToEnd:
    """End-to-end run with mocked API — verifies Bug scenario artifact flow."""

    @staticmethod
    def _make_tool_response(tool_name: str, input_dict: dict):
        block = MagicMock()
        block.type = "tool_use"
        block.input = input_dict
        block.name = tool_name
        resp = MagicMock()
        resp.content = [block]
        return resp

    def test_chain_runs_end_to_end(self):
        rc_resp = self._make_tool_response("classify_result", {
            "risk_level": "P1",
            "mode": "cross-domain",
            "change_type": "bug",
            "domains": ["order", "inventory"],
            "routing": ["systematic-debugging", "impl-verify", "biz-impact-analysis"],
        })
        sd_resp = self._make_tool_response("debug_investigation_result", {
            "bug_classification": "integration-failure",
            "root_cause_hypothesis": "order 域下单后未发送 MQ 消息触发 inventory 扣减",
            "evidence_sources": ["order-service logs", "inventory-service logs"],
            "affected_components": ["order", "inventory"],
            "investigation_complete": True,
            "next_phase": "hypothesis-test",
        })

        from tests.eval.chain.harness import load_chain, run_chain
        chain_def = load_chain(CHAIN_ID)

        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.side_effect = [rc_resp, sd_resp]
            result = run_chain(chain_def)

        assert result["chain"]
        assert len(result["steps"]) == 2
        passed = {a["name"]: a["passed"] for a in result["assertions"]}
        assert passed.get("rc_classifies_as_bug") is True
        assert passed.get("rc_routes_to_systematic_debugging") is True
        assert passed.get("sd_hypothesis_not_empty") is True
        assert passed.get("sd_identifies_affected_component") is True

    def test_all_assertions_pass_with_ideal_responses(self):
        """All chain assertions pass given ideal mock artifact values."""
        from tests.eval.chain.harness import load_chain
        from tests.eval.chain.assertions import run_assertions

        chain_def = load_chain(CHAIN_ID)
        mock_artifacts = {
            "risk-classifier": {
                "field:risk_level": "P1",
                "field:mode": "cross-domain",
                "field:change_type": "bug",
                "field:domains": "['order', 'inventory']",
                "field:routing": "['systematic-debugging', 'impl-verify', 'biz-impact-analysis']",
            },
            "systematic-debugging": {
                "field:bug_classification": "integration-failure",
                "field:root_cause_hypothesis": "order 域下单后未发 MQ 触发 inventory 扣减",
                "field:evidence_sources": "['order logs', 'inventory logs']",
                "field:affected_components": "['order', 'inventory']",
                "field:investigation_complete": "True",
                "field:next_phase": "hypothesis-test",
            },
        }
        results = run_assertions(chain_def["assertions"], mock_artifacts)
        failed = [r for r in results if not r["passed"]]
        assert not failed, f"Assertions failed: {[r['name'] for r in failed]}"
