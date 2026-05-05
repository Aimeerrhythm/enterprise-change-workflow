"""Tests for Issue #2: impl-verify subagent architecture."""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestImplVerifySubagentArchitecture:
    """Verify impl-verify has subagent dispatch architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "impl-verify" / "SKILL.md").read_text()

    def test_has_subagent_architecture_section(self):
        """Must have a section describing subagent dispatch architecture."""
        assert "Subagent" in self.content, \
            "Must have subagent architecture description"

    def test_parallel_dispatch_required(self):
        """Rounds must be dispatched in parallel."""
        lower = self.content.lower()
        assert "parallel" in lower, "Must mention parallel dispatch"

    def test_structured_findings_format(self):
        """Subagents must return structured findings (YAML format)."""
        lower = self.content.lower()
        assert "findings" in lower and ("yaml" in lower or "structured" in lower), \
            "Must specify structured findings format"

    def test_round_headers_indicate_subagent(self):
        """Round headers should indicate subagent execution."""
        # At least Round 1 should indicate subagent
        assert "[Subagent]" in self.content or "subagent" in self.content.lower(), \
            "Round headers should indicate subagent execution mode"

    def test_coordinator_only_holds_lightweight_data(self):
        """Coordinator should only hold file list + aggregated findings."""
        lower = self.content.lower()
        assert "coordinator" in lower, "Must describe coordinator role"

    def test_incremental_reconvergence(self):
        """Re-verification should be incremental (only affected rounds)."""
        lower = self.content.lower()
        assert "incremental" in lower or "affected round" in lower or "only dispatch" in lower, \
            "Re-verification must be incremental"

    def test_model_selection_for_verification(self):
        """Should specify model for verification subagents."""
        lower = self.content.lower()
        assert "sonnet" in lower or "model" in lower, \
            "Should specify model selection for verification agents"

    def test_existing_rounds_preserved(self):
        """All 4 rounds must still exist (regression)."""
        assert "Round 1" in self.content
        assert "Round 2" in self.content
        assert "Round 3" in self.content
        assert "Round 4" in self.content

    def test_convergence_condition_preserved(self):
        """Convergence condition must still exist (regression)."""
        assert "zero must-fix" in self.content.lower() or "zero must-fix findings" in self.content.lower(), \
            "Convergence condition must be preserved"

    def test_diff_strategy_preserved(self):
        """Diff Read Strategy section must still exist (regression)."""
        assert "Diff Read Strategy" in self.content, \
            "Diff Read Strategy must be preserved"


class TestImplVerifyPerRoundPersistence:
    """Verify impl-verify has per-round persistence architecture (Issue #22).

    The coordinator must persist each round's findings to an independent file
    immediately upon receiving the subagent result, BEFORE attempting the
    final merge into impl-verify-findings.md. This prevents data loss when
    the merge step fails or context is compacted mid-verification.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "impl-verify" / "SKILL.md").read_text()

    def test_per_round_file_naming_convention(self):
        """SKILL.md must define per-round file naming (impl-verify-round{N}.md)."""
        assert "impl-verify-round" in self.content, (
            "Must define per-round file naming convention "
            "(e.g., impl-verify-round1.md, impl-verify-round2.md)"
        )

    def test_immediate_persistence_directive(self):
        """Coordinator must persist each round result immediately upon receipt."""
        lower = self.content.lower()
        assert ("immediately" in lower or "as soon as" in lower) and "round" in lower, (
            "Must instruct coordinator to persist round results immediately "
            "upon receipt, not defer to final merge"
        )

    def test_merge_after_per_round_persistence(self):
        """Final merge into impl-verify-findings.md comes AFTER per-round persistence."""
        content = self.content
        round_file_pos = content.find("impl-verify-round")
        findings_file_pos = content.find("impl-verify-findings.md")
        assert round_file_pos != -1 and findings_file_pos != -1, (
            "Both per-round files and findings.md must be mentioned"
        )
        assert round_file_pos < findings_file_pos, (
            "Per-round persistence must be described before final merge "
            "to impl-verify-findings.md"
        )

    def test_degraded_round_still_persists_completed(self):
        """Even when some rounds fail, completed round files must be preserved."""
        lower = self.content.lower()
        has_partial = (
            "partial" in lower
            or "completed round" in lower
            or "already persisted" in lower
            or "surviving round" in lower
        )
        assert has_partial, (
            "Must describe that completed round files survive even when "
            "other rounds fail or the merge step errors"
        )

    def test_output_templates_has_per_round_format(self):
        """output-templates.md must define per-round file format."""
        templates = (ROOT / "skills" / "impl-verify" / "output-templates.md").read_text()
        assert "impl-verify-round" in templates, (
            "output-templates.md must document per-round file format"
        )
