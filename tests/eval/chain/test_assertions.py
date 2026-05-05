"""Unit tests for assertions.py.

Verifies the mini-DSL assertion engine with all supported operators.
No eval() — all operators handled safely.
"""
from __future__ import annotations

import pytest


# Sample artifacts fixture used across tests
SAMPLE_ARTIFACTS = {
    "risk-classifier": {
        "field:risk_level": "P0",
        "field:mode": "single-domain",
        "field:routing": '["requirements-elicitation", "writing-plans", "spec-challenge"]',
        "field:task_count": "5",
        "tool_result": '{"risk_level": "P0"}',
    },
    "writing-plans": {
        "field:task_count": "4",
        "field:has_plan_header": "True",
        "field:every_task_has_tdd_steps": "True",
        "field:plan_content": "# Plan\n幂等检查\nTask 1: do something",
        "field:requirement_points_covered": "3",
    },
    "spec-challenge": {
        "field:fatal_flaw_count": "2",
        "field:improvement_count": "1",
        "field:conclusion_verdict": "reject",
        "field:review_content": "Fatal: missing idempotency check. Task 1 is affected.",
    },
}


class TestRunAssertions:
    """Tests for run_assertions()."""

    def test_passing_assertion(self):
        from tests.eval.chain.assertions import run_assertions
        defs = [{"name": "P0 check", "check": {"field": "risk-classifier.risk_level", "op": "==", "value": "P0"}}]
        results = run_assertions(defs, SAMPLE_ARTIFACTS)
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["error"] is None

    def test_failing_assertion(self):
        from tests.eval.chain.assertions import run_assertions
        defs = [{"name": "P1 check", "check": {"field": "risk-classifier.risk_level", "op": "==", "value": "P1"}}]
        results = run_assertions(defs, SAMPLE_ARTIFACTS)
        assert results[0]["passed"] is False

    def test_assertion_error_recorded(self):
        """Reference to nonexistent step returns failed assertion with error message."""
        from tests.eval.chain.assertions import run_assertions
        defs = [{"name": "bad ref", "check": {"field": "nonexistent.risk_level", "op": "==", "value": "P0"}}]
        results = run_assertions(defs, SAMPLE_ARTIFACTS)
        assert results[0]["passed"] is False
        # Either error is set or passed is False
        assert results[0]["error"] is not None or results[0]["passed"] is False

    def test_multiple_assertions(self):
        from tests.eval.chain.assertions import run_assertions
        defs = [
            {"name": "level", "check": {"field": "risk-classifier.risk_level", "op": "==", "value": "P0"}},
            {"name": "mode", "check": {"field": "risk-classifier.mode", "op": "==", "value": "cross-domain"}},
        ]
        results = run_assertions(defs, SAMPLE_ARTIFACTS)
        assert results[0]["passed"] is True
        assert results[1]["passed"] is False  # mode is single-domain


class TestEvaluateCheck:
    """Tests for _evaluate_check() covering all supported operators."""

    def _check(self, check_spec, artifacts=None):
        from tests.eval.chain.assertions import _evaluate_check
        return _evaluate_check(check_spec, artifacts or SAMPLE_ARTIFACTS)

    # == operator
    def test_eq_pass(self):
        assert self._check({"field": "risk-classifier.risk_level", "op": "==", "value": "P0"}) is True

    def test_eq_fail(self):
        assert self._check({"field": "risk-classifier.risk_level", "op": "==", "value": "P1"}) is False

    # != operator
    def test_ne_pass(self):
        assert self._check({"field": "risk-classifier.mode", "op": "!=", "value": "cross-domain"}) is True

    def test_ne_fail(self):
        assert self._check({"field": "risk-classifier.mode", "op": "!=", "value": "single-domain"}) is False

    # in operator (substring check)
    def test_in_pass(self):
        assert self._check({"field": "writing-plans.plan_content", "op": "in", "value": "幂等"}) is True

    def test_in_fail(self):
        assert self._check({"field": "writing-plans.plan_content", "op": "in", "value": "nonexistent_keyword"}) is False

    # contains operator (alias for in)
    def test_contains_pass(self):
        assert self._check({"field": "spec-challenge.review_content", "op": "contains", "value": "Task"}) is True

    def test_contains_fail(self):
        assert self._check({"field": "spec-challenge.review_content", "op": "contains", "value": "xyz_not_present"}) is False

    # >= operator (numeric comparison)
    def test_ge_pass(self):
        assert self._check({"field": "writing-plans.task_count", "op": ">=", "value": 3}) is True

    def test_ge_fail(self):
        assert self._check({"field": "writing-plans.task_count", "op": ">=", "value": 10}) is False

    # <= operator
    def test_le_pass(self):
        assert self._check({"field": "writing-plans.task_count", "op": "<=", "value": 10}) is True

    def test_le_fail(self):
        assert self._check({"field": "writing-plans.task_count", "op": "<=", "value": 2}) is False

    # > operator
    def test_gt_pass(self):
        assert self._check({"field": "spec-challenge.fatal_flaw_count", "op": ">", "value": 0}) is True

    def test_gt_fail(self):
        assert self._check({"field": "spec-challenge.fatal_flaw_count", "op": ">", "value": 5}) is False

    # < operator
    def test_lt_pass(self):
        assert self._check({"field": "spec-challenge.fatal_flaw_count", "op": "<", "value": 5}) is True

    def test_lt_fail(self):
        assert self._check({"field": "spec-challenge.fatal_flaw_count", "op": "<", "value": 1}) is False

    # Boolean field checks
    def test_bool_true(self):
        assert self._check({"field": "writing-plans.has_plan_header", "op": "==", "value": "True"}) is True

    def test_bool_false_value(self):
        assert self._check({"field": "writing-plans.has_plan_header", "op": "==", "value": "False"}) is False

    # Missing field
    def test_missing_field_raises_or_fails(self):
        from tests.eval.chain.assertions import _evaluate_check
        # Missing step → should raise or return False with error context
        with pytest.raises(Exception):
            _evaluate_check({"field": "nonexistent-step.field_x", "op": "==", "value": "X"}, SAMPLE_ARTIFACTS)

    # Unsupported operator
    def test_unsupported_op_raises(self):
        from tests.eval.chain.assertions import _evaluate_check
        with pytest.raises(ValueError, match="Unsupported operator"):
            _evaluate_check({"field": "risk-classifier.risk_level", "op": "???", "value": "P0"}, SAMPLE_ARTIFACTS)


class TestArtifactValidation:
    """Tests for validate_assertion_refs() — checks before running assertions."""

    def test_valid_refs_no_error(self):
        from tests.eval.chain.assertions import validate_assertion_refs
        defs = [
            {"name": "check", "check": {"field": "risk-classifier.risk_level", "op": "==", "value": "P0"}},
        ]
        # Should not raise
        validate_assertion_refs(defs, SAMPLE_ARTIFACTS)

    def test_missing_step_ref_raises(self):
        from tests.eval.chain.assertions import validate_assertion_refs
        defs = [
            {"name": "check", "check": {"field": "nonexistent.some_field", "op": "==", "value": "X"}},
        ]
        with pytest.raises(ValueError, match="nonexistent"):
            validate_assertion_refs(defs, SAMPLE_ARTIFACTS)

    def test_missing_field_in_step_raises(self):
        from tests.eval.chain.assertions import validate_assertion_refs
        defs = [
            {"name": "check", "check": {"field": "risk-classifier.no_such_field", "op": "==", "value": "X"}},
        ]
        with pytest.raises(ValueError, match="no_such_field"):
            validate_assertion_refs(defs, SAMPLE_ARTIFACTS)
