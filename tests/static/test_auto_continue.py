"""Tests for auto-continue mechanism across ECW skill transitions.

Verifies that risk-classifier and related skills have explicit instructions
to prevent redundant confirmation prompts between skill transitions.
Finding-02 / Finding-04 from WMS P0 integration test.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestRiskClassifierAutoContinue:
    """Verify risk-classifier has auto-continue instructions after user confirms."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "risk-classifier" / "SKILL.md").read_text()
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
