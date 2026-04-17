"""Tests for Issue #1: Multi-dimensional Implementation Strategy Selection."""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestStrategySelectionRules:
    """Verify risk-classifier has multi-dimensional strategy rules."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "risk-classifier" / "SKILL.md").read_text()

    def test_has_file_count_dimension(self):
        """Strategy must consider file count, not just task count."""
        # The table should mention "files" as a dimension
        assert "files" in self.content.lower() or "file" in self.content.lower()
        # Specifically check for the threshold
        section = self._get_strategy_section()
        assert "files" in section.lower(), "Strategy section must reference file count"

    def test_has_domain_count_dimension(self):
        """Strategy must consider number of domains modified."""
        section = self._get_strategy_section()
        assert "domain" in section.lower(), "Strategy section must reference domain count"

    def test_low_task_high_file_routes_to_orchestration(self):
        """<=3 tasks but >=6 files should use impl-orchestration."""
        section = self._get_strategy_section()
        # Check that there's a rule combining low task count with high file count -> orchestration
        assert "impl-orchestration" in section, "Must have orchestration route"
        # The key pattern: tasks <= 3 AND files >= 6 -> orchestration
        lines = section.split('\n')
        found = False
        for line in lines:
            lower = line.lower()
            if ('3' in line or '<= 3' in line) and ('file' in lower) and ('orchestration' in lower or 'subagent' in lower):
                found = True
                break
        assert found, "Must have rule: Tasks<=3 + files>=6 -> orchestration"

    def test_low_task_low_file_stays_direct(self):
        """<=3 tasks with <=5 files should stay direct."""
        section = self._get_strategy_section()
        lines = section.split('\n')
        found = False
        for line in lines:
            lower = line.lower()
            if ('3' in line or '<= 3' in line) and ('5' in line or '<= 5' in line) and ('direct' in lower):
                found = True
                break
        assert found, "Must have rule: Tasks<=3 + files<=5 -> direct"

    def test_three_dimension_description(self):
        """Strategy must describe the three-dimension evaluation method."""
        section = self._get_strategy_section()
        lower = section.lower()
        # Should mention scanning plan for file counts
        assert "task" in lower and "file" in lower and "domain" in lower, \
            "Strategy description must mention all three dimensions"

    def test_original_rules_preserved(self):
        """Existing rules for Tasks 4-8 and Tasks > 8 must still exist."""
        section = self._get_strategy_section()
        assert "4-8" in section, "Tasks 4-8 rule must be preserved"
        assert "P3" in section, "P3 direct rule must be preserved"

    def _get_strategy_section(self):
        """Extract the Implementation Strategy Selection section."""
        start = self.content.find("### Implementation Strategy Selection")
        if start == -1:
            pytest.fail("Cannot find Implementation Strategy Selection section")
        end = self.content.find("###", start + 10)
        if end == -1:
            end = len(self.content)
        return self.content[start:end]


class TestTddSubagentDelegation:
    """Verify TDD skill has subagent delegation path."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "tdd" / "SKILL.md").read_text()

    def test_has_subagent_section(self):
        """TDD must have a section about subagent delegation."""
        lower = self.content.lower()
        assert "subagent" in lower, "TDD must mention subagent delegation"

    def test_references_impl_orchestration(self):
        """TDD subagent section should reference impl-orchestration."""
        assert "impl-orchestration" in self.content, \
            "TDD must explain relationship with impl-orchestration"

    def test_file_threshold_for_delegation(self):
        """TDD should specify file count threshold for subagent delegation."""
        lower = self.content.lower()
        # Should mention a file count threshold (6 files)
        assert "6" in self.content and "file" in lower, \
            "TDD must specify file threshold for subagent delegation"

    def test_coordinator_does_not_read_files(self):
        """When delegated, coordinator should not read implementation files."""
        lower = self.content.lower()
        assert "coordinator" in lower, "Must describe coordinator behavior"
        # Should mention that coordinator only receives summaries
        assert "summary" in lower or "summaries" in lower, \
            "Must state coordinator only receives summaries"

    def test_iron_law_still_exists(self):
        """Iron Law must be preserved (regression)."""
        assert "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST" in self.content
