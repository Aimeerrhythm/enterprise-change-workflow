"""Unit tests for hooks/pre-compact.py

Red Team tests: verify the PreCompact hook outputs valid JSON with the
required fields for context-compaction recovery.

These tests call the hook script as a subprocess (same approach as
test_verify_completion.py) and validate the stdout JSON contract.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ── Constants ──
ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_SCRIPT = ROOT / "hooks" / "pre-compact.py"


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
