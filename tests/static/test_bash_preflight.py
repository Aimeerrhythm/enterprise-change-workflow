"""Unit tests for hooks/bash-preflight.py

Covers dangerous command blocking, warning patterns, override mechanism,
safe command passthrough, and edge cases.
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
def bash_preflight():
    """Import bash-preflight.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "bash_preflight",
        HOOKS_DIR / "bash-preflight.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_input(command):
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": "/fake/project",
    }


# ══════════════════════════════════════════════════════
# Blocked: --no-verify
# ══════════════════════════════════════════════════════

class TestNoVerifyBlocking:

    def test_git_commit_no_verify_blocked(self, bash_preflight):
        inp = _make_input("git commit --no-verify -m 'skip hooks'")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "--no-verify" in msg

    def test_git_push_no_verify_blocked(self, bash_preflight):
        inp = _make_input("git push --no-verify origin main")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"


# ══════════════════════════════════════════════════════
# Blocked: Force Push
# ══════════════════════════════════════════════════════

class TestForcePushBlocking:

    def test_force_push_long_flag_blocked(self, bash_preflight):
        inp = _make_input("git push --force origin main")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "force" in msg.lower()

    def test_force_push_short_flag_blocked(self, bash_preflight):
        inp = _make_input("git push -f origin main")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"

    def test_force_with_lease_allowed(self, bash_preflight):
        """--force-with-lease is the safe alternative and must NOT be blocked."""
        inp = _make_input("git push --force-with-lease origin feature")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_force_with_lease_no_warning(self, bash_preflight):
        """--force-with-lease should produce no warning at all."""
        inp = _make_input("git push --force-with-lease origin feature")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_force_push_tag_long_warned(self, bash_preflight):
        """Force-pushing a tag (v1.0.0) should warn but not block."""
        inp = _make_input("git push --force origin v1.0.0")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg  # Should have a warning

    def test_force_push_tag_short_warned(self, bash_preflight):
        """Force-pushing a tag with -f should warn but not block."""
        inp = _make_input("git push -f origin v2.3.1")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg

    def test_force_push_refs_tags_warned(self, bash_preflight):
        """Force-pushing refs/tags/ should warn but not block."""
        inp = _make_input("git push --force origin refs/tags/v1.0")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg

    def test_force_push_branch_still_blocked(self, bash_preflight):
        """Force-pushing a branch must still be blocked after tag fix."""
        inp = _make_input("git push --force origin feature-x")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"

    def test_force_delete_tag_not_affected(self, bash_preflight):
        """git push --delete should not be affected by force-push rules."""
        inp = _make_input("git push --delete origin v1.0.0")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Blocked: Hard Reset
# ══════════════════════════════════════════════════════

class TestHardResetBlocking:

    def test_git_reset_hard_blocked(self, bash_preflight):
        inp = _make_input("git reset --hard HEAD~1")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "reset" in msg.lower()

    def test_git_reset_soft_not_blocked(self, bash_preflight):
        inp = _make_input("git reset --soft HEAD~1")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Blocked: Hooks Path Override
# ══════════════════════════════════════════════════════

class TestHooksPathBlocking:

    def test_core_hookspath_blocked(self, bash_preflight):
        inp = _make_input("git config core.hooksPath /dev/null")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "hooksPath" in msg


# ══════════════════════════════════════════════════════
# Blocked: git clean -f
# ══════════════════════════════════════════════════════

class TestGitCleanBlocking:

    def test_git_clean_f_blocked(self, bash_preflight):
        inp = _make_input("git clean -fd")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"

    def test_git_clean_dry_run_not_blocked(self, bash_preflight):
        inp = _make_input("git clean -n")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Warning: rm -rf
# ══════════════════════════════════════════════════════

class TestRmRfWarning:

    def test_rm_rf_warned(self, bash_preflight):
        inp = _make_input("rm -rf /tmp/build")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert "rm -rf" in msg

    def test_rm_fr_warned(self, bash_preflight):
        """rm -fr is equivalent to rm -rf."""
        inp = _make_input("rm -fr ./dist")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg  # Warning produced


# ══════════════════════════════════════════════════════
# Warning: SQL Operations
# ══════════════════════════════════════════════════════

class TestSQLWarnings:

    def test_drop_table_warned(self, bash_preflight):
        inp = _make_input("mysql -e 'DROP TABLE users'")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert "DROP" in msg

    def test_delete_from_warned(self, bash_preflight):
        inp = _make_input("psql -c 'DELETE FROM orders'")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert "DELETE" in msg

    def test_truncate_warned(self, bash_preflight):
        inp = _make_input("psql -c 'TRUNCATE TABLE logs'")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert "TRUNCATE" in msg


# ══════════════════════════════════════════════════════
# Override Mechanism
# ══════════════════════════════════════════════════════

class TestOverride:

    def test_override_bypasses_block(self, bash_preflight):
        inp = _make_input("git push --force origin main")
        with patch.dict(os.environ, {"ECW_ALLOW_DANGEROUS_CMD": "1"}):
            action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_override_0_still_blocks(self, bash_preflight):
        inp = _make_input("git push --force origin main")
        with patch.dict(os.environ, {"ECW_ALLOW_DANGEROUS_CMD": "0"}):
            action, _ = bash_preflight.check(inp)
        assert action == "block"


# ══════════════════════════════════════════════════════
# Safe Command Passthrough
# ══════════════════════════════════════════════════════

class TestSafeCommands:

    @pytest.mark.parametrize("cmd", [
        "git status",
        "git diff",
        "git log --oneline -10",
        "git branch -a",
        "ls -la",
        "npm install",
        "python3 -m pytest",
        "make build",
        "mvn clean package",
        "echo hello",
    ])
    def test_safe_commands_pass(self, bash_preflight, cmd):
        inp = _make_input(cmd)
        action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_empty_command_passes(self, bash_preflight):
        inp = _make_input("")
        action, msg = bash_preflight.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_missing_command_key_passes(self, bash_preflight):
        inp = {"tool_name": "Bash", "tool_input": {}, "cwd": "/fake"}
        action, msg = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Pattern Integrity
# ══════════════════════════════════════════════════════

class TestPatternIntegrity:

    def test_blocked_patterns_are_compiled_regex(self, bash_preflight):
        for pattern, label, guidance in bash_preflight.BLOCKED_PATTERNS:
            assert hasattr(pattern, "search"), f"Pattern for '{label}' is not a compiled regex"

    def test_warn_patterns_are_compiled_regex(self, bash_preflight):
        for pattern, label, guidance in bash_preflight.WARN_PATTERNS:
            assert hasattr(pattern, "search"), f"Pattern for '{label}' is not a compiled regex"
