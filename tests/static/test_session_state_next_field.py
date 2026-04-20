"""Tests for session-state Next field and hook integration.

Validates:
1. session-state-format.md has Next field in STATUS section
2. pre-compact.py extracts Next field for precise recovery
3. session-start.py includes Next field in recovery hint
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
HOOKS_DIR = ROOT / "hooks"
SESSION_STATE_FORMAT = SKILLS_DIR / "risk-classifier" / "session-state-format.md"


class TestSessionStateNextField:
    """session-state-format.md must include Next field in STATUS section."""

    @pytest.fixture(autouse=True)
    def load_format(self):
        self.content = SESSION_STATE_FORMAT.read_text(encoding="utf-8")

    def test_has_next_field(self):
        assert "**Next**" in self.content, (
            "session-state-format.md missing '**Next**' field"
        )

    def test_next_field_between_status_markers(self):
        start = self.content.find("ECW:STATUS:START")
        end = self.content.find("ECW:STATUS:END")
        assert start != -1 and end != -1, "STATUS markers not found"
        status_section = self.content[start:end]
        assert "**Next**" in status_section, (
            "**Next** field must be inside ECW:STATUS:START/END markers"
        )


class TestPreCompactNextField:
    """pre-compact.py must use Next field for precise recovery."""

    @pytest.fixture
    def pre_compact(self):
        spec = importlib.util.spec_from_file_location(
            "pre_compact", HOOKS_DIR / "pre-compact.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_extracts_next_skill(self, pre_compact, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260420-1200"
        state_dir.mkdir(parents=True)
        state_path = state_dir / "session-state.md"
        state_path.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "- **Risk Level**: P1\n"
            "- **Current Phase**: phase2-complete\n"
            "- **Next**: ecw:writing-plans\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        msg = pre_compact._build_recovery_message(
            str(state_path), [], str(tmp_path)
        )
        assert "ecw:writing-plans" in msg, (
            "Recovery message must include the Next skill name"
        )
        assert re.search(r'invoke.*ecw:writing-plans.*immediately', msg, re.IGNORECASE) or \
               re.search(r'immediately.*invoke.*ecw:writing-plans', msg, re.IGNORECASE) or \
               "ecw:writing-plans" in msg, \
            "Recovery should direct immediate invocation of Next skill"

    def test_falls_back_without_next(self, pre_compact, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260420-1200"
        state_dir.mkdir(parents=True)
        state_path = state_dir / "session-state.md"
        state_path.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "- **Risk Level**: P1\n"
            "- **Current Phase**: phase2-complete\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        msg = pre_compact._build_recovery_message(
            str(state_path), [], str(tmp_path)
        )
        assert "phase2-complete" in msg, (
            "Without Next field, recovery must fall back to phase-based guidance"
        )


class TestSessionStartNextField:
    """session-start.py must include Next field in recovery hint."""

    @pytest.fixture
    def session_start(self):
        spec = importlib.util.spec_from_file_location(
            "session_start", HOOKS_DIR / "session-start.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_next_skill_in_state_fields(self, session_start):
        content = (
            "- **Risk Level**: P1\n"
            "- **Next**: ecw:impl-verify\n"
            "- **Status**: active\n"
        )
        fields = session_start._extract_state_fields(content)
        assert "next_skill" in fields, (
            "_extract_state_fields must extract 'next_skill' from **Next** field"
        )
        assert fields["next_skill"] == "ecw:impl-verify"
