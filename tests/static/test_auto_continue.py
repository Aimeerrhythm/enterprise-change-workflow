"""Tests for auto-continue mechanism across ECW skill transitions.

Verifies that all skills have explicit auto-continue instructions
to prevent redundant confirmation prompts between skill transitions.
"""
import importlib.util
import json
import re

import pytest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
TEMPLATES_DIR = ROOT / "templates"
HOOKS_DIR = ROOT / "hooks"


def _read_skill(name):
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def _load_ecw_yml():
    return yaml.safe_load((TEMPLATES_DIR / "ecw.yml").read_text(encoding="utf-8"))


class TestRiskClassifierAutoContinue:
    """Verify risk-classifier has downstream handoff instructions after user confirms."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("risk-classifier")
        self.lower = self.content.lower()

    def test_has_downstream_handoff(self):
        """Phase 2 must have a Downstream Handoff block."""
        assert "downstream handoff" in self.lower, \
            "risk-classifier must have Downstream Handoff block"

    def test_prohibits_confirmation_text(self):
        """Phase 2 Downstream Handoff must reference session-state.md for routing."""
        assert re.search(r'session.?state', self.lower), \
            "risk-classifier must reference session-state.md in Downstream Handoff"

    def test_has_auto_continue_field(self):
        """Downstream Handoff in Phase 2 must reference session-state.md (which holds Auto-Continue)."""
        assert re.search(r'session.?state', self.lower), \
            "risk-classifier must reference session-state.md"

    def test_phase2_handoff_to_writing_plans(self):
        """Phase 2 Downstream Handoff must route to ecw:writing-plans."""
        assert re.search(r'phase\s*2.{0,300}writing.?plans', self.lower) or \
               re.search(r'writing.?plans.{0,300}phase\s*2', self.lower), \
            "Phase 2 Downstream Handoff must reference ecw:writing-plans"


class TestAutoConfirmConfig:
    """Verify ecw.yml has auto_flow.auto_confirm and risk-classifier references it."""

    def test_ecw_yml_has_auto_flow_section(self):
        cfg = _load_ecw_yml()
        assert "auto_flow" in cfg, "ecw.yml missing 'auto_flow' section"

    def test_auto_flow_has_auto_confirm(self):
        cfg = _load_ecw_yml()
        af = cfg["auto_flow"]
        assert "auto_confirm" in af, "auto_flow missing 'auto_confirm' key"
        assert isinstance(af["auto_confirm"], bool), "auto_confirm must be bool"

    def test_risk_classifier_references_auto_continue(self):
        content = _read_skill("risk-classifier").lower()
        assert re.search(r'session.?state', content), (
            "risk-classifier/SKILL.md must reference session-state.md"
        )


class TestDomainCollabAutoContinue:
    """Verify domain-collab has downstream handoff after Round 3."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("domain-collab")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "domain-collab/SKILL.md missing Downstream Handoff block"
        )

    def test_immediately_invokes_phase2(self):
        assert re.search(r'immediately.{0,80}phase\s*2', self.lower), (
            "domain-collab must immediately invoke Phase 2 for P0/P1"
        )


class TestRequirementsElicitationAutoContinue:
    """Verify requirements-elicitation has downstream handoff after summary confirmation."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("requirements-elicitation")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "requirements-elicitation/SKILL.md missing Downstream Handoff block"
        )

    def test_invokes_phase2_or_writing_plans(self):
        assert re.search(
            r'phase\s*2', self.lower
        ) and re.search(
            r'writing.?plans', self.lower
        ), "requirements-elicitation Downstream Handoff must reference Phase 2 and writing-plans"


class TestSpecChallengeAutoContinue:
    """Verify spec-challenge has downstream handoff to implementation."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("spec-challenge")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "spec-challenge/SKILL.md missing Downstream Handoff block"
        )

    def test_routes_to_tdd_or_impl_orchestration(self):
        has_route = bool(
            re.search(r'ecw:tdd', self.lower)
            and re.search(r'impl-orchestration', self.lower)
        )
        assert has_route, "spec-challenge Downstream Handoff must reference ecw:tdd and impl-orchestration"


class TestTddDownstreamHandoff:
    """Verify tdd has downstream handoff to impl-verify."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("tdd")
        self.lower = self.content.lower()

    def test_has_downstream_handoff(self):
        assert "downstream handoff" in self.lower, (
            "tdd/SKILL.md missing 'Downstream Handoff' section"
        )

    def test_has_handoff_block_with_impl_verify(self):
        assert re.search(r'downstream handoff.{0,300}impl.?verify', self.lower), (
            "tdd/SKILL.md Downstream Handoff must reference impl-verify"
        )

    def test_invokes_impl_verify(self):
        assert re.search(r'impl.?verify', self.lower), (
            "tdd must invoke impl-verify after all tasks GREEN"
        )


class TestWritingPlansAutoContinue:
    """Verify writing-plans auto-routes implementation without unnecessary AskUserQuestion."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("writing-plans")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "writing-plans/SKILL.md missing Downstream Handoff block"
        )

    def test_no_unnecessary_ask(self):
        start = self.content.find("## Downstream Handoff")
        end = self.content.find("## Common Rationalizations")
        if start != -1 and end != -1:
            section = self.content[start:end].lower()
            assert "offer execution choice via askuserquestion" not in section, (
                "writing-plans Downstream Handoff should not offer execution choice "
                "via AskUserQuestion — strategy is auto-decided"
            )


class TestImplVerifyAutoContinue:
    """Verify impl-verify has downstream handoff to biz-impact-analysis in SKILL.md."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("impl-verify")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "impl-verify/SKILL.md missing Downstream Handoff block"
        )

    def test_p0_p1_routes_to_biz_impact(self):
        assert re.search(r'p0.{0,200}biz.?impact|biz.?impact.{0,200}p0', self.lower), (
            "impl-verify Downstream Handoff must route P0/P1 to ecw:biz-impact-analysis"
        )


class TestBizImpactAutoContinue:
    """Verify biz-impact-analysis has downstream handoff to Phase 3."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("biz-impact-analysis")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "biz-impact-analysis/SKILL.md missing Downstream Handoff block"
        )

    def test_routes_to_phase3(self):
        assert re.search(
            r'phase\s*3', self.lower
        ) or re.search(
            r'risk.?classifier.{0,60}phase', self.lower
        ), "biz-impact-analysis Downstream Handoff must reference Phase 3 calibration"


class TestSpecChallengeHookBehavior:
    """spec-challenge must update phase/mode but NOT inject systemMessage (Issue #29).

    Fatal Flaw handling requires mandatory per-flaw AskUserQuestion confirmation.
    Injecting "do not ask for confirmation" overrides SKILL.md and bypasses that flow.
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.hook = mod

    def _make_state(self, tmp_path, phase="plan-complete"):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-ff01"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P0\n"
            "auto_continue: true\n"
            "routing: [ecw:writing-plans, ecw:spec-challenge, ecw:tdd]\n"
            "next: ecw:tdd\n"
            f"current_phase: {phase}\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "working_mode: planning\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def _parse_state(self, state_file):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", HOOKS_DIR / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)
        return mu.parse_status(state_file.read_text())

    def test_phase_advances_to_spec_challenge_complete(self, tmp_path):
        """Phase must still advance to spec-challenge-complete — hook does this, not SKILL.md."""
        state_file = self._make_state(tmp_path)
        self.hook._advance_session_state(str(state_file), "ecw:spec-challenge")
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "spec-challenge-complete"

    def test_no_system_message_injected(self, tmp_path, monkeypatch):
        """main() must NOT output systemMessage for spec-challenge — would bypass AskUserQuestion."""
        import io

        state_file = self._make_state(tmp_path)

        payload = json.dumps({
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:spec-challenge"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())

        self.hook.main()

        output = json.loads("".join(captured))
        assert "systemMessage" not in output, (
            "auto-continue must not inject systemMessage for spec-challenge — "
            "doing so overrides mandatory Fatal Flaw confirmation (Issue #29)"
        )

    def test_phase_still_updated_when_no_system_message(self, tmp_path, monkeypatch):
        """Phase update and systemMessage skip must both happen in the same main() run."""
        import io

        state_file = self._make_state(tmp_path, phase="plan-complete")

        payload = json.dumps({
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:spec-challenge"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: None,
            "flush": lambda self: None,
        })())

        self.hook.main()

        content = state_file.read_text()
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "spec-challenge-complete"


class TestRemainingRouteUnit:
    """Unit tests for _remaining_route in auto-continue.py.

    Critical edge cases:
    - skill not found in routing → must return [], not the full chain
    - empty routing → return []
    - skill at last position → return []
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.fn = mod._remaining_route

    def test_normal_middle_skill(self):
        routing = "ecw:risk-classifier → ecw:requirements-elicitation → ecw:writing-plans → ecw:tdd"
        result = self.fn(routing, "ecw:requirements-elicitation")
        assert result == ["ecw:writing-plans", "ecw:tdd"]

    def test_skill_at_last_position(self):
        routing = "ecw:risk-classifier → ecw:writing-plans → ecw:tdd"
        result = self.fn(routing, "ecw:tdd")
        assert result == []

    def test_skill_not_in_routing_returns_empty(self):
        """Must return [] — NOT the full chain. Returning full chain would re-run whole workflow."""
        routing = "ecw:risk-classifier → ecw:writing-plans → ecw:tdd"
        result = self.fn(routing, "ecw:domain-collab")
        assert result == [], (
            "_remaining_route must return [] when skill not found, "
            "not the full chain (which would re-run the entire workflow)"
        )

    def test_empty_routing(self):
        assert self.fn("", "ecw:risk-classifier") == []
        assert self.fn(None, "ecw:risk-classifier") == []

    def test_skill_at_first_position(self):
        routing = "ecw:risk-classifier → ecw:requirements-elicitation → ecw:writing-plans"
        result = self.fn(routing, "ecw:risk-classifier")
        assert result == ["ecw:requirements-elicitation", "ecw:writing-plans"]

    def test_yaml_list_input(self):
        """Accepts YAML list (new format) in addition to string."""
        routing = ["ecw:risk-classifier", "ecw:writing-plans", "ecw:impl-verify"]
        result = self.fn(routing, "ecw:writing-plans")
        assert result == ["ecw:impl-verify"]

    def test_tdd_alias_tdd_red_in_routing(self):
        """When routing has TDD:RED (alias for ecw:tdd), remaining starts after TDD:RED."""
        routing = ["ecw:writing-plans", "TDD:RED", "Implementation(GREEN)", "ecw:impl-verify"]
        result = self.fn(routing, "ecw:tdd")
        # TDD:RED and Implementation(GREEN) are both aliases; last-match is Implementation(GREEN)
        assert result == ["ecw:impl-verify"]

    def test_no_substring_false_positive(self):
        """'ecw:tdd' must NOT match a hypothetical 'ecw:tdd-extended' step."""
        routing = ["ecw:tdd-extended", "ecw:impl-verify"]
        result = self.fn(routing, "ecw:tdd")
        assert result == [], "Substring match must not fire for unrelated skill names"


class TestSystematicDebuggingAutoContinue:
    """systematic-debugging must have a Downstream Handoff block routing to impl-verify."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("systematic-debugging")
        self.lower = self.content.lower()

    def test_has_downstream_handoff_block(self):
        assert "downstream handoff" in self.lower, (
            "systematic-debugging/SKILL.md missing Downstream Handoff block — "
            "bug fix workflow will truncate and never reach impl-verify"
        )

    def test_routes_to_impl_verify(self):
        assert "impl-verify" in self.lower or "ecw:impl-verify" in self.lower, (
            "systematic-debugging Downstream Handoff must route to ecw:impl-verify"
        )


class TestDownstreamHandoffStatusMarker:
    """Downstream Handoff in all active skills must require STATUS marker when updating Next.

    Background: auto-continue hook reads session-state.md via read_marker_section('STATUS').
    If the model updates Next outside the STATUS block, the hook silently fails and
    the auto-continue chain breaks. Each skill's Downstream Handoff must explicitly
    require the update to be inside ECW:STATUS:START/END.
    """

    SKILLS_TO_CHECK = [
        "tdd",
        "writing-plans",
        "domain-collab",
        "requirements-elicitation",
        "impl-verify",
        "biz-impact-analysis",
    ]

    @pytest.mark.parametrize("skill_name", SKILLS_TO_CHECK)
    def test_downstream_handoff_requires_status_marker(self, skill_name):
        content = _read_skill(skill_name)
        lower = content.lower()

        # Find the section-level "## Downstream Handoff" header (not inline references)
        handoff_start = -1
        for m in re.finditer(r'##\s+downstream handoff', lower):
            handoff_start = m.start()
            break

        # Fall back to blockquote-style "> **Downstream Handoff**"
        if handoff_start == -1:
            m = re.search(r'>\s+\*\*downstream handoff\*\*', lower)
            if m:
                handoff_start = m.start()

        assert handoff_start != -1, f"{skill_name}/SKILL.md missing Downstream Handoff block"

        handoff_section = lower[handoff_start:handoff_start + 2000]
        has_marker_ref = any(phrase in handoff_section for phrase in [
            "ecw:status:start",
            "status:start",
            "marker block",
            "within the",
            "status marker",
        ])
        assert has_marker_ref, (
            f"{skill_name}/SKILL.md Downstream Handoff says 'update Next field' "
            f"but does not require the update to be inside the ECW:STATUS:START/END "
            f"marker block — auto-continue hook will silently fail if model writes "
            f"Next outside the marker"
        )


class TestAdvanceSessionState:
    """auto-continue hook must atomically update Current Phase and Working Mode
    in session-state.md when a skill completes (Issue #21).

    Validates _advance_session_state writes both STATUS and MODE in a single
    read-modify-write, so the fields stay consistent regardless of interruptions.
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.hook = mod

    def _make_state(self, tmp_path, phase="phase1-complete", mode="analysis"):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260429-ab12"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "# ECW Session State\n\n"
            "<!-- ECW:STATUS:START -->\n"
            f"current_phase: {phase}\n"
            "risk_level: P1\n"
            "auto_continue: true\n"
            "next: ecw:requirements-elicitation\n"
            "<!-- ECW:STATUS:END -->\n\n"
            "<!-- ECW:MODE:START -->\n"
            f"working_mode: {mode}\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def _parse_state(self, state_file):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", HOOKS_DIR / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)
        return mu.parse_status(state_file.read_text())

    def _parse_mode(self, state_file):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", HOOKS_DIR / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)
        result = mu.parse_yaml_section(state_file.read_text(), "MODE")
        return result.get("working_mode") if result else None

    def test_updates_phase_after_skill_completes(self, tmp_path):
        """Current Phase must advance after risk-classifier finishes."""
        state_file = self._make_state(tmp_path, phase="phase1-complete")
        self.hook._advance_session_state(str(state_file), "ecw:risk-classifier")
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "phase1-complete"

    def test_updates_phase_after_requirements_elicitation(self, tmp_path):
        state_file = self._make_state(tmp_path, phase="phase1-complete")
        self.hook._advance_session_state(str(state_file), "ecw:requirements-elicitation")
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "requirements-complete"

    def test_updates_mode_after_writing_plans(self, tmp_path):
        """Working Mode must update to 'planning' after writing-plans finishes."""
        state_file = self._make_state(tmp_path, mode="analysis")
        self.hook._advance_session_state(str(state_file), "ecw:writing-plans")
        assert self._parse_mode(state_file) == "planning"

    def test_updates_both_fields_atomically(self, tmp_path):
        """Both Current Phase and Working Mode must be written in a single update."""
        state_file = self._make_state(tmp_path, phase="plan-complete", mode="planning")
        self.hook._advance_session_state(str(state_file), "ecw:tdd")
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "tdd-complete"
        assert self._parse_mode(state_file) == "implementation"

    def test_preserves_unrelated_fields(self, tmp_path):
        """Risk Level, Auto-Continue, and Next must not be modified."""
        state_file = self._make_state(tmp_path)
        self.hook._advance_session_state(str(state_file), "ecw:impl-verify")
        fields = self._parse_state(state_file)
        assert fields["risk_level"] == "P1"
        assert fields["auto_continue"] is True
        assert fields["next"] == "ecw:requirements-elicitation"

    def test_unknown_skill_is_noop(self, tmp_path):
        """Skills not in the mapping table must not modify the file."""
        state_file = self._make_state(tmp_path, phase="phase1-complete", mode="analysis")
        original = state_file.read_text()
        self.hook._advance_session_state(str(state_file), "ecw:unknown-skill")
        assert state_file.read_text() == original

    def test_missing_file_does_not_raise(self, tmp_path):
        """A non-existent path must be silently swallowed — hook must never block."""
        self.hook._advance_session_state(
            str(tmp_path / "nonexistent" / "session-state.md"),
            "ecw:tdd",
        )  # must not raise

    def test_all_skills_have_phase_mapping(self):
        """Every key in _SKILL_COMPLETED_PHASE must be a valid ecw: skill name."""
        for skill in self.hook._SKILL_COMPLETED_PHASE:
            assert skill.startswith("ecw:"), (
                f"Phase mapping key '{skill}' does not start with 'ecw:'"
            )

    def test_all_skills_have_mode_mapping(self):
        """Every key in _SKILL_MODE must map to a known working mode."""
        known_modes = {"analysis", "planning", "implementation", "verification"}
        for skill, mode in self.hook._SKILL_MODE.items():
            assert mode in known_modes, (
                f"Skill '{skill}' has unknown mode '{mode}'"
            )

    def test_main_triggers_advance_when_auto_continue_active(self, tmp_path, monkeypatch):
        """Full main() path: _advance_session_state must be called when Auto-Continue: yes."""
        import io

        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260429-cd34"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        state_file.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "auto_continue: true\n"
            "routing: [ecw:risk-classifier, ecw:writing-plans]\n"
            "next: ecw:writing-plans\n"
            "current_phase: phase1-complete\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "working_mode: analysis\n"
            "<!-- ECW:MODE:END -->\n"
        )

        payload = json.dumps({
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:risk-classifier"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())

        self.hook.main()

        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "phase1-complete"
        assert self._parse_mode(state_file) == "analysis"
        output = json.loads("".join(captured))
        assert "systemMessage" in output


class TestNextSkillFromRouting:
    """Unit tests for _next_skill_from_routing — resolves next ECW skill from Routing chain.

    Covers:
    - Standard ecw:-prefix steps (most skills)
    - TDD:RED alias → ecw:tdd
    - Implementation(GREEN) / Fix(GREEN) as tdd-internal steps (not new skill invocations)
    - Phase markers (Phase 2, Phase 3) are non-skill steps → skipped
    - Skill not found → None
    - Last skill in chain → None
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.fn = mod._next_skill_from_routing

    def test_standard_ecw_prefix_chain(self):
        """Normal ecw: prefix chain: next after requirements-elicitation is writing-plans."""
        routing = "ecw:requirements-elicitation → Phase 2 → ecw:writing-plans → ecw:spec-challenge"
        assert self.fn(routing, "ecw:requirements-elicitation") == "ecw:writing-plans"

    def test_tdd_red_alias_maps_to_ecw_tdd(self):
        """TDD:RED in Routing should resolve to ecw:tdd as the next skill after spec-challenge."""
        routing = "ecw:writing-plans → ecw:spec-challenge → TDD:RED → Implementation(GREEN) → ecw:impl-verify"
        assert self.fn(routing, "ecw:spec-challenge") == "ecw:tdd"

    def test_implementation_green_is_internal_to_tdd(self):
        """After tdd (matched via TDD:RED and Implementation(GREEN)), next skill is impl-verify."""
        routing = "ecw:spec-challenge → TDD:RED → Implementation(GREEN) → ecw:impl-verify → ecw:biz-impact-analysis"
        assert self.fn(routing, "ecw:tdd") == "ecw:impl-verify"

    def test_fix_green_is_internal_to_tdd(self):
        """Fix(GREEN) is a tdd phase in bug fix routes; after tdd, next is impl-verify."""
        routing = "ecw:systematic-debugging → TDD:RED → Fix(GREEN) → ecw:impl-verify"
        assert self.fn(routing, "ecw:tdd") == "ecw:impl-verify"

    def test_systematic_debugging_next_is_tdd(self):
        """After systematic-debugging in bug fix flow, next skill is ecw:tdd (starts at TDD:RED)."""
        routing = "ecw:systematic-debugging → TDD:RED → Fix(GREEN) → ecw:impl-verify"
        assert self.fn(routing, "ecw:systematic-debugging") == "ecw:tdd"

    def test_phase_markers_skipped(self):
        """Phase 2 and Phase 3 are non-skill markers; next ECW skill is found past them."""
        routing = "ecw:requirements-elicitation → Phase 2 → ecw:writing-plans → ecw:impl-verify → Phase 3"
        assert self.fn(routing, "ecw:impl-verify") is None  # Phase 3 is not a skill

    def test_biz_impact_followed_by_knowledge_track(self):
        """After biz-impact-analysis, ecw:knowledge-track is the next skill."""
        routing = "ecw:impl-verify → ecw:biz-impact-analysis → ecw:knowledge-track → Phase 3"
        assert self.fn(routing, "ecw:biz-impact-analysis") == "ecw:knowledge-track"

    def test_skill_not_found_returns_none(self):
        """If current skill not in routing, return None (not the full chain)."""
        routing = "ecw:writing-plans → ecw:spec-challenge → ecw:tdd"
        assert self.fn(routing, "ecw:domain-collab") is None

    def test_last_skill_in_chain_returns_none(self):
        """If current skill is last ECW skill, return None."""
        routing = "ecw:impl-verify → ecw:biz-impact-analysis → Phase 3"
        assert self.fn(routing, "ecw:biz-impact-analysis") is None

    def test_empty_routing_returns_none(self):
        assert self.fn("", "ecw:tdd") is None
        assert self.fn(None, "ecw:tdd") is None


class TestPreToolUseHandler:
    """PreToolUse hook must update Current Phase (in-progress), Next, and Working Mode
    at skill entry, without injecting a systemMessage.

    Issue #26: these fields were left to LLM soft-constraints; now the hook handles them.
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.hook = mod

    def _make_state(self, tmp_path, routing, next_val="ecw:spec-challenge", phase="plan-complete"):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-cc01"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        # routing is a list or string; convert to YAML list
        if isinstance(routing, str):
            routing_list = [s.strip() for s in routing.split("→")]
        else:
            routing_list = routing
        import yaml as _yaml
        routing_yaml = _yaml.dump(routing_list, default_flow_style=True).strip()
        state_file.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P0\n"
            "auto_continue: true\n"
            f"routing: {routing_yaml}\n"
            f"next: {next_val}\n"
            f"current_phase: {phase}\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "working_mode: planning\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def _parse_state(self, state_file):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", HOOKS_DIR / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)
        return mu.parse_status(state_file.read_text())

    def _parse_mode(self, state_file):
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", HOOKS_DIR / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)
        result = mu.parse_yaml_section(state_file.read_text(), "MODE")
        return result.get("working_mode") if result else None

    def _run_pre_tool_use(self, tmp_path, monkeypatch, skill):
        import io
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-cc01"
        payload = json.dumps({
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": skill},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())
        self.hook.main()
        return json.loads("".join(captured))

    def test_pre_tool_use_updates_current_phase_to_in_progress(self, tmp_path, monkeypatch):
        """At skill entry, Current Phase must show the skill is in-progress (e.g. 'spec-challenge')."""
        routing = "ecw:writing-plans → ecw:spec-challenge → TDD:RED → ecw:impl-verify"
        self._make_state(tmp_path, routing, next_val="ecw:spec-challenge", phase="plan-complete")
        self._run_pre_tool_use(tmp_path, monkeypatch, "ecw:spec-challenge")
        state_file = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-cc01" / "session-state.md"
        fields = self._parse_state(state_file)
        assert fields["current_phase"] == "spec-challenge", (
            "PreToolUse must update Current Phase to the in-progress skill name"
        )
        assert fields["current_phase"] != "plan-complete"

    def test_pre_tool_use_updates_next_to_downstream_skill(self, tmp_path, monkeypatch):
        """At skill entry, Next must be updated to the skill AFTER the current one in Routing.

        Issue #26 root cause: Next pointed to the current skill throughout execution.
        After this fix, when spec-challenge starts, Next = ecw:tdd (not ecw:spec-challenge).
        """
        routing = "ecw:writing-plans → ecw:spec-challenge → TDD:RED → Implementation(GREEN) → ecw:impl-verify"
        self._make_state(tmp_path, routing, next_val="ecw:spec-challenge", phase="plan-complete")
        self._run_pre_tool_use(tmp_path, monkeypatch, "ecw:spec-challenge")
        state_file = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-cc01" / "session-state.md"
        fields = self._parse_state(state_file)
        assert fields["next"] == "ecw:tdd", (
            "When spec-challenge starts, Next must be updated to ecw:tdd (via TDD:RED alias)"
        )

    def test_pre_tool_use_updates_working_mode(self, tmp_path, monkeypatch):
        """At skill entry, Working Mode must switch to the skill's mode."""
        routing = "ecw:writing-plans → ecw:tdd → ecw:impl-verify"
        self._make_state(tmp_path, routing, next_val="ecw:tdd", phase="plan-complete")
        self._run_pre_tool_use(tmp_path, monkeypatch, "ecw:tdd")
        state_file = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-cc01" / "session-state.md"
        assert self._parse_mode(state_file) == "implementation"

    def test_pre_tool_use_returns_continue_not_system_message(self, tmp_path, monkeypatch):
        """PreToolUse must return {result: continue}, never inject a systemMessage."""
        routing = "ecw:spec-challenge → TDD:RED → ecw:impl-verify"
        self._make_state(tmp_path, routing)
        output = self._run_pre_tool_use(tmp_path, monkeypatch, "ecw:spec-challenge")
        assert output.get("result") == "continue", (
            "PreToolUse must return continue — it must never block skill execution"
        )
        assert "systemMessage" not in output

    def test_pre_tool_use_does_not_update_next_when_last_skill(self, tmp_path, monkeypatch):
        """When the skill is last in the chain, Next must not be overwritten to None."""
        routing = "ecw:impl-verify → ecw:biz-impact-analysis → Phase 3"
        state_file = self._make_state(tmp_path, routing, next_val="ecw:biz-impact-analysis")
        self._run_pre_tool_use(tmp_path, monkeypatch, "ecw:biz-impact-analysis")
        fields = self._parse_state(state_file)
        # biz-impact-analysis is last skill; _next_skill_from_routing returns None → Next unchanged
        assert fields["next"] == "ecw:biz-impact-analysis"


class TestKnowledgeTrackInjection:
    """After biz-impact-analysis PostToolUse, knowledge-track must be triggered when:
    1. ecw.yml has paths.knowledge_root set (ECW-ready session)
    2. Risk level is P0 or P1
    3. knowledge-track is NOT already in the remaining Routing chain (old sessions)

    Issue #26: knowledge-track was skipped in P0/P1 workflows because it wasn't in
    the Routing chain and biz-impact-analysis SKILL.md prompt was the only trigger.
    """

    @pytest.fixture(autouse=True)
    def load_hook(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.hook = mod

    def _make_state(self, tmp_path, risk_level="P0", routing=None):
        if routing is None:
            routing = "ecw:impl-verify → ecw:biz-impact-analysis → Phase 3"
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-dd01"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "session-state.md"
        if isinstance(routing, str):
            routing_list = [s.strip() for s in routing.split("→")]
        else:
            routing_list = routing
        import yaml as _yaml
        routing_yaml = _yaml.dump(routing_list, default_flow_style=True).strip()
        state_file.write_text(
            "<!-- ECW:STATUS:START -->\n"
            f"risk_level: {risk_level}\n"
            "auto_continue: true\n"
            f"routing: {routing_yaml}\n"
            "next: ecw:biz-impact-analysis\n"
            "current_phase: verify-complete\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "working_mode: verification\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def _make_ecw_yml(self, tmp_path, with_knowledge_root=True):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True, exist_ok=True)
        content = "paths:\n"
        if with_knowledge_root:
            content += "  knowledge_root: .claude/knowledge\n"
        (ecw_dir / "ecw.yml").write_text(content)

    def _run_post_tool_use(self, tmp_path, monkeypatch):
        import io
        payload = json.dumps({
            "hook_event_name": "PostToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:biz-impact-analysis"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())
        self.hook.main()
        return json.loads("".join(captured))

    def test_injects_knowledge_track_for_p0_with_knowledge_root(self, tmp_path, monkeypatch):
        """After biz-impact-analysis (P0, knowledge_root exists), must inject knowledge-track."""
        self._make_state(tmp_path, risk_level="P0")
        self._make_ecw_yml(tmp_path, with_knowledge_root=True)
        output = self._run_post_tool_use(tmp_path, monkeypatch)
        assert "systemMessage" in output
        assert "knowledge-track" in output["systemMessage"].lower() or \
               "ecw:knowledge-track" in output["systemMessage"], (
            "systemMessage must trigger ecw:knowledge-track after biz-impact-analysis "
            "when P0/P1 and knowledge_root is set"
        )

    def test_injects_knowledge_track_for_p1_with_knowledge_root(self, tmp_path, monkeypatch):
        """After biz-impact-analysis (P1, knowledge_root exists), must inject knowledge-track."""
        self._make_state(tmp_path, risk_level="P1")
        self._make_ecw_yml(tmp_path, with_knowledge_root=True)
        output = self._run_post_tool_use(tmp_path, monkeypatch)
        assert "systemMessage" in output
        assert "knowledge-track" in output["systemMessage"].lower() or \
               "ecw:knowledge-track" in output["systemMessage"]

    def test_no_knowledge_track_for_p2(self, tmp_path, monkeypatch):
        """P2 does not require knowledge-track; must not inject it."""
        self._make_state(tmp_path, risk_level="P2",
                         routing="ecw:impl-verify → ecw:biz-impact-analysis → Phase 3")
        self._make_ecw_yml(tmp_path, with_knowledge_root=True)
        output = self._run_post_tool_use(tmp_path, monkeypatch)
        msg = output.get("systemMessage", "")
        assert "knowledge-track" not in msg.lower()

    def test_no_knowledge_track_without_knowledge_root(self, tmp_path, monkeypatch):
        """When ecw.yml has no knowledge_root, must not inject knowledge-track."""
        self._make_state(tmp_path, risk_level="P0")
        self._make_ecw_yml(tmp_path, with_knowledge_root=False)
        output = self._run_post_tool_use(tmp_path, monkeypatch)
        msg = output.get("systemMessage", "")
        assert "knowledge-track" not in msg.lower()

    def test_knowledge_track_in_routing_not_duplicated(self, tmp_path, monkeypatch):
        """When knowledge-track is already in Routing, use normal route injection (no duplicate)."""
        routing = "ecw:impl-verify → ecw:biz-impact-analysis → ecw:knowledge-track → Phase 3"
        self._make_state(tmp_path, risk_level="P0", routing=routing)
        self._make_ecw_yml(tmp_path, with_knowledge_root=True)
        output = self._run_post_tool_use(tmp_path, monkeypatch)
        # Normal systemMessage includes remaining route (ecw:knowledge-track → Phase 3)
        # Fallback injection must NOT fire; normal routing message handles it
        assert "systemMessage" in output
        msg = output["systemMessage"]
        # Should appear exactly once (from the remaining route), not from fallback injection
        assert msg.count("knowledge-track") >= 1

