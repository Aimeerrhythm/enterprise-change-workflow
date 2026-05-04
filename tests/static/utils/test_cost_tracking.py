"""Tests for Subagent Ledger cost tracking.

Validates:
1. session-state-format.md LEDGER entry has `model` key (YAML format, Issue #40)
2. SKILL.md inline Ledger examples include model value (YAML format)
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
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
    """Subagent Ledger must include model key for cost tracking."""

    def test_session_state_format_has_model_key(self):
        content = SESSION_STATE_FORMAT.read_text(encoding="utf-8")
        assert re.search(
            r'^\s*model:', content, re.MULTILINE
        ), "session-state-format.md LEDGER entry missing 'model:' YAML key"

    def test_ledger_entry_has_required_yaml_keys(self):
        content = SESSION_STATE_FORMAT.read_text(encoding="utf-8")
        for key in ("phase", "agent", "type", "model", "scale", "started", "duration"):
            assert re.search(rf'{key}:', content), (
                f"session-state-format.md LEDGER entry missing YAML key '{key}'"
            )

    @pytest.mark.parametrize("skill", SKILLS_WITH_LEDGER_EXAMPLES)
    def test_skills_ledger_examples_include_model(self, skill):
        content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        ledger_sections = re.findall(
            r"(?:Ledger update|Subagent Ledger).{0,800}", content, re.DOTALL
        )
        assert ledger_sections, (
            f"{skill}/SKILL.md: no Ledger update section found"
        )
        found_model = False
        for section in ledger_sections:
            # New YAML format: model: opus / sonnet / haiku
            if re.search(r'model:\s*(opus|sonnet|haiku)', section):
                found_model = True
                break
        assert found_model, (
            f"{skill}/SKILL.md: Ledger inline examples missing model value (opus/sonnet/haiku) "
            f"— expected YAML format `model: <model_name>`"
        )
