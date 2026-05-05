"""Tests for c1_p0_single_plan_review chain YAML, fixtures, and prompt_file support.

Unit tests only — no real API calls.
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
CHAIN_ID = "c1_p0_single_plan_review"


class TestChainC1YAMLStructure:
    """Validate the chain YAML is well-formed and compatible with harness.py."""

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
        """spec-challenge must use agents/spec-challenge.md, not SKILL.md (coordinator)."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_step = chain["steps"][2]
        assert sc_step["skill"] == "spec-challenge"
        assert "prompt_file" in sc_step, (
            "spec-challenge step must declare prompt_file: agents/spec-challenge.md "
            "(SKILL.md is the coordinator; the review agent instructions are in agents/)"
        )

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
        assert pf.startswith("agents/"), f"prompt_file should be under agents/, got: {pf}"

    def test_chain_has_at_least_ten_assertions(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        assert len(chain.get("assertions") or []) >= 10

    def test_assertion_names_unique(self):
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        names = [a["name"] for a in chain.get("assertions") or []]
        assert len(names) == len(set(names)), "Duplicate assertion names found"

    def test_rc_and_wp_steps_have_no_prompt_file(self):
        """Only spec-challenge needs prompt_file; others use standard SKILL.md."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        for step in chain["steps"][:2]:
            assert "prompt_file" not in step, (
                f"Step '{step['skill']}' should not have prompt_file; "
                "only spec-challenge needs it"
            )

    def test_writing_plans_skill_files_no_prompts_dir(self):
        """prompts/*.md files are auto-loaded by skill_loader; don't list them in skill_files."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        wp_step = chain["steps"][1]
        for f in wp_step.get("skill_files") or []:
            assert not f.startswith("prompts/"), (
                f"'{f}' is in prompts/ and auto-loaded; remove from skill_files to avoid duplication"
            )

    def test_spec_challenge_skill_files_excludes_review_prompt_template(self):
        """review-prompt-template.md is the coordinator's dispatch template, not for the agent."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_step = chain["steps"][2]
        assert "prompts/review-prompt-template.md" not in (sc_step.get("skill_files") or [])

    def test_context_refs_use_correct_step_names(self):
        """from_step values must match the skill field of a prior step."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        prior_skills = set()
        for step in chain["steps"]:
            for _key, val in (step.get("context") or {}).items():
                if isinstance(val, dict) and "from_step" in val:
                    ref = val["from_step"]
                    assert ref in prior_skills, (
                        f"Step '{step['skill']}' context references '{ref}' "
                        f"which hasn't been seen yet. Prior: {prior_skills}"
                    )
            prior_skills.add(step["skill"])

    def test_rc_step_context_uses_fixtures(self):
        """risk-classifier context should load ecw.yml and domain-registry from fixtures."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        rc_context = chain["steps"][0].get("context") or {}
        fixture_vals = [v for v in rc_context.values() if isinstance(v, str) and v.startswith("fixtures/")]
        assert len(fixture_vals) >= 2, "RC step should load at least 2 fixtures (ecw_yml, domain_registry)"

    def test_wp_step_session_state_from_rc(self):
        """writing-plans must receive session_state from risk-classifier output."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        wp_context = chain["steps"][1].get("context") or {}
        ss = wp_context.get("session_state")
        assert isinstance(ss, dict) and ss.get("from_step") == "risk-classifier"

    def test_sc_step_plan_document_from_wp(self):
        """spec-challenge must receive plan content from writing-plans.plan_content."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        sc_context = chain["steps"][2].get("context") or {}
        pd = sc_context.get("plan_document")
        assert isinstance(pd, dict)
        assert pd.get("from_step") == "writing-plans"
        assert pd.get("field") == "plan_content"


class TestChainC1Fixtures:
    """Validate fixture files exist and have the expected content."""

    def test_ecw_yml_exists(self):
        assert (FIXTURES_DIR / "ecw_yml_java_monolith.yaml").exists()

    def test_domain_registry_exists(self):
        assert (FIXTURES_DIR / "domain_registry_5domains.md").exists()

    def test_path_mappings_exists(self):
        assert (FIXTURES_DIR / "path_mappings_standard.md").exists()

    def test_ecw_yml_is_valid_yaml(self):
        content = (FIXTURES_DIR / "ecw_yml_java_monolith.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict)

    def test_ecw_yml_has_java_monolith_config(self):
        data = yaml.safe_load(
            (FIXTURES_DIR / "ecw_yml_java_monolith.yaml").read_text(encoding="utf-8")
        )
        assert data.get("project", {}).get("language") == "java"
        assert data.get("project", {}).get("type") == "java-monolith"

    def test_ecw_yml_has_output_language(self):
        data = yaml.safe_load(
            (FIXTURES_DIR / "ecw_yml_java_monolith.yaml").read_text(encoding="utf-8")
        )
        assert data.get("project", {}).get("output_language") == "zh-CN"

    def test_ecw_yml_has_tdd_config(self):
        data = yaml.safe_load(
            (FIXTURES_DIR / "ecw_yml_java_monolith.yaml").read_text(encoding="utf-8")
        )
        assert "tdd" in data
        assert data["tdd"].get("enabled") is True

    def test_domain_registry_has_exactly_five_domains(self):
        content = (FIXTURES_DIR / "domain_registry_5domains.md").read_text(encoding="utf-8")
        domain_count = sum(1 for line in content.splitlines() if line.startswith("## "))
        assert domain_count == 5, f"Expected 5 domains, got {domain_count}"

    def test_domain_registry_contains_payment(self):
        content = (FIXTURES_DIR / "domain_registry_5domains.md").read_text(encoding="utf-8")
        assert "## payment" in content

    def test_domain_registry_has_code_dirs(self):
        content = (FIXTURES_DIR / "domain_registry_5domains.md").read_text(encoding="utf-8")
        assert "代码目录" in content

    def test_path_mappings_is_table(self):
        content = (FIXTURES_DIR / "path_mappings_standard.md").read_text(encoding="utf-8")
        assert "|" in content, "path_mappings should be a markdown table"

    def test_path_mappings_contains_all_five_domains(self):
        content = (FIXTURES_DIR / "path_mappings_standard.md").read_text(encoding="utf-8")
        for domain in ("payment", "order", "inventory", "user", "notification"):
            assert domain in content, f"path_mappings missing domain '{domain}'"

    def test_fixtures_referenced_in_chain_yaml_exist(self):
        """Every fixture path referenced in chain steps must resolve to an actual file."""
        from tests.eval.chain.harness import load_chain
        chain = load_chain(CHAIN_ID)
        for step in chain["steps"]:
            for _key, val in (step.get("context") or {}).items():
                if isinstance(val, str) and val.startswith("fixtures/"):
                    fixture_path = FIXTURES_DIR.parent / val  # chains/../fixtures/...
                    # context_builder resolves fixtures/ relative to CHAIN_DIR
                    alt_path = Path(__file__).parent / val
                    assert alt_path.exists(), f"Fixture '{val}' not found at {alt_path}"


class TestSkillLoaderPromptFile:
    """Tests for the new prompt_file parameter in load_skill_prompt."""

    def test_prompt_file_overrides_skill_md(self, tmp_path, monkeypatch):
        """When prompt_file is given, load that file instead of SKILL.md + prompts/."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "test-agent.md").write_text("# Agent Instructions", encoding="utf-8")

        import tests.eval.chain.skill_loader as sl
        monkeypatch.setattr(sl, "PROJECT_ROOT", tmp_path)

        result = sl.load_skill_prompt("any-skill", prompt_file="agents/test-agent.md")
        assert result == "# Agent Instructions"

    def test_prompt_file_not_found_raises(self, tmp_path, monkeypatch):
        """When prompt_file path doesn't exist, raises FileNotFoundError."""
        import tests.eval.chain.skill_loader as sl
        monkeypatch.setattr(sl, "PROJECT_ROOT", tmp_path)

        with pytest.raises(FileNotFoundError, match="prompt_file not found"):
            sl.load_skill_prompt("any-skill", prompt_file="agents/nonexistent.md")

    def test_prompt_file_with_extra_files_appended(self, tmp_path, monkeypatch):
        """When prompt_file is given, extra_files are still appended from skill dir."""
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "review-agent.md").write_text("# Review Agent", encoding="utf-8")

        skills_dir = tmp_path / "skills"
        sc_dir = skills_dir / "spec-challenge"
        sc_dir.mkdir(parents=True)
        (sc_dir / "extra.md").write_text("# Extra Content", encoding="utf-8")

        import tests.eval.chain.skill_loader as sl
        monkeypatch.setattr(sl, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(sl, "SKILLS_DIR", skills_dir)

        result = sl.load_skill_prompt(
            "spec-challenge",
            extra_files=["extra.md"],
            prompt_file="agents/review-agent.md",
        )
        assert "# Review Agent" in result
        assert "# Extra Content" in result

    def test_prompt_file_none_uses_skill_md(self, tmp_path, monkeypatch):
        """Without prompt_file, SKILL.md is loaded as before."""
        skill_dir = tmp_path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# My Skill", encoding="utf-8")

        import tests.eval.chain.skill_loader as sl
        monkeypatch.setattr(sl, "SKILLS_DIR", tmp_path / "skills")

        result = sl.load_skill_prompt("my-skill")
        assert result == "# My Skill"

    def test_harness_run_step_passes_prompt_file_to_loader(self):
        """run_step reads prompt_file from step dict and passes to skill_loader."""
        step = {
            "skill": "spec-challenge",
            "input": "review this plan",
            "prompt_file": "agents/spec-challenge.md",
        }
        mock_resp = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "review done"
        mock_resp.content = [text_block]

        with patch("tests.eval.chain.harness.CLIENT") as mock_client, \
             patch("tests.eval.chain.harness.load_skill_prompt") as mock_loader:
            mock_client.messages.create.return_value = mock_resp
            mock_loader.return_value = "agent prompt content"
            from tests.eval.chain.harness import run_step
            run_step(step, {})
            mock_loader.assert_called_once_with(
                "spec-challenge",
                extra_files=None,
                prompt_file="agents/spec-challenge.md",
            )


class TestChainC1EndToEnd:
    """End-to-end chain run with mocked API — verifies artifact flow and assertions."""

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
            "risk_level": "P0",
            "mode": "single-domain",
            "change_type": "requirement",
            "domains": ["payment"],
            "routing": ["writing-plans", "spec-challenge"],
        })
        wp_resp = self._make_tool_response("plan_quality_result", {
            "task_count": 4,
            "has_plan_header": True,
            "every_task_has_tdd_steps": True,
            "every_task_has_file_paths": True,
            "has_rollback_notes": True,
            "implementation_strategy": "subagent-driven",
            "requirement_points_covered": 3,
            "requirement_points_total": 3,
            "plan_content": "# Plan: 支付退款\n\n## Task 1: 幂等退款逻辑\n退款 refund logic",
        })
        sc_resp = self._make_tool_response("spec_challenge_quality_result", {
            "has_fatal_flaws": False,
            "fatal_flaw_count": 0,
            "fatal_flaw_topics": [],
            "improvement_count": 2,
            "blind_spot_count": 1,
            "conclusion_verdict": "pass",
            "review_content": (
                "# 评审报告\n\n## Fatal Flaws\n无。\n\n"
                "## Improvement Suggestions\n改进建议 Task 退款 相关..."
            ),
        })

        from tests.eval.chain.harness import load_chain, run_chain
        chain_def = load_chain(CHAIN_ID)

        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.side_effect = [rc_resp, wp_resp, sc_resp]
            result = run_chain(chain_def)

        assert result["chain"]
        assert len(result["steps"]) == 3
        passed = {a["name"]: a["passed"] for a in result["assertions"]}
        assert passed.get("rc_classifies_as_p0") is True
        assert passed.get("rc_single_domain") is True
        assert passed.get("wp_has_rollback_notes_for_p0") is True
        assert passed.get("sc_does_not_reject_sound_plan") is True

    def test_assertion_refs_valid_with_complete_artifacts(self):
        """validate_assertion_refs passes given a complete mock artifacts dict."""
        from tests.eval.chain.harness import load_chain
        from tests.eval.chain.assertions import validate_assertion_refs

        chain_def = load_chain(CHAIN_ID)
        mock_artifacts = {
            "risk-classifier": {
                "tool_result": json.dumps({
                    "risk_level": "P0",
                    "mode": "single-domain",
                    "change_type": "requirement",
                    "domains": ["payment"],
                    "routing": ["writing-plans", "spec-challenge"],
                }),
                "field:risk_level": "P0",
                "field:mode": "single-domain",
                "field:change_type": "requirement",
                "field:domains": "['payment']",
                "field:routing": "['writing-plans', 'spec-challenge']",
            },
            "writing-plans": {
                "tool_result": json.dumps({"task_count": 4}),
                "field:task_count": "4",
                "field:has_plan_header": "True",
                "field:every_task_has_tdd_steps": "True",
                "field:every_task_has_file_paths": "True",
                "field:has_rollback_notes": "True",
                "field:implementation_strategy": "subagent-driven",
                "field:requirement_points_covered": "3",
                "field:requirement_points_total": "3",
                "field:plan_content": "# Plan: 支付退款\n## Task 1 退款 logic",
            },
            "spec-challenge": {
                "tool_result": json.dumps({"has_fatal_flaws": False}),
                "field:has_fatal_flaws": "False",
                "field:fatal_flaw_count": "0",
                "field:fatal_flaw_topics": "[]",
                "field:improvement_count": "2",
                "field:blind_spot_count": "1",
                "field:conclusion_verdict": "pass",
                "field:review_content": "评审报告 Task 退款 相关内容",
            },
        }
        # Should not raise
        validate_assertion_refs(chain_def["assertions"], mock_artifacts)

    def test_all_assertions_pass_with_ideal_responses(self):
        """All chain assertions pass given ideal mock artifact values."""
        from tests.eval.chain.harness import load_chain
        from tests.eval.chain.assertions import run_assertions

        chain_def = load_chain(CHAIN_ID)
        mock_artifacts = {
            "risk-classifier": {
                "field:risk_level": "P0",
                "field:mode": "single-domain",
                "field:change_type": "requirement",
                "field:domains": "['payment']",
                "field:routing": "['writing-plans', 'spec-challenge', 'tdd', 'impl-verify']",
            },
            "writing-plans": {
                "field:task_count": "4",
                "field:has_plan_header": "True",
                "field:every_task_has_tdd_steps": "True",
                "field:every_task_has_file_paths": "True",
                "field:has_rollback_notes": "True",
                "field:implementation_strategy": "subagent-driven",
                "field:requirement_points_covered": "3",
                "field:requirement_points_total": "3",
                "field:plan_content": "# Plan: 支付退款\n\n## Task 1: 幂等退款\n退款逻辑",
            },
            "spec-challenge": {
                "field:has_fatal_flaws": "False",
                "field:fatal_flaw_count": "0",
                "field:fatal_flaw_topics": "[]",
                "field:improvement_count": "2",
                "field:blind_spot_count": "1",
                "field:conclusion_verdict": "pass",
                "field:review_content": "评审报告内容 Task 退款 specification...",
            },
        }
        results = run_assertions(chain_def["assertions"], mock_artifacts)
        failed = [r for r in results if not r["passed"]]
        assert not failed, f"Assertions failed: {[r['name'] for r in failed]}"
