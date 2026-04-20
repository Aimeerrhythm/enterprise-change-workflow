"""Tests for auto-continue mechanism across ECW skill transitions.

Verifies that all skills have explicit auto-continue instructions
to prevent redundant confirmation prompts between skill transitions.
"""
import re

import pytest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
TEMPLATES_DIR = ROOT / "templates"


def _read_skill(name):
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def _load_ecw_yml():
    return yaml.safe_load((TEMPLATES_DIR / "ecw.yml").read_text(encoding="utf-8"))


class TestRiskClassifierAutoContinue:
    """Verify risk-classifier has auto-continue instructions after user confirms."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("risk-classifier")
        self.lower = self.content.lower()

    def test_has_immediate_invoke_instruction(self):
        """After user selects 'Proceed', must IMMEDIATELY invoke next skill."""
        assert re.search(
            r'immediately\s+(invoke|trigger|call|execute|proceed)', self.lower
        ), "Must have IMMEDIATELY invoke instruction after user confirms Proceed"

    def test_prohibits_confirmation_text(self):
        """Must explicitly prohibit outputting confirmation text between skills."""
        has_prohibition = bool(
            re.search(r'(do not|never|禁止|不要).{0,60}(是否继续|confirmation|confirm|ready|准备)', self.lower)
            or re.search(r'(do not|never|禁止|不要).{0,60}(ask|wait|prompt).{0,40}(user|confirm)', self.lower)
            or re.search(r'(skip|no).{0,30}(re-?confirm|second.?confirm)', self.lower)
        )
        assert has_prohibition, \
            "Must explicitly prohibit confirmation text between skill transitions"

    def test_has_auto_continue_field(self):
        """session-state.md must include Auto-Continue field."""
        assert re.search(r'auto.?continue', self.lower), \
            "session-state.md template must include Auto-Continue field"

    def test_phase2_auto_proceed_instruction(self):
        """Phase 2 completion must have auto-proceed instruction to next skill."""
        has_phase2_auto = bool(
            re.search(r'phase\s*2.{0,200}immediately', self.lower)
            or re.search(r'immediately.{0,200}phase\s*2', self.lower)
            or re.search(r'phase\s*2.{0,200}auto.?proceed', self.lower)
            or re.search(r'phase\s*2.{0,200}(do not|never).{0,40}(ask|wait|confirm)', self.lower)
        )
        assert has_phase2_auto, \
            "Phase 2 completion must have auto-proceed instruction"


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

    def test_risk_classifier_references_auto_confirm(self):
        content = _read_skill("risk-classifier").lower()
        assert re.search(r'auto_confirm|auto_flow\.auto_confirm', content), (
            "risk-classifier/SKILL.md must reference auto_confirm config"
        )


class TestDomainCollabAutoContinue:
    """Verify domain-collab has auto-continue after Round 3."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("domain-collab")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "domain-collab/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_immediately_invokes_phase2(self):
        assert re.search(r'immediately.{0,80}phase\s*2', self.lower), (
            "domain-collab must immediately invoke Phase 2 for P0/P1"
        )


class TestRequirementsElicitationAutoContinue:
    """Verify requirements-elicitation has auto-continue after summary confirmation."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("requirements-elicitation")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "requirements-elicitation/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_immediately_invokes_phase2(self):
        assert re.search(
            r'immediately.{0,80}phase\s*2', self.lower
        ) or re.search(
            r'immediately.{0,80}writing-plans', self.lower
        ), "requirements-elicitation must immediately invoke Phase 2 or writing-plans"


class TestSpecChallengeAutoContinue:
    """Verify spec-challenge has auto-continue after user chooses 'Continue'."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("spec-challenge")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "spec-challenge/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_immediately_invokes_tdd_or_impl(self):
        has_invoke = bool(
            re.search(r'immediately invoke.*the next skill', self.lower)
            and (
                re.search(r'invoke.*ecw:tdd', self.lower)
                or re.search(r'invoke.*impl-orchestration', self.lower)
            )
        )
        assert has_invoke, "spec-challenge must immediately invoke ecw:tdd or impl-orchestration"


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

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "tdd/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_immediately_invokes_impl_verify(self):
        assert re.search(r'immediately.{0,80}impl-verify', self.lower), (
            "tdd must immediately invoke impl-verify after all tasks GREEN"
        )


class TestWritingPlansAutoContinue:
    """Verify writing-plans auto-routes implementation without unnecessary AskUserQuestion."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("writing-plans")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "writing-plans/SKILL.md missing CRITICAL Auto-Continue Rule block"
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
    """Verify impl-verify has auto-continue to biz-impact-analysis in SKILL.md."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("impl-verify")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "impl-verify/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_p0_p1_immediately_invokes_biz_impact(self):
        assert re.search(r'immediately.{0,80}biz-impact', self.lower), (
            "impl-verify must immediately invoke biz-impact-analysis for P0/P1"
        )


class TestBizImpactAutoContinue:
    """Verify biz-impact-analysis has standardized auto-continue to Phase 3."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("biz-impact-analysis")
        self.lower = self.content.lower()

    def test_has_auto_continue_block(self):
        assert re.search(r'critical.*auto-continue', self.lower), (
            "biz-impact-analysis/SKILL.md missing CRITICAL Auto-Continue Rule block"
        )

    def test_immediately_invokes_phase3(self):
        assert re.search(
            r'immediately.{0,80}phase\s*3', self.lower
        ) or re.search(
            r'immediately.{0,80}risk-classifier.*phase.?3', self.lower
        ), "biz-impact-analysis must immediately invoke Phase 3 for P0/P1"
