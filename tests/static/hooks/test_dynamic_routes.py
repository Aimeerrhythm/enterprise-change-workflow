#!/usr/bin/env python3
"""Tests for dynamic route loading from workflow-routes.yml (Issue #62 Part 1).

Verifies that auto-continue.py generates mapping tables at runtime from
workflow-routes.yml rather than maintaining hardcoded dictionaries.
"""

import importlib.util
import sys
import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOKS_DIR = ROOT / "hooks"
SKILLS_DIR = ROOT / "skills"
ROUTES_FILE = SKILLS_DIR / "risk-classifier" / "workflow-routes.yml"


def _load_auto_continue():
    spec = importlib.util.spec_from_file_location(
        "auto_continue", HOOKS_DIR / "auto-continue.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_routes():
    return yaml.safe_load(ROUTES_FILE.read_text(encoding="utf-8"))


class TestNoHardcodedDicts:
    """Verify that hardcoded dictionaries have been removed from auto-continue.py."""

    @pytest.fixture(autouse=True)
    def load_source(self):
        self.source = (HOOKS_DIR / "auto-continue.py").read_text(encoding="utf-8")

    def test_no_static_skill_completed_phase(self):
        """_SKILL_COMPLETED_PHASE must not be a hardcoded dict literal."""
        assert "_SKILL_COMPLETED_PHASE = {" not in self.source, (
            "_SKILL_COMPLETED_PHASE is still a hardcoded dict — must be generated from routes.yml"
        )

    def test_no_static_skill_mode(self):
        """_SKILL_MODE must not be a hardcoded dict literal."""
        assert "_SKILL_MODE = {" not in self.source, (
            "_SKILL_MODE is still a hardcoded dict — must be generated from routes.yml"
        )

    def test_no_static_routing_aliases(self):
        """_SKILL_ROUTING_ALIASES must not be a hardcoded dict literal."""
        assert "_SKILL_ROUTING_ALIASES = {" not in self.source, (
            "_SKILL_ROUTING_ALIASES is still a hardcoded dict — must be generated from routes.yml"
        )

    def test_no_static_routing_step_to_skill(self):
        """_ROUTING_STEP_TO_SKILL must not be a hardcoded dict literal."""
        assert "_ROUTING_STEP_TO_SKILL = {" not in self.source, (
            "_ROUTING_STEP_TO_SKILL is still a hardcoded dict — must be generated from routes.yml"
        )

    def test_no_static_off_chain_allowed(self):
        """_OFF_CHAIN_ALLOWED must not be a hardcoded set literal."""
        assert "_OFF_CHAIN_ALLOWED = {" not in self.source, (
            "_OFF_CHAIN_ALLOWED is still a hardcoded set — must be generated from routes.yml"
        )


class TestDynamicLoading:
    """Verify dynamic loading produces correct mappings from workflow-routes.yml."""

    @pytest.fixture(autouse=True)
    def load_module(self):
        self.mod = _load_auto_continue()

    def test_skill_completed_phase_has_all_chain_skills(self):
        """Every skill appearing in any route chain must have a phase mapping."""
        routes = _load_routes()
        chain_skills = set()
        for route in routes["routes"]:
            for step in route.get("chain", []):
                step_lower = step.lower().replace("-", "-")
                # Only consider steps that look like skill names (no spaces, no special markers)
                if " " not in step and "(" not in step and ":" not in step:
                    chain_skills.add(f"ecw:{step}")

        for skill in chain_skills:
            assert skill in self.mod._SKILL_COMPLETED_PHASE, (
                f"Skill '{skill}' appears in routes.yml chain but has no phase mapping"
            )

    def test_all_phase_values_end_with_loaded(self):
        """All phase values must end with '-loaded'."""
        for skill, phase in self.mod._SKILL_COMPLETED_PHASE.items():
            assert phase.endswith("-loaded"), (
                f"Skill '{skill}' phase '{phase}' must end with '-loaded'"
            )

    def test_off_chain_includes_manual_skills(self):
        """Off-chain whitelist must include manual-only tools."""
        for skill in ("ecw:cross-review", "ecw:knowledge-audit",
                      "ecw:knowledge-repomap", "ecw:workspace"):
            assert skill in self.mod._OFF_CHAIN_ALLOWED, (
                f"Manual skill '{skill}' missing from _OFF_CHAIN_ALLOWED"
            )

    def test_tdd_has_routing_aliases(self):
        """ecw:tdd must have TDD:RED and Implementation(GREEN) as routing aliases."""
        aliases = self.mod._SKILL_ROUTING_ALIASES.get("ecw:tdd", [])
        assert "TDD:RED" in aliases
        assert "Implementation(GREEN)" in aliases

    def test_routing_step_to_skill_covers_tdd_red(self):
        """TDD:RED must resolve to ecw:tdd."""
        assert self.mod._ROUTING_STEP_TO_SKILL.get("TDD:RED") == "ecw:tdd"


class TestDynamicLoadingWithModifiedRoutes:
    """Verify that adding a dummy skill to routes.yml is automatically picked up."""

    def test_dummy_skill_in_routes_produces_mapping(self, tmp_path, monkeypatch):
        """If routes.yml has a new skill in skill_metadata, dynamic loading must include it."""
        routes = _load_routes()
        # Add a dummy skill to skill_metadata
        routes["skill_metadata"]["dummy-new-skill"] = {
            "mode": "verification",
            "phase_name": "dummy",
        }

        # Write modified routes to tmp
        tmp_routes = tmp_path / "workflow-routes.yml"
        tmp_routes.write_text(yaml.dump(routes, allow_unicode=True))

        # Re-generate mappings with modified routes
        mod = _load_auto_continue()
        mappings = mod._load_routes_from_file(str(tmp_routes))
        assert "ecw:dummy-new-skill" in mappings["completed_phase"]
        assert mappings["completed_phase"]["ecw:dummy-new-skill"] == "dummy-loaded"


class TestBehaviorPreservation:
    """Ensure dynamic loading preserves existing behavior from hardcoded dicts."""

    @pytest.fixture(autouse=True)
    def load_module(self):
        self.mod = _load_auto_continue()

    def test_risk_classifier_phase(self):
        assert self.mod._SKILL_COMPLETED_PHASE["ecw:risk-classifier"] == "phase1-loaded"

    def test_writing_plans_phase(self):
        assert self.mod._SKILL_COMPLETED_PHASE["ecw:writing-plans"] == "plan-loaded"

    def test_impl_verify_phase(self):
        assert self.mod._SKILL_COMPLETED_PHASE["ecw:impl-verify"] == "verify-loaded"

    def test_remaining_route_still_works(self):
        routing = ["writing-plans", "TDD:RED", "Implementation(GREEN)", "impl-verify"]
        result = self.mod._remaining_route(routing, "ecw:tdd")
        assert result == ["impl-verify"]

    def test_next_skill_from_routing_still_works(self):
        routing = ["writing-plans", "TDD:RED", "Implementation(GREEN)", "impl-verify"]
        result = self.mod._next_skill_from_routing(routing, "ecw:writing-plans")
        assert result == "ecw:tdd"

    def test_advance_session_state_still_works(self, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260508-test"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "auto_continue: true\n"
            "routing: [writing-plans, impl-verify]\n"
            "current_phase: plan-complete\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        self.mod._advance_session_state(str(state_file), "ecw:impl-verify")
        content = state_file.read_text()
        assert "verify-loaded" in content


class TestComputeRoutingTail:
    """compute_routing_tail derives routing tails dynamically from workflow-routes.yml.

    Critical: P2 cross-domain tail must include writing-plans (the hardcoded
    _RISK_TAILS["P2"] omitted it, causing a silent routing gap for cross-domain P2).
    """

    @pytest.fixture(autouse=True)
    def load_fn(self):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("routes_utils", HOOKS_DIR / "routes_utils.py")
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.fn = mod.compute_routing_tail

    def test_p0_single_domain_tail(self):
        """P0 single-domain tail: writing-plans → spec-challenge → TDD:RED → ... → knowledge-track."""
        tail = self.fn("P0", "ecw:requirements-elicitation")
        assert "ecw:writing-plans" in tail
        assert "ecw:spec-challenge" in tail
        assert "ecw:impl-verify" in tail
        assert "ecw:biz-impact-analysis" in tail
        assert "ecw:knowledge-track" in tail

    def test_p1_single_domain_no_spec_challenge(self):
        """P1 single-domain tail must NOT include spec-challenge."""
        tail = self.fn("P1", "ecw:requirements-elicitation")
        assert "ecw:writing-plans" in tail
        assert "ecw:spec-challenge" not in tail
        assert "ecw:impl-verify" in tail

    def test_p2_single_domain_tail(self):
        """P2 single-domain: routing[0]=writing-plans, tail is TDD:RED → impl-verify."""
        tail = self.fn("P2", "ecw:writing-plans")
        assert "TDD:RED" in tail
        assert "ecw:impl-verify" in tail
        assert "ecw:writing-plans" not in tail
        assert "ecw:biz-impact-analysis" not in tail

    def test_p2_cross_domain_tail_includes_writing_plans(self):
        """P2 cross-domain: routing[0]=domain-collab, tail MUST include writing-plans.

        This is the core bug fixed by switching from hardcoded _RISK_TAILS to dynamic
        routes.yml lookup: _RISK_TAILS["P2"] = [TDD:RED,...] was cross-domain-blind.
        """
        tail = self.fn("P2", "ecw:domain-collab")
        assert "ecw:writing-plans" in tail, (
            "P2 cross-domain tail must include writing-plans "
            "(chain: domain-collab → writing-plans → TDD:RED → impl-verify)"
        )
        assert "TDD:RED" in tail
        assert "ecw:impl-verify" in tail
        assert "ecw:biz-impact-analysis" not in tail

    def test_p3_empty_tail(self):
        """P3 single-domain: empty tail."""
        tail = self.fn("P3", "ecw:requirements-elicitation")
        assert tail == []

    def test_p3_cross_domain_empty_tail(self):
        """P3 cross-domain: routing[0]=domain-collab, tail is empty (only skill)."""
        tail = self.fn("P3", "ecw:domain-collab")
        assert tail == []

    def test_unknown_level_returns_empty(self):
        """Unknown risk_level must return [] safely."""
        assert self.fn("PX", "ecw:requirements-elicitation") == []

    def test_tdd_alias_preserved_in_tail(self):
        """TDD:RED and Implementation(GREEN) must be preserved as-is (not ecw:-prefixed)."""
        tail = self.fn("P2", "ecw:writing-plans")
        assert "TDD:RED" in tail
        assert "Implementation(GREEN)" in tail
        assert "ecw:TDD:RED" not in tail
