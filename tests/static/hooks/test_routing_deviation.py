#!/usr/bin/env python3
"""Tests for routing chain deviation detection in auto-continue hook."""

import importlib.util
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOKS_DIR = ROOT / "hooks"


def _load_auto_continue():
    spec = importlib.util.spec_from_file_location(
        "auto_continue", HOOKS_DIR / "auto-continue.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_auto_continue()
_check_routing_deviation = _mod._check_routing_deviation
_OFF_CHAIN_ALLOWED = _mod._OFF_CHAIN_ALLOWED


def test_on_chain_no_deviation():
    """Normal on-chain call should not report deviation."""
    routing = ["requirements-elicitation", "Phase 2", "writing-plans", "impl-verify"]
    current = "ecw:writing-plans"
    expected = "ecw:writing-plans"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_skip_intermediate_skill():
    """Skipping intermediate skills should report out-of-order deviation."""
    routing = ["requirements-elicitation", "Phase 2", "writing-plans", "impl-verify"]
    current = "ecw:impl-verify"
    expected = "ecw:writing-plans"

    result = _check_routing_deviation(routing, current, expected)
    assert result is not None
    assert result["type"] == "out-of-order"
    assert "writing-plans" in result["detail"]
    assert "impl-verify" in result["detail"]


def test_off_chain_not_whitelisted():
    """Off-chain skill not in whitelist should report off-chain deviation."""
    routing = ["requirements-elicitation", "Phase 2", "writing-plans"]
    current = "ecw:impl-verify"
    expected = None

    result = _check_routing_deviation(routing, current, expected)
    assert result is not None
    assert result["type"] == "off-chain"
    assert "impl-verify" in result["detail"]


def test_off_chain_whitelisted():
    """Whitelisted off-chain skills should not report deviation."""
    routing = ["requirements-elicitation", "Phase 2", "writing-plans"]

    for skill in _OFF_CHAIN_ALLOWED:
        result = _check_routing_deviation(routing, skill, None)
        assert result is None, f"Whitelisted skill {skill} should not report deviation"


def test_routing_list_type():
    """Should accept routing as a list."""
    routing = ["requirements-elicitation", "writing-plans", "impl-verify"]
    current = "ecw:writing-plans"
    expected = "ecw:writing-plans"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_empty_routing():
    """Empty routing should not report deviation (no chain to validate)."""
    routing = []
    current = "ecw:impl-verify"
    expected = None

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_none_routing():
    """None routing should not report deviation."""
    routing = None
    current = "ecw:impl-verify"
    expected = None

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_routing_with_non_skill_steps():
    """Routing with non-skill steps (Phase 2, TDD:RED) should be handled correctly."""
    routing = ["requirements-elicitation", "Phase 2", "writing-plans", "TDD:RED", "Implementation(GREEN)", "impl-verify"]
    current = "ecw:tdd"
    expected = "ecw:tdd"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_expected_next_none_on_chain():
    """When expected_next is None but skill is on-chain, should not report deviation."""
    routing = ["requirements-elicitation", "writing-plans", "impl-verify"]
    current = "ecw:impl-verify"
    expected = None

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_tdd_alias_matching():
    """TDD skill with routing alias TDD:RED should match correctly."""
    routing = ["writing-plans", "TDD:RED", "Implementation(GREEN)", "impl-verify"]
    current = "ecw:tdd"
    expected = "ecw:tdd"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_systematic_debugging_on_chain():
    """systematic-debugging in bug fix routing should not report deviation."""
    routing = ["systematic-debugging", "TDD:RED", "Fix(GREEN)", "impl-verify"]
    current = "ecw:systematic-debugging"
    expected = "ecw:systematic-debugging"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


def test_domain_collab_cross_domain():
    """domain-collab in cross-domain routing should not report deviation."""
    routing = ["domain-collab", "Phase 2", "writing-plans", "spec-challenge", "impl-verify"]
    current = "ecw:domain-collab"
    expected = "ecw:domain-collab"

    result = _check_routing_deviation(routing, current, expected)
    assert result is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
