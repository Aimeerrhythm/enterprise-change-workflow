"""Tests for spec-challenge SKILL.md adversarial review architecture.

Content-assertion tests verifying the spec-challenge skill:
adversarial agent dispatch, user-driven decision flow, auto-trigger,
and session split recommendation.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestSpecChallengeArchitecture:
    """Verify spec-challenge SKILL.md has adversarial review architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "spec-challenge" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_agent_dispatch(self):
        """Must describe dispatching spec-challenge agent for review."""
        assert "agent" in self.lower and "dispatch" in self.lower

    def test_model_selection_opus(self):
        """Must specify opus model for adversarial review."""
        assert "opus" in self.lower

    def test_has_user_driven_decisions(self):
        """Must describe user-driven per-item confirmation (AskUserQuestion)."""
        assert "askuserquestion" in self.lower

    def test_auto_trigger_p0(self):
        """Must auto-trigger for P0 changes."""
        assert re.search(r'p0.{0,40}(auto|trigger|after)', self.lower) or \
               re.search(r'(auto\w*|trigger|after).{0,60}p0', self.lower)

    def test_auto_trigger_p1_cross_domain(self):
        """Must auto-trigger for P1 cross-domain changes."""
        assert re.search(r'p1.{0,40}cross.?domain', self.lower)

    def test_persists_report_file(self):
        """Must persist review report to spec-challenge-report.md."""
        assert "spec-challenge-report.md" in self.content

    def test_has_session_split_recommendation(self):
        """Must recommend session split after review completion."""
        assert "session" in self.lower and "split" in self.lower or \
               "new session" in self.lower

    def test_has_timeout(self):
        """Must specify timeout for agent dispatch (300s)."""
        assert "300" in self.content
