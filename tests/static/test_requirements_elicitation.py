"""Tests for requirements-elicitation SKILL.md architecture.

Content-assertion tests verifying the requirements-elicitation skill:
systematic questioning, synthesis analysis, checkpoint persistence,
and termination controls.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestRequirementsElicitationArchitecture:
    """Verify requirements-elicitation SKILL.md has systematic questioning architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "requirements-elicitation" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_questioning_dimension_checklist(self):
        """Must have a questioning dimension checklist section."""
        assert "dimension" in self.lower and "checklist" in self.lower

    def test_questions_per_round_limit(self):
        """Must specify 3-5 questions per round."""
        assert re.search(r'3.?5\s*question', self.lower)

    def test_has_synthesis_analysis_subagent(self):
        """Must describe synthesis analysis using Agent tool."""
        assert "synthesis" in self.lower and "agent" in self.lower

    def test_synthesis_model_selection(self):
        """Must specify model for synthesis agent (sonnet)."""
        assert "sonnet" in self.lower

    def test_has_requirements_summary_checkpoint(self):
        """Must persist requirements-summary.md as checkpoint."""
        assert "requirements-summary.md" in self.content

    def test_has_termination_limits(self):
        """Must have termination limits by risk level (P0: 15 rounds)."""
        assert "15" in self.content and "termination" in self.lower

    def test_has_phase2_handoff(self):
        """Must describe handoff to risk-classifier Phase 2 after confirmation."""
        assert "phase 2" in self.lower
