"""Unit tests for hooks/pre-compact.py

Red Team tests: verify the PreCompact hook outputs valid JSON with the
required fields for context-compaction recovery.

These tests call the hook script as a subprocess (same approach as
test_verify_completion.py) and validate the stdout JSON contract.
Unit tests also cover the internal functions added in v0.7+.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ── Constants ──
ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOK_SCRIPT = ROOT / "hooks" / "pre-compact.py"
HOOKS_DIR = ROOT / "hooks"


@pytest.fixture
def run_pre_compact():
    """Run hooks/pre-compact.py with the given stdin payload and return parsed stdout."""
    def _run(stdin_payload: dict | None = None):
        payload = json.dumps(stdin_payload or {})
        result = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result
    return _run


@pytest.fixture
def pre_compact_module():
    """Import pre-compact.py as a module for unit testing internal functions."""
    spec = importlib.util.spec_from_file_location(
        "pre_compact",
        HOOKS_DIR / "pre-compact.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# PreCompact Hook Output Contract
# ══════════════════════════════════════════════════════

class TestPreCompactHook:
    """Verify the pre-compact.py hook output conforms to the Claude hook protocol."""

    def test_pre_compact_outputs_valid_json(self, run_pre_compact):
        """Hook stdout must be parseable JSON."""
        result = run_pre_compact({})
        assert result.returncode == 0, (
            f"pre-compact.py exited with code {result.returncode}; "
            f"stderr: {result.stderr}"
        )
        output = json.loads(result.stdout)
        assert isinstance(output, dict), "Output must be a JSON object"

    def test_pre_compact_has_system_message(self, run_pre_compact):
        """Output must contain a 'systemMessage' field (the recovery prompt)."""
        result = run_pre_compact({})
        output = json.loads(result.stdout)
        assert "systemMessage" in output, (
            "pre-compact.py output must include 'systemMessage' for context recovery"
        )
        assert isinstance(output["systemMessage"], str)
        assert len(output["systemMessage"]) > 0, "systemMessage must not be empty"

    def test_pre_compact_mentions_session_state(self, run_pre_compact):
        """systemMessage must reference session-state.md so the LLM reads it after compaction."""
        result = run_pre_compact({})
        output = json.loads(result.stdout)
        msg = output["systemMessage"]
        assert "session-state.md" in msg, (
            "systemMessage must mention 'session-state.md' for post-compaction recovery"
        )

    def test_pre_compact_mentions_session_data(self, run_pre_compact):
        """systemMessage must reference the session-data directory for checkpoint files."""
        result = run_pre_compact({})
        output = json.loads(result.stdout)
        msg = output["systemMessage"]
        assert "session-data" in msg, (
            "systemMessage must mention 'session-data' directory for checkpoint recovery"
        )

    def test_pre_compact_result_continue(self, run_pre_compact):
        """result field must be 'continue' — the hook must not block the workflow."""
        result = run_pre_compact({})
        output = json.loads(result.stdout)
        # The hook protocol uses either a top-level "result" or nested structure.
        # Accept either pattern.
        if "result" in output:
            assert output["result"] == "continue", (
                f"pre-compact hook result must be 'continue', got '{output['result']}'"
            )
        else:
            # If there's no explicit "result" field, the hook should not have
            # a "deny" decision — absence of deny means continue.
            hook_output = output.get("hookSpecificOutput", {})
            decision = hook_output.get("permissionDecision", "")
            assert decision != "deny", (
                "pre-compact hook must not deny (block) the workflow"
            )


class TestPreCompactHookScriptExists:
    """Guard test: the hook script file must exist."""

    def test_hook_script_exists(self):
        """hooks/pre-compact.py must exist in the plugin."""
        assert HOOK_SCRIPT.exists(), (
            f"Missing hook script: {HOOK_SCRIPT}\n"
            "Issue #5 requires a PreCompact hook at hooks/pre-compact.py"
        )


# ══════════════════════════════════════════════════════
# _extract_risk_level / _extract_current_phase (v0.7+)
# ══════════════════════════════════════════════════════

class TestExtractHelpers:
    """Tests for session-state.md field extraction helpers."""

    def test_extract_risk_level_p0(self, pre_compact_module, tmp_path):
        f = tmp_path / "state.md"
        f.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P0\n"
            "current_phase: implementation\n"
            "routing: []\n"
            "auto_continue: true\n"
            "<!-- ECW:STATUS:END -->"
        )
        assert pre_compact_module._extract_risk_level(str(f)) == "P0"

    def test_extract_risk_level_p3(self, pre_compact_module, tmp_path):
        f = tmp_path / "state.md"
        f.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P3\n"
            "routing: []\n"
            "auto_continue: true\n"
            "current_phase: impl-complete\n"
            "<!-- ECW:STATUS:END -->"
        )
        assert pre_compact_module._extract_risk_level(str(f)) == "P3"

    def test_extract_risk_level_missing(self, pre_compact_module, tmp_path):
        f = tmp_path / "state.md"
        f.write_text("No risk info here\n")
        assert pre_compact_module._extract_risk_level(str(f)) is None

    def test_extract_current_phase(self, pre_compact_module, tmp_path):
        f = tmp_path / "state.md"
        f.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "current_phase: requirements-elicitation\n"
            "routing: []\n"
            "auto_continue: true\n"
            "risk_level: P1\n"
            "<!-- ECW:STATUS:END -->"
        )
        assert pre_compact_module._extract_current_phase(str(f)) == "requirements-elicitation"

    def test_extract_current_phase_missing(self, pre_compact_module, tmp_path):
        f = tmp_path / "state.md"
        f.write_text("No phase info\n")
        assert pre_compact_module._extract_current_phase(str(f)) is None


# ══════════════════════════════════════════════════════
# _build_recovery_message (v0.7+)
# ══════════════════════════════════════════════════════

class TestBuildRecoveryMessage:
    """Tests for the recovery message builder added in the v0.7 refactor."""

    def test_with_state_risk_phase_and_checkpoints(self, pre_compact_module, tmp_path):
        """Full happy path: state + risk + phase + checkpoint files."""
        state = tmp_path / ".claude" / "ecw" / "session-data" / "wf1" / "session-state.md"
        state.parent.mkdir(parents=True)
        state.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P0\n"
            "current_phase: implementation\n"
            "routing: []\n"
            "auto_continue: true\n"
            "<!-- ECW:STATUS:END -->"
        )

        checkpoint_files = [
            ".claude/ecw/session-data/wf1/session-state.md",
            ".claude/ecw/session-data/wf1/domain-collab-report.md",
            ".claude/ecw/session-data/wf1/requirements-summary.md",
        ]
        msg = pre_compact_module._build_recovery_message(str(state), checkpoint_files, str(tmp_path))

        assert "MANDATORY: Auto-continue" in msg
        assert "(P0)" in msg
        assert "domain-collab-report.md" in msg
        assert "requirements-summary.md" in msg
        # session-state.md should NOT appear in the "checkpoint files" step
        # (it's already shown in step 1 as the primary state file)
        if "checkpoint files" in msg:
            checkpoint_section = msg.split("checkpoint files")[1].split("\n**NEXT")[0]
            assert "session-state" not in checkpoint_section
        assert "`implementation`" in msg

    def test_without_state_path(self, pre_compact_module, tmp_path):
        """No session-state.md: message instructs discovery."""
        msg = pre_compact_module._build_recovery_message(None, [], str(tmp_path))

        assert "MANDATORY: Auto-continue" in msg
        assert "List `.claude/ecw/session-data/`" in msg
        assert "NEXT ACTION" in msg

    def test_with_state_but_no_risk_no_phase(self, pre_compact_module, tmp_path):
        """State file exists but has no risk/phase fields."""
        state = tmp_path / "state.md"
        state.write_text("# Session State\nSome content\n")

        msg = pre_compact_module._build_recovery_message(str(state), [], str(tmp_path))

        assert "MANDATORY: Auto-continue" in msg
        # No risk parenthetical
        assert "(P" not in msg
        # Generic next action (no phase)
        assert "determine the current" in msg

    def test_checkpoint_files_capped_at_5(self, pre_compact_module, tmp_path):
        """Only first 5 non-state checkpoint files are listed."""
        state = tmp_path / "state.md"
        state.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "routing: []\n"
            "auto_continue: true\n"
            "current_phase: impl-complete\n"
            "<!-- ECW:STATUS:END -->"
        )

        checkpoints = [f".claude/ecw/session-data/wf1/file-{i}.md" for i in range(8)]
        msg = pre_compact_module._build_recovery_message(str(state), checkpoints, str(tmp_path))

        assert "file-4.md" in msg
        assert "file-5.md" not in msg

    def test_no_checkpoint_files_omits_step3(self, pre_compact_module, tmp_path):
        """Empty checkpoint list: step 3 (read checkpoints) is omitted."""
        state = tmp_path / "state.md"
        state.write_text(
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P2\n"
            "routing: []\n"
            "auto_continue: true\n"
            "current_phase: impl-complete\n"
            "<!-- ECW:STATUS:END -->"
        )

        msg = pre_compact_module._build_recovery_message(str(state), [], str(tmp_path))

        assert "checkpoint files" not in msg

    def test_auto_continue_directive_is_first(self, pre_compact_module, tmp_path):
        """Auto-continue directive must be the very first content in the message."""
        msg = pre_compact_module._build_recovery_message(None, [], str(tmp_path))
        assert msg.startswith("**MANDATORY: Auto-continue")


# ══════════════════════════════════════════════════════
# _find_session_state (v0.7+)
# ══════════════════════════════════════════════════════

class TestFindSessionState:
    """Tests for find_session_state (now delegated to marker_utils)."""

    def test_finds_in_session_data_subdir(self, pre_compact_module, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260418-1200"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text("# State")
        find_session_state = pre_compact_module.find_session_state
        result = find_session_state(str(tmp_path))
        assert result is not None
        assert "session-state.md" in result

    def test_falls_back_to_legacy(self, pre_compact_module, tmp_path):
        legacy = tmp_path / ".claude" / "ecw" / "session-state.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("# Legacy State")
        find_session_state = pre_compact_module.find_session_state
        result = find_session_state(str(tmp_path))
        assert result is not None

    def test_returns_none_when_missing(self, pre_compact_module, tmp_path):
        find_session_state = pre_compact_module.find_session_state
        assert find_session_state(str(tmp_path)) is None


# ══════════════════════════════════════════════════════
# _get_session_data_files (v0.7+)
# ══════════════════════════════════════════════════════

class TestGetSessionDataFiles:
    """Tests for _get_session_data_files listing checkpoint files."""

    def test_lists_md_files_from_subdir(self, pre_compact_module, tmp_path):
        subdir = tmp_path / ".claude" / "ecw" / "session-data" / "wf1"
        subdir.mkdir(parents=True)
        (subdir / "report.md").write_text("# Report")
        (subdir / "notes.txt").write_text("not md")
        result = pre_compact_module._get_session_data_files(str(tmp_path))
        assert any("report.md" in f for f in result)
        assert not any("notes.txt" in f for f in result)

    def test_returns_empty_when_no_dir(self, pre_compact_module, tmp_path):
        assert pre_compact_module._get_session_data_files(str(tmp_path)) == []


# ══════════════════════════════════════════════════════
# _append_compact_marker (v0.7+)
# ══════════════════════════════════════════════════════

class TestAppendCompactMarker:
    """Tests for _append_compact_marker appending timestamp to state file."""

    def test_appends_marker(self, pre_compact_module, tmp_path):
        state = tmp_path / "state.md"
        state.write_text("# ECW State\n")
        pre_compact_module._append_compact_marker(str(state))
        content = state.read_text()
        assert "<!-- ECW:COMPACT:" in content
        assert content.startswith("# ECW State\n")
