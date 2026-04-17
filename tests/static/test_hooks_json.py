"""Unit tests for hooks/hooks.json configuration integrity.

Red Team tests: validate that hooks.json is valid, contains the PreCompact
hook entry, and preserves backward-compatible PreToolUse entries.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Constants ──
ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"


@pytest.fixture
def hooks_data():
    """Load and return the parsed hooks.json content."""
    assert HOOKS_JSON.exists(), f"hooks.json not found at {HOOKS_JSON}"
    content = HOOKS_JSON.read_text(encoding="utf-8")
    return json.loads(content)


# ══════════════════════════════════════════════════════
# hooks.json Structural Validity
# ══════════════════════════════════════════════════════

class TestHooksJsonValidity:
    """Verify hooks.json is well-formed and loadable."""

    def test_hooks_json_valid(self):
        """hooks.json must be valid JSON."""
        assert HOOKS_JSON.exists(), "hooks.json must exist"
        content = HOOKS_JSON.read_text(encoding="utf-8")
        data = json.loads(content)  # Will raise on invalid JSON
        assert isinstance(data, dict), "hooks.json root must be an object"
        assert "hooks" in data, "hooks.json must have a top-level 'hooks' key"


# ══════════════════════════════════════════════════════
# PreCompact Hook Configuration
# ══════════════════════════════════════════════════════

class TestPreCompactHookConfig:
    """Verify the PreCompact event is properly configured in hooks.json."""

    def test_hooks_json_has_pre_compact(self, hooks_data):
        """hooks.json must contain a 'PreCompact' event entry."""
        hooks = hooks_data.get("hooks", {})
        assert "PreCompact" in hooks, (
            "hooks.json must define a 'PreCompact' event hook "
            "(Issue #5: inject recovery prompt before context compaction)"
        )

    def test_pre_compact_hook_references_script(self, hooks_data):
        """The PreCompact hook command must reference 'pre-compact.py'."""
        hooks = hooks_data.get("hooks", {})
        pre_compact_entries = hooks.get("PreCompact", [])
        assert len(pre_compact_entries) > 0, "PreCompact must have at least one entry"

        # Search across all entries and their nested hooks for the script reference
        found = False
        for entry in pre_compact_entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if "pre-compact.py" in cmd:
                    found = True
                    break
            if found:
                break

        assert found, (
            "PreCompact hook command must reference 'pre-compact.py' script"
        )

    def test_pre_compact_hook_has_timeout(self, hooks_data):
        """The PreCompact hook must have a timeout configured."""
        hooks = hooks_data.get("hooks", {})
        pre_compact_entries = hooks.get("PreCompact", [])
        assert len(pre_compact_entries) > 0, "PreCompact must have at least one entry"

        found_timeout = False
        for entry in pre_compact_entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if "pre-compact.py" in cmd:
                    timeout = hook.get("timeout")
                    assert timeout is not None, (
                        "PreCompact hook for pre-compact.py must have a 'timeout' field"
                    )
                    assert isinstance(timeout, (int, float)) and timeout > 0, (
                        f"PreCompact hook timeout must be a positive number, got {timeout}"
                    )
                    found_timeout = True
                    break
            if found_timeout:
                break

        assert found_timeout, "Could not find pre-compact.py hook to verify timeout"


# ══════════════════════════════════════════════════════
# Regression: Existing Hooks Preserved
# ══════════════════════════════════════════════════════

class TestExistingHooksRegression:
    """Verify that the dispatcher pattern preserves completion verification."""

    def test_dispatcher_registered_for_pre_tool_use(self, hooks_data):
        """PreToolUse must use dispatcher.py as the unified entry point."""
        hooks = hooks_data.get("hooks", {})
        assert "PreToolUse" in hooks, (
            "hooks.json must contain 'PreToolUse' event"
        )

        pre_tool_entries = hooks["PreToolUse"]
        found_dispatcher = False
        for entry in pre_tool_entries:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if "dispatcher.py" in cmd:
                    found_dispatcher = True
                    break
            if found_dispatcher:
                break

        assert found_dispatcher, (
            "PreToolUse must use dispatcher.py as unified entry point "
            "(B-1: Hook dispatcher pattern replaces direct hook registration)"
        )

    def test_dispatcher_uses_wildcard_matcher(self, hooks_data):
        """Dispatcher must use '*' matcher to receive all PreToolUse events."""
        hooks = hooks_data.get("hooks", {})
        pre_tool_entries = hooks.get("PreToolUse", [])

        found_wildcard = False
        for entry in pre_tool_entries:
            if entry.get("matcher") == "*":
                for hook in entry.get("hooks", []):
                    if "dispatcher.py" in hook.get("command", ""):
                        found_wildcard = True
                        break
            if found_wildcard:
                break

        assert found_wildcard, (
            "Dispatcher entry must use '*' matcher for routing flexibility"
        )

    def test_dispatcher_has_timeout(self, hooks_data):
        """Dispatcher must have a timeout configured."""
        hooks = hooks_data.get("hooks", {})
        pre_tool_entries = hooks.get("PreToolUse", [])

        for entry in pre_tool_entries:
            for hook in entry.get("hooks", []):
                if "dispatcher.py" in hook.get("command", ""):
                    timeout = hook.get("timeout")
                    assert timeout is not None, "Dispatcher must have a timeout"
                    assert isinstance(timeout, (int, float)) and timeout > 0
                    return

        pytest.fail("Could not find dispatcher.py entry to verify timeout")

    def test_verify_completion_script_exists(self, hooks_data):
        """verify-completion.py must exist as a loadable sub-hook
        (dispatcher loads it at runtime, not via hooks.json)."""
        from pathlib import Path
        ROOT = Path(__file__).resolve().parent.parent.parent
        verify_script = ROOT / "hooks" / "verify-completion.py"
        assert verify_script.exists(), (
            "verify-completion.py must still exist as a dispatcher sub-hook"
        )


# ══════════════════════════════════════════════════════
# Session Lifecycle Hooks (Wave 2)
# ══════════════════════════════════════════════════════

class TestSessionStartHookConfig:
    """Verify SessionStart hook is properly configured."""

    def test_has_session_start(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        assert "SessionStart" in hooks, "hooks.json must define SessionStart event"

    def test_session_start_references_script(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        entries = hooks.get("SessionStart", [])
        found = any(
            "session-start.py" in hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        )
        assert found, "SessionStart must reference session-start.py"

    def test_session_start_has_timeout(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        for entry in hooks.get("SessionStart", []):
            for hook in entry.get("hooks", []):
                if "session-start.py" in hook.get("command", ""):
                    assert hook.get("timeout") is not None
                    assert hook["timeout"] > 0
                    return
        pytest.fail("Could not find session-start.py to verify timeout")


class TestStopHookConfig:
    """Verify Stop hook is properly configured."""

    def test_has_stop(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        assert "Stop" in hooks, "hooks.json must define Stop event"

    def test_stop_references_script(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        entries = hooks.get("Stop", [])
        found = any(
            "stop-persist.py" in hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        )
        assert found, "Stop must reference stop-persist.py"

    def test_stop_has_timeout(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        for entry in hooks.get("Stop", []):
            for hook in entry.get("hooks", []):
                if "stop-persist.py" in hook.get("command", ""):
                    assert hook.get("timeout") is not None
                    assert hook["timeout"] > 0
                    return
        pytest.fail("Could not find stop-persist.py to verify timeout")


class TestSessionEndHookConfig:
    """Verify SessionEnd hook is properly configured."""

    def test_has_session_end(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        assert "SessionEnd" in hooks, "hooks.json must define SessionEnd event"

    def test_session_end_references_script(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        entries = hooks.get("SessionEnd", [])
        found = any(
            "session-end.py" in hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
        )
        assert found, "SessionEnd must reference session-end.py"

    def test_session_end_has_timeout(self, hooks_data):
        hooks = hooks_data.get("hooks", {})
        for entry in hooks.get("SessionEnd", []):
            for hook in entry.get("hooks", []):
                if "session-end.py" in hook.get("command", ""):
                    assert hook.get("timeout") is not None
                    assert hook["timeout"] > 0
                    return
        pytest.fail("Could not find session-end.py to verify timeout")
