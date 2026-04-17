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
    """Verify that adding PreCompact does not break existing hook entries."""

    def test_verify_completion_still_exists(self, hooks_data):
        """PreToolUse → TaskUpdate → verify-completion.py must still be configured
        (regression guard — Issue #5 changes should not remove existing hooks)."""
        hooks = hooks_data.get("hooks", {})
        assert "PreToolUse" in hooks, (
            "hooks.json must still contain 'PreToolUse' event "
            "(verify-completion hook must not be removed)"
        )

        pre_tool_entries = hooks["PreToolUse"]
        found_verify = False
        for entry in pre_tool_entries:
            matcher = entry.get("matcher", "")
            if matcher == "TaskUpdate":
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "verify-completion.py" in cmd:
                        found_verify = True
                        break
            if found_verify:
                break

        assert found_verify, (
            "PreToolUse → TaskUpdate → verify-completion.py must still exist in hooks.json "
            "(regression check: Issue #5 must not remove existing hooks)"
        )
