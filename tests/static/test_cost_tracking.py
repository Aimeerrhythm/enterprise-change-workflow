"""Tests for Subagent Ledger cost tracking.

Validates:
1. session-state-format.md Ledger has Model column (7 columns total)
2. SKILL.md inline Ledger examples include Model value
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
SESSION_STATE_FORMAT = SKILLS_DIR / "risk-classifier" / "session-state-format.md"

SKILLS_WITH_LEDGER_EXAMPLES = [
    "domain-collab",
    "spec-challenge",
    "biz-impact-analysis",
    "requirements-elicitation",
    "impl-orchestration",
]


class TestLedgerModelColumn:
    """Subagent Ledger must include Model column for cost tracking."""

    def test_session_state_format_has_model_column(self):
        content = SESSION_STATE_FORMAT.read_text(encoding="utf-8")
        assert re.search(
            r"\|\s*Model\s*\|", content
        ), "session-state-format.md Ledger header missing 'Model' column"

    def test_ledger_has_seven_columns(self):
        content = SESSION_STATE_FORMAT.read_text(encoding="utf-8")
        header_match = re.search(
            r"^\|([^|\n]+\|){6,8}\s*$", content, re.MULTILINE
        )
        assert header_match, "Could not find Ledger header row"
        header = header_match.group(0)
        cols = [c.strip() for c in header.strip("|").split("|")]
        assert len(cols) == 7, (
            f"Ledger should have 7 columns, found {len(cols)}: {cols}"
        )
        expected = ["Phase", "Agent", "Type", "Model", "Est. Scale", "Started", "Duration"]
        assert cols == expected, f"Ledger columns mismatch: {cols} != {expected}"

    @pytest.mark.parametrize("skill", SKILLS_WITH_LEDGER_EXAMPLES)
    def test_skills_ledger_examples_include_model(self, skill):
        content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        ledger_sections = re.findall(
            r"(?:Ledger update|Subagent Ledger).{0,500}", content, re.DOTALL
        )
        assert ledger_sections, (
            f"{skill}/SKILL.md: no Ledger update section found"
        )
        found_model = False
        for section in ledger_sections:
            if re.search(r"\|\s*(?:opus|sonnet|haiku)\s*\|", section):
                found_model = True
                break
        assert found_model, (
            f"{skill}/SKILL.md: Ledger inline examples missing model value (opus/sonnet/haiku)"
        )
