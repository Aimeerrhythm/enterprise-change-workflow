"""Unit tests for harness.py.

Tests chain loading, step execution (with mocked API), and result structure.
Does NOT make real API calls — all Claude responses are mocked.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

EVAL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "eval"
CHAIN_DIR = EVAL_DIR / "chain"


def _make_tool_response(tool_name: str, input_dict: dict):
    """Create a mock Anthropic API response with a single tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = input_dict
    block.name = tool_name
    resp = MagicMock()
    resp.content = [block]
    return resp


def _make_text_response(text: str):
    """Create a mock Anthropic API response with a single text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


class TestLoadChain:
    """Tests for load_chain()."""

    def test_load_valid_chain(self, tmp_path, monkeypatch):
        """Chain YAML is loaded and returned as dict."""
        chain_file = tmp_path / "c_test.yaml"
        chain_file.write_text(
            'name: "Test Chain"\nsteps:\n  - skill: risk-classifier\n    input: "hello"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr("tests.eval.chain.harness.CHAIN_DIR", tmp_path)
        from tests.eval.chain.harness import load_chain
        result = load_chain("c_test")
        assert result["name"] == "Test Chain"
        assert result["steps"][0]["skill"] == "risk-classifier"

    def test_load_missing_chain_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tests.eval.chain.harness.CHAIN_DIR", tmp_path)
        from tests.eval.chain.harness import load_chain
        with pytest.raises(FileNotFoundError):
            load_chain("nonexistent_chain")


class TestRunStep:
    """Tests for run_step()."""

    def test_tool_use_response_captured(self):
        """Tool use response is captured as field:xxx keys in artifacts."""
        step = {
            "skill": "risk-classifier",
            "input": "payment refund flow",
            "tool_schema": "tools/classify_result.json",
        }
        mock_resp = _make_tool_response("classify_result", {
            "risk_level": "P0",
            "mode": "single-domain",
            "routing": ["writing-plans"],
        })
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_step
            artifacts = run_step(step, {})

        assert "tool_result" in artifacts
        assert artifacts["field:risk_level"] == "P0"
        assert artifacts["field:mode"] == "single-domain"

    def test_text_response_captured(self):
        """Text-only response (no tool) captured as text_output."""
        step = {
            "skill": "risk-classifier",
            "input": "what risk is this",
        }
        mock_resp = _make_text_response("This is P2 risk.")
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_step
            artifacts = run_step(step, {})

        assert artifacts["text_output"] == "This is P2 risk."
        assert "tool_result" not in artifacts

    def test_tool_schema_resolved_relative_to_eval_dir(self):
        """tool_schema path is resolved relative to tests/eval/, not chain/."""
        step = {
            "skill": "risk-classifier",
            "input": "test",
            "tool_schema": "tools/classify_result.json",
        }
        mock_resp = _make_tool_response("classify_result", {"risk_level": "P0"})
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_step
            # Should not raise — classify_result.json exists at tests/eval/tools/
            artifacts = run_step(step, {})
        assert "field:risk_level" in artifacts

    def test_tool_schema_writing_plans_resolved(self):
        """tool_schema for writing-plans resolves to L2b tools dir."""
        step = {
            "skill": "writing-plans",
            "input": "generate plan",
            "tool_schema": "writing-plans/tools/plan_quality_result.json",
        }
        mock_resp = _make_tool_response("plan_quality_result", {
            "task_count": 5,
            "has_plan_header": True,
            "every_task_has_tdd_steps": True,
            "every_task_has_file_paths": True,
            "implementation_strategy": "direct",
            "requirement_points_covered": 3,
            "requirement_points_total": 3,
            "plan_content": "# Plan",
        })
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_step
            artifacts = run_step(step, {})
        assert artifacts["field:task_count"] == "5"

    def test_prior_artifacts_passed_to_context_builder(self):
        """Prior step artifacts are forwarded to build_context."""
        step = {
            "skill": "writing-plans",
            "input": "gen plan",
            "context": {"session_state": {"from_step": "risk-classifier"}},
        }
        prior = {
            "risk-classifier": {
                "tool_result": json.dumps({"risk_level": "P0", "mode": "single-domain", "routing": ["writing-plans"], "domains": ["payment"]})
            }
        }
        mock_resp = _make_text_response("plan content here")
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_step
            artifacts = run_step(step, prior)
        # Verify the API was called with a system prompt containing session state
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "ECW:STATUS:START" in call_kwargs["system"] or "P0" in call_kwargs["system"]

    def test_skill_files_forwarded_to_loader(self):
        """chain step skill_files are passed to skill_loader."""
        step = {
            "skill": "risk-classifier",
            "input": "test",
            "skill_files": ["session-state-format.md"],
        }
        mock_resp = _make_text_response("response")
        with patch("tests.eval.chain.harness.CLIENT") as mock_client, \
             patch("tests.eval.chain.harness.load_skill_prompt") as mock_loader:
            mock_client.messages.create.return_value = mock_resp
            mock_loader.return_value = "skill content"
            from tests.eval.chain.harness import run_step
            run_step(step, {})
            mock_loader.assert_called_once_with("risk-classifier", extra_files=["session-state-format.md"], prompt_file=None)


class TestRunChain:
    """Tests for run_chain()."""

    def test_chain_result_structure(self):
        """run_chain returns dict with chain name, steps list, and assertions list."""
        chain_def = {
            "name": "Test Chain",
            "steps": [
                {"skill": "risk-classifier", "input": "test payment flow"},
            ],
            "assertions": [],
        }
        mock_resp = _make_tool_response("classify_result", {
            "risk_level": "P0",
            "mode": "single-domain",
            "routing": ["writing-plans"],
        })
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_chain
            result = run_chain(chain_def)

        assert result["chain"] == "Test Chain"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["skill"] == "risk-classifier"
        assert "duration_s" in result["steps"][0]
        assert result["assertions"] == []

    def test_artifact_accumulation_across_steps(self):
        """Each step's artifacts are available to subsequent steps."""
        step1_resp = _make_tool_response("classify_result", {"risk_level": "P1", "mode": "single-domain", "routing": ["writing-plans"]})
        step2_resp = _make_text_response("plan based on P1")
        chain_def = {
            "name": "Two Step Chain",
            "steps": [
                {"skill": "risk-classifier", "input": "first step"},
                {
                    "skill": "writing-plans",
                    "input": "second step",
                    "context": {"session_state": {"from_step": "risk-classifier"}},
                },
            ],
            "assertions": [],
        }
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.side_effect = [step1_resp, step2_resp]
            from tests.eval.chain.harness import run_chain
            result = run_chain(chain_def)

        assert len(result["steps"]) == 2
        # Second step should have had access to first step's artifacts (verified via system prompt)
        second_call = mock_client.messages.create.call_args_list[1]
        system = second_call[1]["system"]
        assert "P1" in system or "ECW:STATUS:START" in system

    def test_assertions_run_after_all_steps(self):
        """Assertions are evaluated after all steps complete."""
        chain_def = {
            "name": "Assert Chain",
            "steps": [
                {"skill": "risk-classifier", "input": "payment"},
            ],
            "assertions": [
                {"name": "level check", "check": {"field": "risk-classifier.risk_level", "op": "==", "value": "P0"}},
            ],
        }
        mock_resp = _make_tool_response("classify_result", {"risk_level": "P0", "mode": "single-domain", "routing": []})
        with patch("tests.eval.chain.harness.CLIENT") as mock_client:
            mock_client.messages.create.return_value = mock_resp
            from tests.eval.chain.harness import run_chain
            result = run_chain(chain_def)

        assert len(result["assertions"]) == 1
        assert result["assertions"][0]["name"] == "level check"
        assert result["assertions"][0]["passed"] is True
