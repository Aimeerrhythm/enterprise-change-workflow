"""Tests for biz-impact-analysis Knowledge Auto-Backfill architecture (v0.7+).

Regression guards for the auto-backfill feature added to biz-impact-analysis
and its Phase 3 calibration integration. Follows the SKILL.md content-assertion
pattern used by other skill architecture tests.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestBizImpactAutoBackfill:
    """Verify biz-impact-analysis SKILL.md has auto-backfill architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "biz-impact-analysis" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_auto_backfill_section(self):
        """Must have a Knowledge Auto-Backfill section."""
        assert "auto-backfill" in self.lower or "auto backfill" in self.lower

    def test_backfill_is_conservative(self):
        """Backfill strategy must be append-only / conservative."""
        assert re.search(r'append.?only|never\s+(modify|delete)', self.lower)

    def test_backfill_targets_cross_domain_calls(self):
        """Must target cross-domain-calls.md specifically."""
        assert "cross-domain-calls.md" in self.content

    def test_has_phase3_calibration_integration(self):
        """Must describe auto-chaining to Phase 3 for P0/P1."""
        assert "phase 3" in self.lower

    def test_has_coordinator_preprocessing(self):
        """Must describe coordinator preprocessing before agent dispatch."""
        assert "git diff" in self.lower

    def test_has_path_mappings_reference(self):
        """Must reference ecw-path-mappings for domain identification."""
        assert "path-mappings" in self.lower or "path_mappings" in self.lower
