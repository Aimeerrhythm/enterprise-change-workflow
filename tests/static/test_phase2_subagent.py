"""Tests for Issue #4: Phase 2 risk-classifier subagent architecture."""
import re
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _read_skill(skill_name: str) -> str:
    """Read SKILL.md for the given skill name."""
    path = ROOT / "skills" / skill_name / "SKILL.md"
    assert path.exists(), f"SKILL.md not found for skill: {skill_name}"
    return path.read_text()


def _get_phase2_section(content: str) -> str:
    """Extract the Phase 2 section from risk-classifier SKILL.md.

    Looks for a heading containing 'Phase 2' and extracts until the next
    same-level or higher heading.
    """
    # Try to find Phase 2 section with various heading patterns
    match = re.search(
        r'(^#{1,4}\s+.*Phase\s*2.*$)',
        content,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        pytest.fail("Cannot find Phase 2 section heading in risk-classifier SKILL.md")

    start = match.start()
    heading_level = len(re.match(r'(#+)', match.group(1)).group(1))

    # Find the next heading at same or higher level
    rest = content[match.end():]
    next_heading = re.search(
        rf'^#{{1,{heading_level}}}\s',
        rest,
        re.MULTILINE,
    )
    if next_heading:
        end = match.end() + next_heading.start()
    else:
        end = len(content)

    return content[start:end]


class TestPhase2SubagentArchitecture:
    """Verify risk-classifier Phase 2 uses subagent dispatch."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("risk-classifier")
        self.phase2 = _get_phase2_section(self.content)

    def test_phase2_uses_subagent(self):
        """AC: Phase 2 must describe subagent dispatch for dependency analysis.

        The Phase 2 section should explicitly describe using subagents to
        perform the heavy dependency graph queries, rather than doing
        everything in the coordinator.
        """
        lower = self.phase2.lower()
        has_subagent = bool(re.search(r'sub-?agent', lower))
        assert has_subagent, \
            "Phase 2 must describe subagent dispatch"

    def test_phase2_who_executes_updated(self):
        """AC: Quick Reference table 'Who executes' must no longer say 'no agent dispatch'.

        The previous design had Phase 2 as coordinator-only. With subagent
        architecture, the quick reference should reflect that agents are now used.
        """
        lower = self.content.lower()
        # Find the quick reference / summary table area
        # It should NOT contain "no agent dispatch" for Phase 2
        # Look for table rows mentioning Phase 2
        phase2_table_pattern = re.search(
            r'phase\s*2.*no\s+agent\s+dispatch',
            lower,
        )
        assert phase2_table_pattern is None, \
            "Quick Reference must not say 'no agent dispatch' for Phase 2"

    def test_phase2_subagent_returns_yaml(self):
        """AC: Subagent must return structured YAML — schema in phase2-subagent-schema.md.

        The schema file must exist and contain risk_level and affected_domains.
        """
        lower = self.phase2.lower()
        # Phase 2 section references the schema file
        has_schema_ref = bool(
            re.search(r'phase2-subagent-schema', lower)
            or re.search(r'subagent.{0,40}schema', lower)
            or re.search(r'yaml', lower)
        )
        assert has_schema_ref, \
            "Phase 2 section must reference subagent schema or YAML structure"

        # Verify the schema file itself exists and has required fields
        schema_path = (
            Path(__file__).resolve().parent.parent.parent
            / "skills" / "risk-classifier" / "phase2-subagent-schema.md"
        )
        if schema_path.exists():
            schema = schema_path.read_text().lower()
            assert re.search(r'risk.?level', schema), \
                "phase2-subagent-schema.md must include risk_level field"
            assert re.search(r'affected.?domain', schema), \
                "phase2-subagent-schema.md must include affected_domains field"
        else:
            pytest.fail("phase2-subagent-schema.md not found")

    def test_phase2_knowledge_summary_priority(self):
        """AC: When knowledge-summary.md exists, subagent should prioritize using it.

        If a previously generated knowledge-summary.md is available, the
        subagent should use it as a more efficient source rather than reading
        all raw knowledge files from scratch.
        """
        lower = self.phase2.lower()
        has_knowledge_summary = bool(
            re.search(r'knowledge.?summary', lower)
        )
        has_priority = bool(
            re.search(r'(priorit|prefer|first|exist|available|if).{0,40}knowledge.?summary', lower)
            or re.search(r'knowledge.?summary.{0,40}(priorit|prefer|first|exist|available)', lower)
        )
        assert has_knowledge_summary, \
            "Phase 2 must reference knowledge-summary.md"
        assert has_priority, \
            "Phase 2 must indicate knowledge-summary.md is used when available"

    def test_phase2_all_five_queries_present(self):
        """AC: All 5 dependency graph query types must be preserved.

        Phase 2 must retain the ability to query all five dependency types:
        cross-domain-calls, mq-topology, shared-resources, external-systems,
        and e2e-paths.
        """
        lower = self.phase2.lower()

        queries = {
            "cross-domain-calls": r'cross.?domain.?call',
            "mq-topology": r'mq.?topolog',
            "shared-resources": r'shared.?resource',
            "external-systems": r'external.?system',
            "e2e-paths": r'e2e.?path',
        }

        missing = []
        for name, pattern in queries.items():
            if not re.search(pattern, lower):
                missing.append(name)

        assert not missing, \
            f"Phase 2 must include all 5 dependency queries. Missing: {missing}"

    def test_phase2_step_labels_indicate_subagent(self):
        """AC: Phase 2 must explicitly describe subagent dispatch for Steps 1-4.

        The design uses a single subagent dispatch for steps 1-4; labeling is
        in the narrative text, not necessarily [Subagent] markers.
        """
        lower = self.phase2.lower()
        has_subagent_for_steps = bool(
            re.search(r'sub-?agent.{0,200}step', lower)
            or re.search(r'step.{0,200}sub-?agent', lower)
            or re.search(r'dispatch.{0,100}sub-?agent', lower)
        )
        assert has_subagent_for_steps, \
            "Phase 2 section must describe subagent dispatch for dependency analysis steps"

    def test_phase2_step5_not_subagent(self):
        """AC: Step 5 must NOT be labeled as [Subagent].

        Step 5 (the final synthesis/decision step) should execute in the
        coordinator, not as a subagent. It aggregates subagent results.
        """
        # Find the Step 5 heading line (#### Step 5 or #### [Subagent] Step 5)
        step5_heading = re.search(
            r'^#{1,5}\s+.*Step\s*5',
            self.phase2,
            re.MULTILINE | re.IGNORECASE,
        )
        if step5_heading:
            heading_text = step5_heading.group(0)
            has_subagent_label = bool(re.search(r'\[Sub-?agent\]', heading_text, re.IGNORECASE))
            assert not has_subagent_label, \
                "Step 5 heading must NOT be labeled [Subagent] - it runs in coordinator"
        else:
            # If no explicit Step 5 heading, check that there's a coordinator step
            lower = self.phase2.lower()
            has_coordinator_step = bool(
                re.search(r'coordinator.{0,60}(step\s*5|compare|synthes|aggregat|final)', lower)
                or re.search(r'(step\s*5|compare).{0,60}coordinator', lower)
            )
            assert has_coordinator_step, \
                "Must have at least one coordinator-executed step (Step 5)"

    def test_phase2_model_selection(self):
        """AC: Subagent must use sonnet model for Phase 2 analysis.

        The Phase 2 subagents should use sonnet model for cost/quality balance.
        """
        lower = self.phase2.lower()
        has_sonnet = "sonnet" in lower
        has_subagent = bool(re.search(r'sub-?agent', lower))
        assert has_sonnet and has_subagent, \
            "Phase 2 must specify sonnet model for subagents"

    def test_phase2_checkpoint_preserved(self):
        """Regression: Phase 2 must still write session-data/phase2-assessment.md checkpoint.

        After Phase 2 completes, the assessment must be persisted to the
        checkpoint file for downstream cold-start recovery.
        """
        lower = self.phase2.lower()
        has_checkpoint = bool(
            re.search(r'phase2-assessment', lower)
            or re.search(r'session.?data.{0,20}phase2', lower)
        )
        assert has_checkpoint, \
            "Phase 2 must write checkpoint to session-data/phase2-assessment.md"

    def test_phase2_upgrade_downgrade_logic_preserved(self):
        """Regression: Upgrade/downgrade logic must still exist in Phase 2.

        The risk level adjustment logic (upgrade from P2->P1 or downgrade
        from P1->P2 based on analysis) must be preserved.
        """
        lower = self.phase2.lower()
        has_upgrade = bool(re.search(r'upgrade', lower))
        has_downgrade = bool(re.search(r'downgrade', lower))
        assert has_upgrade or has_downgrade, \
            "Phase 2 must preserve upgrade/downgrade logic"
        # Ideally both exist
        assert has_upgrade and has_downgrade, \
            "Phase 2 should describe both upgrade and downgrade paths"
