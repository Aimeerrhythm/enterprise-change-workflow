"""Tests for impl-orchestration parallel execution architecture (v0.8.0).

Regression guards for the v0.8.0 rewrite from serial to parallel layer-based
execution with worktree isolation. Follows the same SKILL.md content-assertion
pattern as test_impl_verify_subagent.py and test_writing_plans_subagent.py.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestImplOrchestrationParallelArchitecture:
    """Verify impl-orchestration SKILL.md has parallel execution architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "impl-orchestration" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_worktree_isolation(self):
        """Must describe worktree isolation for parallel dispatch."""
        assert "worktree" in self.lower

    def test_has_dependency_graph_construction(self):
        """Must describe dependency graph building before dispatch."""
        assert "dependency" in self.lower and "graph" in self.lower

    def test_has_execution_layers(self):
        """Must describe layer-based execution with numbered layers."""
        assert re.search(r'layer\s*[0-9]', self.lower)

    def test_has_serial_fallback(self):
        """Must describe conditions for serial fallback."""
        assert "serial" in self.lower and "fallback" in self.lower

    def test_has_pre_flight_check(self):
        """Must describe pre-flight baseline check (compile + test)."""
        assert re.search(r'pre.?flight|pre.?check', self.lower)

    def test_has_loop_safety_controls(self):
        """Must specify global dispatch budget limit."""
        assert "50" in self.content and "budget" in self.lower

    def test_has_model_selection_tiers(self):
        """Must have model selection guidance (haiku/sonnet/opus)."""
        assert "haiku" in self.lower
        assert "sonnet" in self.lower
        assert "opus" in self.lower

    def test_merge_phase_is_sequential(self):
        """Merge phase must be sequential, not parallel."""
        assert re.search(r'sequential.{0,30}merge|merge.{0,30}sequential', self.lower)

    def test_auto_route_to_impl_verify(self):
        """After all tasks, must auto-route to impl-verify."""
        assert "impl-verify" in self.lower

    def test_single_message_parallel_dispatch(self):
        """Must require single-message dispatch for parallel Agent calls."""
        assert "single message" in self.lower or "single response" in self.lower
