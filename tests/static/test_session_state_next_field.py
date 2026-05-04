"""Tests for session-state Next field and hook integration.

Validates:
1. session-state-format.md has Next field in STATUS section
2. pre-compact.py extracts Next field for precise recovery
3. session-start.py includes Next field in recovery hint
4. risk-classifier SKILL.md write instruction explicitly requires ECW:STATUS markers
5. auto-continue hook silently no-ops on malformed session-state (no STATUS block)
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
            "risk_level: P1\n"
            "current_phase: phase2-complete\n"
            "next: ecw:writing-plans\n"
            "routing: []\n"
            "auto_continue: true\n"
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
            "risk_level: P1\n"
            "current_phase: phase2-complete\n"
            "routing: []\n"
            "auto_continue: true\n"
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
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "next: ecw:impl-verify\n"
            "auto_continue: true\n"
            "routing: []\n"
            "current_phase: plan-complete\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        fields = session_start._extract_state_fields(content)
        assert "next_skill" in fields, (
            "_extract_state_fields must extract 'next_skill' from YAML `next` field"
        )
        assert fields["next_skill"] == "ecw:impl-verify"


RISK_CLASSIFIER_SKILL = SKILLS_DIR / "risk-classifier" / "SKILL.md"


class TestRiskClassifierWriteInstruction:
    """risk-classifier SKILL.md must explicitly require ECW:STATUS markers in write instruction.

    Rationale: If the write instruction only says 'read the template', the model may
    write a plain-Markdown session-state.md that the auto-continue hook cannot parse,
    silently breaking the downstream skill chain.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = RISK_CLASSIFIER_SKILL.read_text(encoding="utf-8")

    def test_write_instruction_mentions_status_marker(self):
        assert "ECW:STATUS:START" in self.content, (
            "risk-classifier SKILL.md write instruction must explicitly name "
            "'ECW:STATUS:START' marker — 'read the template' alone is not enough"
        )

    def test_write_instruction_explains_consequence(self):
        # Must tell the model WHY markers are required (hook failure consequence)
        assert any(phrase in self.content for phrase in [
            "hook", "auto-continue", "silent", "chain"
        ]), (
            "risk-classifier SKILL.md must explain the consequence of omitting markers "
            "(hook failure / broken skill chain) so the model treats it as non-negotiable"
        )


class TestAutoContinueMarkerDependency:
    """auto-continue hook must silently no-op when session-state has no STATUS block.

    This is the known failure mode: wrong-format session-state causes hook to do
    nothing, leaving the model without routing guidance. The hook behaviour itself
    is correct (fail-safe), but the test documents the gap so regressions are visible.
    """

    @pytest.fixture
    def auto_continue(self):
        spec = importlib.util.spec_from_file_location(
            "auto_continue", HOOKS_DIR / "auto-continue.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_noop_on_missing_status_block(self, auto_continue, tmp_path, monkeypatch):
        """Hook must return continue (not inject systemMessage) when STATUS block absent."""
        import json, io

        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260428-1000"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "# ECW Session State\n"
            "<!-- MODE: analysis -->\n"
            "## Metadata\n"
            "- Risk Level: P1\n"
            "- Next: ecw:requirements-elicitation\n"
        )

        payload = json.dumps({
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:risk-classifier"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())

        auto_continue.main()
        output = json.loads("".join(captured))
        assert "systemMessage" not in output, (
            "Hook must NOT inject systemMessage when STATUS block is absent — "
            "this is the known silent-failure mode that breaks skill chaining"
        )

    def test_injects_routing_on_valid_status_block(self, auto_continue, tmp_path, monkeypatch):
        """Hook must inject systemMessage when STATUS block is present and auto_continue: true."""
        import json, io

        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260428-1000"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "auto_continue: true\n"
            "routing: [ecw:risk-classifier, ecw:requirements-elicitation, ecw:writing-plans]\n"
            "next: ecw:requirements-elicitation\n"
            "current_phase: phase1-complete\n"
            "<!-- ECW:STATUS:END -->\n"
        )

        payload = json.dumps({
            "tool_name": "Skill",
            "tool_input": {"skill": "ecw:risk-classifier"},
            "cwd": str(tmp_path),
        })
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        captured = []
        monkeypatch.setattr("sys.stdout", type("W", (), {
            "write": lambda self, s: captured.append(s),
            "flush": lambda self: None,
        })())

        auto_continue.main()
        output = json.loads("".join(captured))
        assert "systemMessage" in output, (
            "Hook must inject systemMessage when STATUS block present and Auto-Continue: yes"
        )
        assert "ecw:requirements-elicitation" in output["systemMessage"], (
            "systemMessage must reference the next skill in the routing chain"
        )
