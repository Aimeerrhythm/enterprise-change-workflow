"""Static verification: SKILL.md checkpoint directives and CLAUDE.md artifact table.

Red Team tests: validate that each skill writes the expected session-data
checkpoint files and that stage transitions include compact suggestions.

These are purely text-content assertions on SKILL.md files — no runtime
state or subprocesses needed.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ── Constants ──
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = ROOT / "skills"
CLAUDE_MD = ROOT / "CLAUDE.md"


def _read_skill(skill_name: str) -> str:
    """Read a SKILL.md file and return its content."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    assert path.exists(), f"skills/{skill_name}/SKILL.md does not exist"
    return path.read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════
# Checkpoint File Directives in Skills
# ══════════════════════════════════════════════════════

class TestSessionDataCheckpoints:
    """Verify that skills write checkpoint files to .claude/ecw/session-data/."""

    def test_requirements_elicitation_has_checkpoint(self):
        """requirements-elicitation SKILL.md must instruct writing
        session-data/.../requirements-summary.md after completing elicitation."""
        content = _read_skill("requirements-elicitation")
        assert "session-data/" in content and "requirements-summary.md" in content, (
            "requirements-elicitation SKILL.md must contain a directive to write "
            "'requirements-summary.md' under session-data/ as a checkpoint artifact"
        )

    def test_risk_classifier_phase2_has_checkpoint(self):
        """risk-classifier SKILL.md must instruct writing
        session-data/.../phase2-assessment.md after Phase 2 assessment."""
        content = _read_skill("risk-classifier")
        assert "session-data/" in content and "phase2-assessment.md" in content, (
            "risk-classifier SKILL.md must contain a directive to write "
            "'phase2-assessment.md' under session-data/ as a checkpoint artifact"
        )

    def test_impl_verify_always_writes_findings(self):
        """impl-verify SKILL.md must:
        1. NOT have '>5 must-fix' as a precondition for writing findings
        2. Write findings to session-data/impl-verify-findings.md (always)
        """
        content = _read_skill("impl-verify")

        # The old condition ">5 must-fix" should be removed — findings are
        # always written regardless of count.
        # We check that the phrase ">5 must-fix" does NOT appear as a
        # write-precondition. It may still appear in other contexts (e.g.
        # historical notes), so we look for the specific pattern that gates
        # the file write.
        # Pattern: "> 5 must-fix" appearing near "write" or "findings.md"
        lines = content.split("\n")
        for line in lines:
            if "impl-verify-findings" in line or "findings" in line.lower():
                assert ">5 must-fix" not in line and "> 5 must-fix" not in line, (
                    "impl-verify SKILL.md must NOT gate findings file write on "
                    "'>5 must-fix' — findings should always be written"
                )

        # Must reference the new session-data location
        assert "session-data/" in content and "impl-verify-findings.md" in content, (
            "impl-verify SKILL.md must write findings to "
            "'impl-verify-findings.md' under session-data/ (always, not conditionally)"
        )


# ══════════════════════════════════════════════════════
# Compact Suggestions at Stage Transitions
# ══════════════════════════════════════════════════════

class TestCompactSuggestions:
    """Verify that key stage-transition skills suggest /compact to the user."""

    def test_domain_collab_has_compact_suggestion(self):
        """domain-collab SKILL.md must suggest /compact after Round 3
        (the analysis is complete and a large context can be reclaimed)."""
        content = _read_skill("domain-collab")
        assert "/compact" in content, (
            "domain-collab SKILL.md must include a '/compact' suggestion "
            "after Round 3 to help manage context window"
        )

    def test_writing_plans_has_compact_suggestion(self):
        """writing-plans SKILL.md must suggest /compact after plan production
        (transition from planning to implementation is a natural compact point)."""
        content = _read_skill("writing-plans")
        assert "/compact" in content, (
            "writing-plans SKILL.md must include a '/compact' suggestion "
            "to help manage context window after plan production"
        )


# ══════════════════════════════════════════════════════
# CLAUDE.md Artifact Table Documentation
# ══════════════════════════════════════════════════════

class TestClaudeMdArtifactTable:
    """Verify that CLAUDE.md documents the new session-data checkpoint artifacts."""

    def test_claude_md_documents_session_data(self):
        """CLAUDE.md must list session-data checkpoint files in its artifact table."""
        assert CLAUDE_MD.exists(), "CLAUDE.md must exist at project root"
        content = CLAUDE_MD.read_text(encoding="utf-8")

        assert "session-data/" in content and "requirements-summary" in content, (
            "CLAUDE.md artifact table must document "
            "'requirements-summary' checkpoint under session-data/"
        )
        assert "session-data/" in content and "phase2-assessment" in content, (
            "CLAUDE.md artifact table must document "
            "'phase2-assessment' checkpoint under session-data/"
        )
