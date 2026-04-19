"""
Tests for agent template hardening:
- Subagent Boundary Guard (all 7 agents)
- Anti-Sycophancy Review Tone rules (4 review agents)
- Source Code Reading Limits (4 review agents)
"""
import re
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent.parent / "agents"

ALL_AGENTS = [
    "implementer.md",
    "spec-reviewer.md",
    "domain-analyst.md",
    "domain-negotiator.md",
    "impl-verifier.md",
    "spec-challenge.md",
    "biz-impact-analysis.md",
]

REVIEW_AGENTS = [
    "spec-reviewer.md",
    "domain-analyst.md",
    "domain-negotiator.md",
    "impl-verifier.md",
]

BOUNDARY_SECTION = "## Subagent Boundary"
BOUNDARY_RULES = [
    "Do not invoke any `ecw:` skills",
    "Do not spawn additional subagents",
    "Do not load or read SKILL.md files",
    "BLOCKED or NEEDS_CONTEXT",
]

REVIEW_TONE_SECTION = "## Review Tone"
REVIEW_TONE_RULES = [
    "No pleasantries",
    "without hedging",
]

READING_LIMITS_SECTION = "## Source Code Reading Limits"


def read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text()


# ── Subagent Boundary: present in all 7 agents ──────────────────────────────

class TestSubagentBoundaryPresent:
    def test_implementer_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("implementer.md")

    def test_spec_reviewer_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("spec-reviewer.md")

    def test_domain_analyst_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("domain-analyst.md")

    def test_domain_negotiator_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("domain-negotiator.md")

    def test_impl_verifier_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("impl-verifier.md")

    def test_spec_challenge_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("spec-challenge.md")

    def test_biz_impact_analysis_has_boundary_section(self):
        assert BOUNDARY_SECTION in read_agent("biz-impact-analysis.md")


# ── Subagent Boundary: content rules ────────────────────────────────────────

class TestSubagentBoundaryContent:
    def test_boundary_forbids_ecw_skills(self):
        for agent in ALL_AGENTS:
            content = read_agent(agent)
            assert "Do not invoke any `ecw:` skills" in content, (
                f"{agent} missing ecw: skills prohibition"
            )

    def test_boundary_forbids_spawning_subagents(self):
        for agent in ALL_AGENTS:
            content = read_agent(agent)
            assert "Do not spawn additional subagents" in content, (
                f"{agent} missing subagent spawning prohibition"
            )

    def test_boundary_forbids_reading_skill_files(self):
        for agent in ALL_AGENTS:
            content = read_agent(agent)
            assert "Do not load or read SKILL.md files" in content, (
                f"{agent} missing SKILL.md reading prohibition"
            )

    def test_boundary_references_blocked_needs_context(self):
        for agent in ALL_AGENTS:
            content = read_agent(agent)
            assert "BLOCKED or NEEDS_CONTEXT" in content, (
                f"{agent} missing BLOCKED or NEEDS_CONTEXT escalation path"
            )


# ── Subagent Boundary: insertion order ──────────────────────────────────────

class TestSubagentBoundaryPosition:
    def test_implementer_boundary_before_report_format(self):
        content = read_agent("implementer.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Report Format")

    def test_spec_reviewer_boundary_before_report_format(self):
        content = read_agent("spec-reviewer.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Report Format")

    def test_domain_analyst_boundary_before_output_constraints(self):
        content = read_agent("domain-analyst.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Output Constraints")

    def test_domain_negotiator_boundary_before_output_constraints(self):
        content = read_agent("domain-negotiator.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Output Constraints")

    def test_impl_verifier_boundary_before_constraints(self):
        content = read_agent("impl-verifier.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Constraints")

    def test_spec_challenge_boundary_before_important_constraints(self):
        content = read_agent("spec-challenge.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Important Constraints")

    def test_biz_impact_analysis_boundary_before_important_constraints(self):
        content = read_agent("biz-impact-analysis.md")
        assert content.index(BOUNDARY_SECTION) < content.index("## Important Constraints")


# ── Review Tone: present in 4 review agents only ────────────────────────────

class TestReviewTonePresent:
    def test_spec_reviewer_has_review_tone(self):
        assert REVIEW_TONE_SECTION in read_agent("spec-reviewer.md")

    def test_domain_analyst_has_review_tone(self):
        assert REVIEW_TONE_SECTION in read_agent("domain-analyst.md")

    def test_domain_negotiator_has_review_tone(self):
        assert REVIEW_TONE_SECTION in read_agent("domain-negotiator.md")

    def test_impl_verifier_has_review_tone(self):
        assert REVIEW_TONE_SECTION in read_agent("impl-verifier.md")

    def test_implementer_no_review_tone(self):
        assert REVIEW_TONE_SECTION not in read_agent("implementer.md")

    def test_biz_impact_analysis_no_review_tone(self):
        assert REVIEW_TONE_SECTION not in read_agent("biz-impact-analysis.md")


# ── Review Tone: content rules ───────────────────────────────────────────────

class TestReviewToneContent:
    def test_review_agents_forbid_pleasantries(self):
        for agent in REVIEW_AGENTS:
            content = read_agent(agent)
            assert "No pleasantries" in content, (
                f"{agent} missing 'No pleasantries' rule"
            )

    def test_review_agents_forbid_hedging(self):
        for agent in REVIEW_AGENTS:
            content = read_agent(agent)
            assert "without hedging" in content or "hedge" in content, (
                f"{agent} missing anti-hedging rule"
            )


# ── Source Code Reading Limits: present in 4 review agents ──────────────────

class TestReadingLimitsPresent:
    def test_spec_reviewer_has_reading_limits(self):
        assert READING_LIMITS_SECTION in read_agent("spec-reviewer.md")

    def test_domain_analyst_has_reading_limits(self):
        assert READING_LIMITS_SECTION in read_agent("domain-analyst.md")

    def test_domain_negotiator_has_reading_limits(self):
        assert READING_LIMITS_SECTION in read_agent("domain-negotiator.md")

    def test_impl_verifier_has_reading_limits(self):
        assert READING_LIMITS_SECTION in read_agent("impl-verifier.md")

    def test_implementer_no_reading_limits(self):
        # implementer.md does not receive reading limits section
        assert READING_LIMITS_SECTION not in read_agent("implementer.md")


# ── Source Code Reading Limits: section order ────────────────────────────────

class TestReadingLimitsPosition:
    def test_spec_reviewer_reading_limits_before_boundary(self):
        content = read_agent("spec-reviewer.md")
        assert content.index(READING_LIMITS_SECTION) < content.index(BOUNDARY_SECTION)

    def test_domain_analyst_reading_limits_before_boundary(self):
        content = read_agent("domain-analyst.md")
        assert content.index(READING_LIMITS_SECTION) < content.index(BOUNDARY_SECTION)

    def test_domain_negotiator_reading_limits_before_boundary(self):
        content = read_agent("domain-negotiator.md")
        assert content.index(READING_LIMITS_SECTION) < content.index(BOUNDARY_SECTION)

    def test_impl_verifier_reading_limits_before_boundary(self):
        content = read_agent("impl-verifier.md")
        assert content.index(READING_LIMITS_SECTION) < content.index(BOUNDARY_SECTION)

    def test_spec_reviewer_review_tone_before_reading_limits(self):
        content = read_agent("spec-reviewer.md")
        assert content.index(REVIEW_TONE_SECTION) < content.index(READING_LIMITS_SECTION)

    def test_domain_analyst_review_tone_before_reading_limits(self):
        content = read_agent("domain-analyst.md")
        assert content.index(REVIEW_TONE_SECTION) < content.index(READING_LIMITS_SECTION)

    def test_domain_negotiator_review_tone_before_reading_limits(self):
        content = read_agent("domain-negotiator.md")
        assert content.index(REVIEW_TONE_SECTION) < content.index(READING_LIMITS_SECTION)

    def test_impl_verifier_review_tone_before_reading_limits(self):
        content = read_agent("impl-verifier.md")
        assert content.index(REVIEW_TONE_SECTION) < content.index(READING_LIMITS_SECTION)
