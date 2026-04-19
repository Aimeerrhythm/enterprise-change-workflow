"""Unit tests for hooks/config-protect.py

Covers the config-protect sub-hook: protected file blocking, passthrough for
non-protected files, ECW_ALLOW_CONFIG_EDIT override, and edge cases.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def config_protect():
    """Import config-protect.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "config_protect",
        HOOKS_DIR / "config-protect.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_input(file_path, tool_name="Edit"):
    """Helper to create a minimal hook input dict."""
    return {
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "cwd": "/fake/project",
    }


# ══════════════════════════════════════════════════════
# Protected File Blocking
# ══════════════════════════════════════════════════════

class TestProtectedFileBlocking:
    """Verify that protected ECW config files are blocked."""

    @pytest.mark.parametrize("basename", [
        "ecw.yml",
        "domain-registry.md",
        "change-risk-classification.md",
        "ecw-path-mappings.md",
    ])
    def test_protected_file_is_blocked(self, config_protect, basename):
        """Each protected basename should produce a block result."""
        inp = _make_input(f"/fake/project/.claude/ecw/{basename}")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_CONFIG_EDIT", None)
            action, message = config_protect.check(inp)
        assert action == "block"
        assert basename in message

    def test_protected_file_in_nested_path(self, config_protect):
        """Protection works regardless of directory depth."""
        inp = _make_input("/some/deep/nested/path/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_CONFIG_EDIT", None)
            action, _ = config_protect.check(inp)
        assert action == "block"

    def test_write_tool_also_blocked(self, config_protect):
        """Write tool targeting protected file is also blocked."""
        inp = _make_input("/project/.claude/ecw/ecw.yml", tool_name="Write")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_CONFIG_EDIT", None)
            action, _ = config_protect.check(inp)
        assert action == "block"

    def test_block_message_contains_guidance(self, config_protect):
        """Block message should guide user to fix source code instead."""
        inp = _make_input("/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_CONFIG_EDIT", None)
            _, message = config_protect.check(inp)
        assert "ECW_ALLOW_CONFIG_EDIT" in message
        assert "source code" in message.lower() or "business logic" in message.lower()


# ══════════════════════════════════════════════════════
# Non-Protected File Passthrough
# ══════════════════════════════════════════════════════

class TestNonProtectedPassthrough:
    """Verify that non-protected files pass through without blocking."""

    def test_regular_java_file_passes(self, config_protect):
        inp = _make_input("/project/src/main/java/com/example/Service.java")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_regular_md_file_passes(self, config_protect):
        inp = _make_input("/project/docs/README.md")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_session_state_file_passes(self, config_protect):
        """session-state.md is NOT protected (it's an artifact, not config)."""
        inp = _make_input("/project/.claude/ecw/state/session-state.md")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_empty_file_path_passes(self, config_protect):
        inp = _make_input("")
        action, message = config_protect.check(inp)
        assert action == "continue"

    def test_missing_file_path_key_passes(self, config_protect):
        inp = {"tool_name": "Edit", "tool_input": {}, "cwd": "/fake"}
        action, message = config_protect.check(inp)
        assert action == "continue"

    def test_similar_but_different_name_passes(self, config_protect):
        """A file named 'my-ecw.yml' should not be blocked."""
        inp = _make_input("/project/my-ecw.yml")
        action, message = config_protect.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# ECW_ALLOW_CONFIG_EDIT Override
# ══════════════════════════════════════════════════════

class TestAllowConfigEditOverride:
    """Verify the environment variable override mechanism."""

    def test_override_allows_protected_file(self, config_protect):
        """ECW_ALLOW_CONFIG_EDIT=1 should bypass protection."""
        inp = _make_input("/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {"ECW_ALLOW_CONFIG_EDIT": "1"}):
            action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_override_value_0_still_blocks(self, config_protect):
        """ECW_ALLOW_CONFIG_EDIT=0 should NOT bypass protection."""
        inp = _make_input("/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {"ECW_ALLOW_CONFIG_EDIT": "0"}):
            action, _ = config_protect.check(inp)
        assert action == "block"

    def test_override_empty_string_still_blocks(self, config_protect):
        """ECW_ALLOW_CONFIG_EDIT='' should NOT bypass protection."""
        inp = _make_input("/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {"ECW_ALLOW_CONFIG_EDIT": ""}):
            action, _ = config_protect.check(inp)
        assert action == "block"

    def test_override_with_whitespace(self, config_protect):
        """ECW_ALLOW_CONFIG_EDIT=' 1 ' (with spaces) should bypass."""
        inp = _make_input("/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {"ECW_ALLOW_CONFIG_EDIT": " 1 "}):
            action, _ = config_protect.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# PROTECTED_BASENAMES Integrity
# ══════════════════════════════════════════════════════

class TestProtectedBasenamesIntegrity:
    """Verify the protected file list is well-formed."""

    def test_all_entries_are_strings(self, config_protect):
        for entry in config_protect.PROTECTED_BASENAMES:
            assert isinstance(entry, str), f"Expected str, got {type(entry)}: {entry}"

    def test_minimum_protected_count(self, config_protect):
        """The 4 core ECW config files must be protected."""
        required = {"ecw.yml", "domain-registry.md", "change-risk-classification.md",
                     "ecw-path-mappings.md"}
        assert required == config_protect.PROTECTED_BASENAMES

    def test_no_duplicate_entries(self, config_protect):
        # PROTECTED_BASENAMES is a set, so duplicates are impossible by construction,
        # but verify it stays a set (not accidentally converted to list).
        assert isinstance(config_protect.PROTECTED_BASENAMES, set)


# ══════════════════════════════════════════════════════
# EDITABLE_PATH_PREFIXES Whitelist (v0.7+)
# ══════════════════════════════════════════════════════

class TestEditablePathPrefixes:
    """Verify that files under EDITABLE_PATH_PREFIXES bypass protection."""

    def test_knowledge_file_passes(self, config_protect):
        """Files under .claude/knowledge/ are editable (used by biz-impact auto-backfill)."""
        inp = _make_input("/fake/project/.claude/knowledge/common/cross-domain-calls.md")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_session_data_file_passes(self, config_protect):
        """Files under .claude/ecw/session-data/ are editable (auto-generated artifacts)."""
        inp = _make_input("/fake/project/.claude/ecw/session-data/wf-001/session-state.md")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_plans_file_passes(self, config_protect):
        """Files under .claude/plans/ are editable (generated by writing-plans)."""
        inp = _make_input("/fake/project/.claude/plans/impl-plan.md")
        action, message = config_protect.check(inp)
        assert action == "continue"
        assert message == ""

    def test_protected_basename_under_editable_prefix_passes(self, config_protect):
        """Whitelist takes priority over basename check — ecw.yml under knowledge/ passes."""
        inp = _make_input("/fake/project/.claude/knowledge/ecw.yml")
        action, _ = config_protect.check(inp)
        assert action == "continue"

    def test_ecw_config_not_in_editable_prefix_still_blocked(self, config_protect):
        """ecw.yml under .claude/ecw/ (not in editable prefix) is still blocked."""
        inp = _make_input("/fake/project/.claude/ecw/ecw.yml")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_CONFIG_EDIT", None)
            action, _ = config_protect.check(inp)
        assert action == "block"

    def test_editable_prefix_constant_completeness(self, config_protect):
        """EDITABLE_PATH_PREFIXES must contain exactly the 3 expected prefixes."""
        expected = {".claude/knowledge/", ".claude/ecw/session-data/", ".claude/plans/"}
        assert set(config_protect.EDITABLE_PATH_PREFIXES) == expected
