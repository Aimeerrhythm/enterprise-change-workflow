"""Tests for c2_p1_cross_domain_plan chain YAML.

Unit tests only — no real API calls.
c2 verifies P1 cross-domain RC→WP→SC compatibility:
- RC correctly identifies cross-domain mode and P1 risk
- WP correctly adapts (lower task_count threshold, may have rollback)
- SC reads WP plan content and produces structured review
Key difference from c1: P1 cross-domain routes to spec-challenge (not P1 single-domain).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

CHAIN_DIR = Path(__file__).parent / "chains"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
EVAL_DIR = Path(__file__).parent.parent
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CHAIN_ID = "c2_p1_cross_domain_plan"


class TestChainC2YAMLStructure:
    """Validate the c2 chain YAML is well-formed and compatible with harness.py."""

    def test_chain_yaml_loads(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert isinstance(chain, dict)

    def test_chain_has_name(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert chain.get("name")

    def test_chain_has_three_steps(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert len(chain["steps"]) == 3

    def test_step_skills_are_correct_order(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        skills = [s["skill"] for s in chain["steps"]]
        assert skills == ["risk-classifier", "writing-plans", "spec-challenge"]

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

    def test_spec_challenge_step_uses_prompt_file(self):
        """spec-challenge must use agents/spec-challenge.md, not SKILL.md."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_step = chain["steps"][2]
        assert sc_step["skill"] == "spec-challenge"
        assert "prompt_file" in sc_step

    def test_spec_challenge_prompt_file_exists(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_step = chain["steps"][2]
        pf = sc_step.get("prompt_file")
        if pf:
            p = PROJECT_ROOT / pf
            assert p.exists(), f"prompt_file '{pf}' not found at {p}"

    def test_spec_challenge_prompt_file_points_to_agents(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_step = chain["steps"][2]
        pf = sc_step.get("prompt_file", "")
        assert pf.startswith("agents/")

    def test_chain_has_at_least_ten_assertions(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert len(chain.get("assertions") or []) >= 10

    def test_assertion_names_unique(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        names = [a["name"] for a in chain.get("assertions") or []]
        assert len(names) == len(set(names)), "Duplicate assertion names found"

    def test_rc_step_has_no_prompt_file(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert "prompt_file" not in chain["steps"][0]

    def test_wp_step_has_no_prompt_file(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert "prompt_file" not in chain["steps"][1]

    def test_wp_step_session_state_from_rc(self):
        """writing-plans must receive session_state from risk-classifier."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        wp_context = chain["steps"][1].get("context") or {}
        ss = wp_context.get("session_state")
        assert isinstance(ss, dict) and ss.get("from_step") == "risk-classifier"

    def test_sc_step_plan_document_from_wp(self):
        """spec-challenge must receive plan_content from writing-plans."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_context = chain["steps"][2].get("context") or {}
        pd = sc_context.get("plan_document")
        assert isinstance(pd, dict)
        assert pd.get("from_step") == "writing-plans"
        assert pd.get("field") == "plan_content"

    def test_context_refs_use_correct_step_names(self):
        """from_step values must match the skill field of a prior step."""
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

    def test_rc_input_contains_cross_domain_scenario(self):
        """RC input must describe a cross-domain scenario so RC classifies cross-domain."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        rc_input = chain["steps"][0].get("input", "")
        # Must mention two domains (order + inventory or similar)
        assert any(kw in rc_input for kw in ["订单", "order"]), "RC input should mention order domain"
        assert any(kw in rc_input for kw in ["库存", "inventory"]), "RC input should mention inventory domain"


class TestChainC2Assertions:
    """Validate that assertion definitions cover critical P1 cross-domain compatibility checks."""

    def _get_assertions(self):
        from tests.eval.chain.harness import load_chain
        return {a["name"]: a for a in load_chain(CHAIN_ID).get("assertions") or []}

    def test_has_rc_p1_classification_assertion(self):
        assertions = self._get_assertions()
        assert "rc_classifies_as_p1" in assertions

    def test_has_rc_cross_domain_assertion(self):
        assertions = self._get_assertions()
        assert "rc_cross_domain" in assertions

    def test_has_rc_routes_to_domain_collab_assertion(self):
        """P1 cross-domain must route to domain-collab (per workflow-routes.yml)."""
        assertions = self._get_assertions()
        assert "rc_routes_to_domain_collab" in assertions

    def test_has_rc_routes_to_spec_challenge_assertion(self):
        """P1 cross-domain must route to spec-challenge (unlike P1 single-domain)."""
        assertions = self._get_assertions()
        assert "rc_routes_to_spec_challenge" in assertions

    def test_has_wp_task_count_assertion(self):
        assertions = self._get_assertions()
        assert "wp_task_count_sufficient_for_p1" in assertions

    def test_has_sc_does_not_reject_assertion(self):
        assertions = self._get_assertions()
        assert "sc_does_not_reject_sound_plan" in assertions


class TestChainC2EndToEnd:
    """End-to-end run with mocked API — verifies P1 cross-domain artifact flow."""

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
            "change_type": "requirement",
            "domains": ["order", "inventory"],
            "routing": ["domain-collab", "writing-plans", "spec-challenge", "impl-verify"],
        })
        wp_resp = self._make_tool_response("plan_quality_result", {
            "task_count": 3,
            "has_plan_header": True,
            "every_task_has_tdd_steps": True,
            "every_task_has_file_paths": True,
            "has_rollback_notes": True,
            "implementation_strategy": "sequential",
            "requirement_points_covered": 3,
            "requirement_points_total": 3,
            "plan_content": "# Plan: 订单取消联动库存\n\n## Task 1: 取消订单\n库存 inventory释放",
        })
        sc_resp = self._make_tool_response("spec_challenge_quality_result", {
            "has_fatal_flaws": False,
            "fatal_flaw_count": 0,
            "fatal_flaw_topics": [],
            "improvement_count": 1,
            "blind_spot_count": 0,
            "conclusion_verdict": "pass",
            "review_content": "# 评审报告\n## 无 Fatal Flaws\n取消 Task 库存分析...",
        })

        from tests.eval.chain.harness import load_chain, run_chain
        chain_def = load_chain(CHAIN_ID)

        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.side_effect = [rc_resp, wp_resp, sc_resp]
            result = run_chain(chain_def)

        assert result["chain"]
        assert len(result["steps"]) == 3
        passed = {a["name"]: a["passed"] for a in result["assertions"]}
        assert passed.get("rc_classifies_as_p1") is True
        assert passed.get("rc_cross_domain") is True
        assert passed.get("rc_routes_to_domain_collab") is True
        assert passed.get("sc_does_not_reject_sound_plan") is True

    def test_all_assertions_pass_with_ideal_responses(self):
        """All chain assertions pass given ideal mock artifact values."""
        from tests.eval.chain.harness import load_chain
        from tests.eval.chain.assertions import run_assertions

        chain_def = load_chain(CHAIN_ID)
        mock_artifacts = {
            "risk-classifier": {
                "field:risk_level": "P1",
                "field:mode": "cross-domain",
                "field:change_type": "requirement",
                "field:domains": "['order', 'inventory']",
                "field:routing": "['domain-collab', 'writing-plans', 'spec-challenge', 'impl-verify', 'biz-impact-analysis']",
            },
            "writing-plans": {
                "field:task_count": "3",
                "field:has_plan_header": "True",
                "field:every_task_has_tdd_steps": "True",
                "field:every_task_has_file_paths": "True",
                "field:has_rollback_notes": "True",
                "field:implementation_strategy": "sequential",
                "field:requirement_points_covered": "3",
                "field:requirement_points_total": "3",
                "field:plan_content": "# Plan: 订单取消库存联动\n\n## Task 1: 取消 inventory 库存释放",
            },
            "spec-challenge": {
                "field:has_fatal_flaws": "False",
                "field:fatal_flaw_count": "0",
                "field:fatal_flaw_topics": "[]",
                "field:improvement_count": "1",
                "field:blind_spot_count": "0",
                "field:conclusion_verdict": "pass",
                "field:review_content": "评审报告内容 Task 取消 库存 specification...",
            },
        }
        results = run_assertions(chain_def["assertions"], mock_artifacts)
        failed = [r for r in results if not r["passed"]]
        assert not failed, f"Assertions failed: {[r['name'] for r in failed]}"
