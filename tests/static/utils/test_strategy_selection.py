"""Tests for Issue #1: Multi-dimensional Implementation Strategy Selection."""
import re

import pytest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILL_DIR = ROOT / "skills" / "risk-classifier"


def _load_workflow_routes():
    """Load workflow-routes.yml — single source of truth for impl_strategy."""
    path = SKILL_DIR / "workflow-routes.yml"
    assert path.exists(), "workflow-routes.yml not found"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestStrategySelectionRules:
    """Verify risk-classifier has multi-dimensional strategy rules in workflow-routes.yml."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (SKILL_DIR / "SKILL.md").read_text()
        self.routes = _load_workflow_routes()
        self.strategies = self.routes.get("impl_strategy", [])

    def _conditions(self):
        return [s.get("condition", "").lower() for s in self.strategies]

    def test_has_file_count_dimension(self):
        """Strategy must consider file count, not just task count."""
        assert any("file" in c for c in self._conditions()), \
            "workflow-routes.yml impl_strategy must reference file count"

    def test_has_domain_count_dimension(self):
        """Strategy must consider number of domains modified."""
        assert any("domain" in c for c in self._conditions()), \
            "workflow-routes.yml impl_strategy must reference domain count"

    def test_low_task_high_file_routes_to_orchestration(self):
        """<=3 tasks but >=6 files should use impl-orchestration."""
        found = any(
            "3" in c and "file" in c and
            s.get("strategy") == "impl-orchestration"
            for c, s in zip(self._conditions(), self.strategies)
        )
        assert found, "Must have rule: Tasks<=3 + files>=6 -> impl-orchestration"

    def test_file_threshold_is_exactly_6(self):
        """The files threshold for impl-orchestration must be exactly 6, not 5.

        Changing files>=6 to files>=5 would silently break the boundary:
        5-file changes would incorrectly route to impl-orchestration.
        This test parses the numeric threshold directly from workflow-routes.yml.
        """
        import re
        orch_conditions = [
            c for c, s in zip(self._conditions(), self.strategies)
            if s.get("strategy") == "impl-orchestration" and "file" in c
        ]
        assert orch_conditions, "No impl-orchestration rule with file condition found"

        for cond in orch_conditions:
            # Extract the numeric threshold after "files" (e.g. "files >= 6" or "files>=6")
            match = re.search(r'files\s*>=\s*(\d+)', cond)
            if match:
                threshold = int(match.group(1))
                assert threshold == 6, (
                    f"impl-orchestration file threshold must be exactly 6, got {threshold}. "
                    f"Condition: '{cond}'"
                )

    def test_direct_file_threshold_is_exactly_5(self):
        """The files threshold for direct strategy must be exactly <=5, not <=6.

        Symmetric guard: if someone changes files<=5 to files<=6, the boundary
        between direct and impl-orchestration collapses.
        """
        import re
        direct_conditions = [
            c for c, s in zip(self._conditions(), self.strategies)
            if s.get("strategy") == "direct" and "file" in c and "task" in c
        ]
        assert direct_conditions, "No direct strategy rule with file+task condition found"

        for cond in direct_conditions:
            match = re.search(r'files\s*<=\s*(\d+)', cond)
            if match:
                threshold = int(match.group(1))
                assert threshold == 5, (
                    f"direct strategy file threshold must be exactly 5, got {threshold}. "
                    f"Condition: '{cond}'"
                )

    def test_low_task_low_file_stays_direct(self):
        """<=3 tasks with <=5 files should stay direct."""
        found = any(
            "3" in c and "5" in c and s.get("strategy") == "direct"
            for c, s in zip(self._conditions(), self.strategies)
        )
        assert found, "Must have rule: Tasks<=3 + files<=5 -> direct"

    def test_three_dimension_description(self):
        """Strategy section in SKILL.md must describe the three-dimension evaluation."""
        lower = self.content.lower()
        assert "task" in lower and "file" in lower and "domain" in lower, \
            "Strategy description must mention all three dimensions"

    def test_original_rules_preserved(self):
        """Existing rules for Tasks 4-8 and P3 must still exist in workflow-routes.yml."""
        conditions = self._conditions()
        strategies = [s.get("strategy") for s in self.strategies]
        assert any("4-8" in c for c in conditions), "Tasks 4-8 rule must be preserved"
        assert "direct" in strategies, "P3/direct strategy must be preserved"

    def _get_strategy_section(self):
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
        lower = self.content.lower()
        assert re.search(r'iron law', lower) and re.search(
            r'no production code.{0,30}failing test|failing test.{0,30}production code', lower
        ), "Iron Law (no production code without a failing test first) must be present"


class TestTddRiskAwareEnforcement:
    """Verify TDD SKILL.md has risk-aware enforcement architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "tdd" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_risk_enforcement_table(self):
        """Must have enforcement table covering P0/P1/P2/P3/Bug/Emergency."""
        assert "p0" in self.lower and "p1" in self.lower
        assert "p2" in self.lower and "p3" in self.lower
        assert "bug" in self.lower and "emergency" in self.lower

    def test_has_p2_simplified_mode(self):
        """Must describe P2 simplified mode with concrete constraints."""
        assert "simplified" in self.lower
        assert re.search(r'max\s*5|5\s*cycle', self.lower)

    def test_has_ecw_yml_override(self):
        """Must describe ecw.yml tdd.enabled override."""
        assert "tdd.enabled" in self.content

    def test_has_skip_confirmation_protocol(self):
        """Must describe skip confirmation via AskUserQuestion."""
        assert "skip" in self.lower and "askuserquestion" in self.lower

    def test_has_cycle_subagent_model_selection(self):
        """Must specify model for TDD cycle subagents (sonnet)."""
        assert "sonnet" in self.lower
