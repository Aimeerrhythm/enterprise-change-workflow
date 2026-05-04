"""Tests for Issue #3: writing-plans subagent architecture for knowledge-heavy plans."""
import re
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _read_skill(skill_name: str) -> str:
    """Read SKILL.md for the given skill name."""
    path = ROOT / "skills" / skill_name / "SKILL.md"
    assert path.exists(), f"SKILL.md not found for skill: {skill_name}"
    return path.read_text()


class TestWritingPlansSubagentDispatch:
    """Verify writing-plans has subagent dispatch architecture for knowledge-heavy scenarios."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("writing-plans")

    def test_has_subagent_dispatch_section(self):
        """AC: writing-plans SKILL.md must contain a section describing subagent dispatch.

        The skill should have a clearly identifiable section covering how
        plan generation is delegated to subagents when knowledge files are heavy.
        """
        lower = self.content.lower()
        has_subagent = bool(re.search(r'sub-?agent', lower))
        has_dispatch = "dispatch" in lower or "delegat" in lower
        assert has_subagent and has_dispatch, \
            "writing-plans must have a section describing subagent dispatch/delegation"

    def test_coordinator_does_not_read_knowledge_files(self):
        """AC: In subagent mode, coordinator must NOT read knowledge file contents directly.

        Coordinator should only pass file paths to subagents, not ingest
        knowledge file contents itself. This keeps coordinator token usage low.
        """
        lower = self.content.lower()
        # Must mention coordinator role
        assert "coordinator" in lower, \
            "Must describe coordinator role in subagent mode"
        # Should mention passing paths (not reading content)
        has_path_passing = bool(
            re.search(r'(pass|send|provide|forward).{0,40}(path|file.?path)', lower)
            or re.search(r'path.{0,30}(pass|send|provide|forward)', lower)
            or re.search(r'coordinator.{0,80}(does not|never|not).{0,40}read', lower)
            or re.search(r'(does not|never|not).{0,40}read.{0,40}knowledge', lower)
        )
        assert has_path_passing, \
            "Coordinator must pass file paths to subagents, not read knowledge files directly"

    def test_subagent_writes_plan_directly(self):
        """AC: Subagent must write Plan files directly to .claude/plans/, not via coordinator.

        This avoids coordinator bottleneck and token overhead of relaying
        full plan content.
        """
        lower = self.content.lower()
        # Must mention subagent writing plan files
        has_direct_write = bool(
            re.search(r'sub-?agent.{0,100}(write|create|output).{0,40}plan', lower)
            or re.search(r'(write|create|output).{0,60}\.claude/plans', lower)
            or re.search(r'sub-?agent.{0,100}\.claude/plans', lower)
        )
        assert has_direct_write, \
            "Subagent must write Plan files directly to .claude/plans/"

    def test_summary_token_limit(self):
        """AC: Coordinator receives summaries with a token/word limit.

        The summary returned to coordinator must be bounded (e.g., <= 500 tokens
        or similar size constraint) to keep coordinator context manageable.
        """
        lower = self.content.lower()
        has_limit = bool(
            re.search(r'(\d+)\s*(token|word)', lower)
            or re.search(r'(brief|concise|short).{0,30}summar', lower)
            or re.search(r'summar.{0,40}(limit|cap|max|bound|brief|concise)', lower)
        )
        assert has_limit, \
            "Summary returned to coordinator must have a token/word limit"

    def test_summary_contains_task_count_and_files(self):
        """AC: Summary format must require Task count and affected file list.

        The summary that subagent returns to coordinator must include:
        - Number of Tasks in the generated plan
        - List of files involved
        """
        lower = self.content.lower()
        has_task_count = bool(
            re.search(r'(task.{0,20}count|number.{0,20}task|task.{0,20}num|\btasks?\b.{0,30}summar)', lower)
        )
        has_files = bool(
            re.search(r'(file.{0,20}(list|involved|affected|touched)|affected.{0,20}file)', lower)
        )
        assert has_task_count and has_files, \
            "Summary must include Task count and affected file list"

    def test_single_domain_stays_direct(self):
        """AC: Single domain or < 3 knowledge files must stay in direct mode.

        Subagent dispatch should only activate when there are multiple domains
        or enough knowledge files to justify the overhead. Single-domain or
        fewer than 3 knowledge files should use direct (non-subagent) planning.
        """
        lower = self.content.lower()
        has_threshold = bool(
            re.search(r'(single.{0,20}domain|1\s*domain).{0,60}direct', lower)
            or re.search(r'(fewer|less|\b[<]\s*3|under\s*3).{0,40}(knowledge|file).{0,40}direct', lower)
            or re.search(r'direct.{0,60}(single.{0,20}domain|fewer.{0,30}knowledge)', lower)
            or re.search(r'(threshold|condition|trigger).{0,80}sub-?agent', lower)
        )
        assert has_threshold, \
            "Must specify that single domain or < 3 knowledge files stays in direct mode"

    def test_model_selection(self):
        """AC: Subagent must specify model for plan generation.

        The skill must specify that subagents use opus model for plan
        generation — plan quality drives all downstream implementation.
        """
        lower = self.content.lower()
        has_opus = bool(re.search(r'model.*opus|opus.*model', lower))
        has_subagent = bool(re.search(r'sub-?agent', lower))
        assert has_opus and has_subagent, \
            "Must specify opus model for subagent plan generation"

    def test_existing_plan_structure_preserved(self):
        """Regression: Plan Document Header and Task Structure rules must still exist.

        The existing plan format rules (document header, task structure, etc.)
        must not be removed or broken by the subagent architecture addition.
        """
        # Check for plan document structure elements
        has_header = bool(
            re.search(r'(document\s+header|plan\s+header|header\s+format)', self.content, re.IGNORECASE)
            or "# Plan:" in self.content
            or "Plan:" in self.content
        )
        has_task_structure = bool(
            re.search(r'task\s+(structure|format|template)', self.content, re.IGNORECASE)
            or re.search(r'##\s*Task\s+\d', self.content)
            or re.search(r'task.{0,30}(spec|specification)', self.content, re.IGNORECASE)
        )
        assert has_header, "Plan Document Header rules must be preserved"
        assert has_task_structure, "Task Structure rules must be preserved"

    def test_downstream_handoff_preserved(self):
        """Regression: Downstream Handoff section must still exist and be complete.

        The section describing how plans are handed off to downstream skills
        (tdd, impl-orchestration, etc.) must remain intact.
        """
        lower = self.content.lower()
        has_handoff = bool(
            re.search(r'(downstream|handoff|hand-off|hand off)', lower)
        )
        assert has_handoff, \
            "Downstream Handoff section must be preserved"


class TestDomainCollabDownstreamRead:
    """Verify domain-collab specifies that downstream skills read from file."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("domain-collab")

    def test_domain_collab_downstream_read_from_file(self):
        """AC: domain-collab SKILL.md must state downstream skills read from file.

        Downstream skills (writing-plans, tdd, etc.) must read domain-collab
        output from the report file, not rely on conversation history. This
        ensures cold-start resilience and subagent compatibility.
        """
        lower = self.content.lower()
        has_downstream = bool(
            re.search(r'downstream', lower)
            or re.search(r'(writing-plans|tdd|impl-orchestration)', lower)
        )
        has_file_read = bool(
            re.search(r'(read|load|consume).{0,40}(file|report|artifact)', lower)
            or re.search(r'(file|report|artifact).{0,40}(read|load|consume)', lower)
            or re.search(r'(not|never|avoid).{0,40}(conversation|chat|dialog).{0,20}(history|context)', lower)
            or re.search(r'domain-collab-report', lower)
        )
        assert has_downstream, \
            "domain-collab must reference downstream skills"
        assert has_file_read, \
            "domain-collab must specify downstream skills read from file, not conversation history"


class TestDomainCollabArchitecture:
    """Verify domain-collab SKILL.md has multi-round collaboration architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = _read_skill("domain-collab")
        self.lower = self.content.lower()

    def test_has_three_round_structure(self):
        """Must describe 3 rounds: independent analysis, negotiation, cross-validation."""
        assert "round 1" in self.lower
        assert "round 2" in self.lower
        assert "round 3" in self.lower

    def test_has_parallel_agent_dispatch(self):
        """Must dispatch domain agents in parallel (single message)."""
        assert re.search(r'parallel|single\s+message', self.lower)

    def test_has_round2_skip_rule(self):
        """Must describe Round 2 skip rule for impact_level: none domains."""
        assert "skip" in self.lower and "round 2" in self.lower

    def test_has_knowledge_summary_output(self):
        """Must produce knowledge-summary.md for downstream reuse."""
        assert "knowledge-summary.md" in self.content

    def test_has_domain_collab_report_output(self):
        """Must produce domain-collab-report.md as full report."""
        assert "domain-collab-report.md" in self.content

    def test_has_model_selection(self):
        """Must specify model for domain analysis agents (opus)."""
        assert "opus" in self.lower
