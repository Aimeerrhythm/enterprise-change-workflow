"""Tests for systematic-debugging SKILL.md root cause analysis architecture.

Content-assertion tests verifying the systematic-debugging skill:
Iron Law, four phases, domain cross-reference, and architecture questioning.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestSystematicDebuggingArchitecture:
    """Verify systematic-debugging SKILL.md has structured debugging architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "systematic-debugging" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_iron_law(self):
        """Must state the Iron Law: no fixes without root cause investigation."""
        assert "iron law" in self.lower
        assert "root cause" in self.lower

    def test_has_four_phases(self):
        """Must describe 4 phases of debugging."""
        assert "phase 1" in self.lower and "phase 4" in self.lower

    def test_has_domain_cross_reference(self):
        """Must describe domain knowledge cross-reference using path-mappings."""
        assert "path-mappings" in self.lower or "ecw-path-mappings" in self.lower

    def test_has_phase1_checkpoint(self):
        """Must persist Phase 1 evidence — checkpoint format in investigation-steps.md."""
        assert re.search(r'checkpoint', self.lower) and re.search(
            r'investigation.?steps\.md|evidence', self.lower
        ), "Must reference Phase 1 checkpoint (directly or via investigation-steps.md)"

    def test_has_scientific_method(self):
        """Phase 3 must describe hypothesis testing (scientific method)."""
        assert "hypothesis" in self.lower

    def test_has_architecture_questioning_threshold(self):
        """Must trigger architecture questioning after 3+ failed fixes."""
        assert re.search(r'3\+?\s*(fix|fail|attempt)|question.{0,40}arch|arch.{0,40}question', self.lower), \
            "Must describe architecture questioning threshold after 3+ failures"

    def test_has_tdd_integration(self):
        """Phase 4 must reference ecw:tdd for test-first fix."""
        assert "tdd" in self.lower
