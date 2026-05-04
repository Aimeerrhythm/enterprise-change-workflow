"""Tests for cross-review SKILL.md cross-file consistency verification (manual tool).

Content-assertion tests verifying the cross-review skill architecture:
multi-round convergence, consistency matrix, and loop safety controls.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestCrossReviewArchitecture:
    """Verify cross-review SKILL.md has structured verification architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "cross-review" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_multi_round_structure(self):
        """Must describe multi-round verification with numbered rounds."""
        assert re.search(r'round\s*[12]', self.lower)

    def test_has_cross_file_consistency_matrix(self):
        """Must describe cross-file consistency matrix in Round 1."""
        assert "consistency" in self.lower and "matrix" in self.lower

    def test_has_convergence_condition(self):
        """Must specify convergence condition: zero findings."""
        assert re.search(r'zero\s+findings?', self.lower)

    def test_has_loop_cap(self):
        """Must specify maximum round cap (5 rounds)."""
        assert "5" in self.content and "round" in self.lower
        assert re.search(r'max\w*\s*5|5\s*round|cap', self.lower)

    def test_has_recurring_inconsistency_detection(self):
        """Must handle recurring inconsistencies to prevent infinite loops."""
        assert "recurring" in self.lower or "persist" in self.lower

    def test_has_severity_levels(self):
        """Must use severity levels for findings (must-fix)."""
        assert "must-fix" in self.lower or "severity" in self.lower

    def test_relationship_with_impl_verify(self):
        """Must clarify distinction from ecw:impl-verify."""
        assert "impl-verify" in self.lower
