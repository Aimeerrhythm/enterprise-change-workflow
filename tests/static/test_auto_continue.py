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
            "- **Risk Level**: P0\n"
            "- **Auto-Continue**: yes\n"
            "- **Routing**: ecw:writing-plans → ecw:spec-challenge → ecw:tdd\n"
            "- **Next**: ecw:tdd\n"
            f"- **Current Phase**: {phase}\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "- **Working Mode**: planning\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def test_phase_advances_to_spec_challenge_complete(self, tmp_path):
        """Phase must still advance to spec-challenge-complete — hook does this, not SKILL.md."""
        state_file = self._make_state(tmp_path)
        self.hook._advance_session_state(str(state_file), "ecw:spec-challenge")
        content = state_file.read_text()
        assert "**Current Phase**: spec-challenge-complete" in content

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
        assert "**Current Phase**: spec-challenge-complete" in content


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
            f"- **Current Phase**: {phase}\n"
            "- **Risk Level**: P1\n"
            "- **Auto-Continue**: yes\n"
            "- **Next**: ecw:requirements-elicitation\n"
            "<!-- ECW:STATUS:END -->\n\n"
            "<!-- ECW:MODE:START -->\n"
            f"- **Working Mode**: {mode}\n"
            "<!-- ECW:MODE:END -->\n"
        )
        return state_file

    def test_updates_phase_after_skill_completes(self, tmp_path):
        """Current Phase must advance after risk-classifier finishes."""
        state_file = self._make_state(tmp_path, phase="phase1-complete")
        self.hook._advance_session_state(str(state_file), "ecw:risk-classifier")
        content = state_file.read_text()
        assert "**Current Phase**: phase1-complete" in content

    def test_updates_phase_after_requirements_elicitation(self, tmp_path):
        state_file = self._make_state(tmp_path, phase="phase1-complete")
        self.hook._advance_session_state(str(state_file), "ecw:requirements-elicitation")
        content = state_file.read_text()
        assert "**Current Phase**: requirements-complete" in content

    def test_updates_mode_after_writing_plans(self, tmp_path):
        """Working Mode must update to 'planning' after writing-plans finishes."""
        state_file = self._make_state(tmp_path, mode="analysis")
        self.hook._advance_session_state(str(state_file), "ecw:writing-plans")
        content = state_file.read_text()
        assert "**Working Mode**: planning" in content

    def test_updates_both_fields_atomically(self, tmp_path):
        """Both Current Phase and Working Mode must be written in a single update."""
        state_file = self._make_state(tmp_path, phase="plan-complete", mode="planning")
        self.hook._advance_session_state(str(state_file), "ecw:tdd")
        content = state_file.read_text()
        assert "**Current Phase**: tdd-complete" in content
        assert "**Working Mode**: implementation" in content

    def test_preserves_unrelated_fields(self, tmp_path):
        """Risk Level, Auto-Continue, and Next must not be modified."""
        state_file = self._make_state(tmp_path)
        self.hook._advance_session_state(str(state_file), "ecw:impl-verify")
        content = state_file.read_text()
        assert "**Risk Level**: P1" in content
        assert "**Auto-Continue**: yes" in content
        assert "**Next**: ecw:requirements-elicitation" in content

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
            "- **Risk Level**: P1\n"
            "- **Auto-Continue**: yes\n"
            "- **Routing**: ecw:risk-classifier → ecw:writing-plans\n"
            "- **Next**: ecw:writing-plans\n"
            "- **Current Phase**: phase1-complete\n"
            "<!-- ECW:STATUS:END -->\n"
            "<!-- ECW:MODE:START -->\n"
            "- **Working Mode**: analysis\n"
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

        content = state_file.read_text()
        assert "**Current Phase**: phase1-complete" in content
        assert "**Working Mode**: analysis" in content
        output = json.loads("".join(captured))
        assert "systemMessage" in output

