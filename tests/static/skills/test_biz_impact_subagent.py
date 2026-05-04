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


class TestBizImpactLedgerPosition:
    """Regression guard: Ledger entry must be inserted inside the LEDGER marker block (Issue #36).

    Root cause: AI appended raw text to EOF, landing after <!-- ECW:LEDGER:END -->,
    making the entry invisible to hook parsers. SKILL.md must explicitly constrain
    the insertion point.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "biz-impact-analysis" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_ledger_instruction_references_end_marker(self):
        """Must mention ECW:LEDGER:END so AI inserts before the closing tag, not after."""
        assert "ecw:ledger:end" in self.lower or "ledger:end" in self.lower, (
            "SKILL.md Ledger section must reference '<!-- ECW:LEDGER:END -->' "
            "to prevent raw-append outside the marker block (Issue #36)."
        )

    def test_ledger_instruction_says_before(self):
        """Must use 'before' to describe insertion point relative to the END marker."""
        ledger_section = self.content[self.content.lower().find("subagent ledger"):]
        assert "before" in ledger_section.lower(), (
            "Ledger write instruction must say 'before <!-- ECW:LEDGER:END -->', "
            "not just 'append to file' (Issue #36)."
        )

    def test_ledger_recommends_append_ledger_entry(self):
        """Must recommend append_ledger_entry from marker_utils as the correct write method."""
        assert "append_ledger_entry" in self.content, (
            "SKILL.md must recommend append_ledger_entry from marker_utils.py "
            "to ensure correct marker-aware insertion (Issue #36)."
        )


class TestBizImpactReportPersisted:
    """Regression guard: biz-impact-report.md must be written to session-data (Issue #37).

    Root cause: SKILL.md step 6 only said 'output' (to conversation), with no
    instruction to write the report to disk. Phase 3 calibration depends on the file.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "biz-impact-analysis" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_skill_instructs_writing_report_file(self):
        """Must contain an explicit instruction to write biz-impact-report.md."""
        assert "biz-impact-report.md" in self.content, (
            "SKILL.md must instruct writing biz-impact-report.md to session-data "
            "(Phase 3 calibration depends on this file — Issue #37)."
        )

    def test_report_write_references_session_data(self):
        """Write instruction must target the session-data directory."""
        idx = self.content.find("biz-impact-report.md")
        surrounding = self.content[max(0, idx - 200): idx + 200].lower()
        assert "session-data" in surrounding, (
            "The biz-impact-report.md write instruction must reference the "
            "session-data/{workflow-id}/ path (Issue #37)."
        )

    def test_report_write_precedes_output(self):
        """Write-to-disk must appear before 'output' in step 6 (write then display)."""
        write_idx = self.content.find("biz-impact-report.md")
        output_idx = self.content.find("output the agent", write_idx)
        assert write_idx != -1 and output_idx != -1 and write_idx < output_idx, (
            "biz-impact-report.md write instruction must precede the 'output' "
            "directive in step 6 so the file is persisted before displaying (Issue #37)."
        )
