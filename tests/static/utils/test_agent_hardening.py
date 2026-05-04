"""Tests for agent prompt template hardening.

Validates that all agent templates include:
1. Subagent boundary guard (prevents skill invocation, sub-spawning, SKILL.md reading)
2. Anti-sycophancy rules (review agents only — no pleasantries, no sandwich feedback)
3. Source code reading limits (review agents only — explicit file count caps)
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
AGENTS_DIR = ROOT / "agents"

ALL_AGENTS = [
    "implementer.md",
    "spec-reviewer.md",
    "spec-challenge.md",
    "domain-analyst.md",
    "domain-negotiator.md",
    "impl-verifier.md",
    "biz-impact-analysis.md",
]

REVIEW_AGENTS = [
    "spec-reviewer.md",
    "domain-analyst.md",
    "domain-negotiator.md",
    "impl-verifier.md",
]


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text(encoding="utf-8")


class TestSubagentBoundaryGuard:
    """Every agent must declare subagent boundary constraints."""

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_has_boundary_section(self, agent):
        content = _read_agent(agent)
        assert re.search(r"##\s+.*[Bb]oundary", content), (
            f"{agent}: missing '## ... Boundary' section header"
        )

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_prohibits_skill_invocation(self, agent):
        content = _read_agent(agent).lower()
        assert re.search(
            r"(?:do not|must not|never)\s+(?:invoke|load|spawn|dispatch)",
            content,
        ), f"{agent}: missing prohibition on invoking skills or spawning agents"

    @pytest.mark.parametrize("agent", ALL_AGENTS)
    def test_declares_leaf_identity(self, agent):
        content = _read_agent(agent).lower()
        assert re.search(
            r"single.task\s+agent|leaf\s+node|you are a subagent",
            content,
        ), f"{agent}: missing identity declaration as single-task/leaf agent"


class TestAntiSycophancy:
    """Review agents must include anti-sycophancy guidance."""

    @pytest.mark.parametrize("agent", REVIEW_AGENTS)
    def test_has_anti_sycophancy_language(self, agent):
        content = _read_agent(agent).lower()
        assert re.search(
            r"no pleasantries"
            r"|no sandwich"
            r"|state.{0,15}(?:problems|issues|findings)\s+directly"
            r"|do not (?:soften|hedge)"
            r"|blunt",
            content,
        ), f"{agent}: missing anti-sycophancy guidance"

    def test_spec_challenge_already_has_it(self):
        """spec-challenge.md should already pass (regression guard)."""
        content = _read_agent("spec-challenge.md").lower()
        assert "no pleasantries" in content


class TestSourceCodeReadingLimits:
    """Review agents must declare explicit source file reading limits."""

    @pytest.mark.parametrize("agent", REVIEW_AGENTS)
    def test_has_numeric_file_limit(self, agent):
        content = _read_agent(agent)
        assert re.search(
            r"(?:at most|maximum|max|limit)\s*\*?\*?\s*\d+\s*\*?\*?\s*(?:source\s+)?files?",
            content, re.IGNORECASE,
        ), f"{agent}: missing explicit numeric file reading limit"

    @pytest.mark.parametrize("agent", REVIEW_AGENTS)
    def test_has_grep_preference(self, agent):
        content = _read_agent(agent)
        assert re.search(
            r"[Gg]rep.{0,40}(?:context|limited|\-A)",
            content,
        ), f"{agent}: missing Grep-with-limited-context preference guidance"

    def test_spec_challenge_already_has_limits(self):
        """spec-challenge.md should already pass (regression guard)."""
        content = _read_agent("spec-challenge.md")
        assert re.search(r"at most\s+\*?\*?10\*?\*?\s+source files", content, re.IGNORECASE)
