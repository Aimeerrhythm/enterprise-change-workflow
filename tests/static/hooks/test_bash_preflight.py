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

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


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


# ══════════════════════════════════════════════════════
# Blocked: sed -i bypass of gateguard
# ══════════════════════════════════════════════════════

JAVA_CONFIG = {"hooks": {"gateguard_extensions": [".java"]}}


class TestSedBypassBlocking:

    def test_sed_i_java_blocked(self, bash_preflight):
        inp = _make_input("sed -i '' 's/old/new/' src/Service.java")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp, JAVA_CONFIG)
        assert action == "block"
        assert "sed -i" in msg
        assert ".java" in msg

    def test_sed_i_non_guarded_passes(self, bash_preflight):
        inp = _make_input("sed -i '' 's/old/new/' README.md")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_sed_i_no_config_passes(self, bash_preflight):
        inp = _make_input("sed -i '' 's/old/new/' Service.java")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_sed_i_empty_extensions_passes(self, bash_preflight):
        inp = _make_input("sed -i '' 's/old/new/' Service.java")
        config = {"hooks": {"gateguard_extensions": []}}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp, config)
        assert action == "continue"

    def test_sed_without_i_passes(self, bash_preflight):
        inp = _make_input("sed 's/old/new/' Service.java")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_sed_i_piped_to_java(self, bash_preflight):
        inp = _make_input("sed -i 's/foo/bar/g' src/main/java/App.java")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp, JAVA_CONFIG)
        assert action == "block"


# ══════════════════════════════════════════════════════
# Stale Diff Range Detection
# ══════════════════════════════════════════════════════

SESSION_STATE_WITH_BASELINE = """\
<!-- ECW:STATUS:START -->
- **Risk Level**: P1
- **Baseline Commit**: abc1234567890def
<!-- ECW:STATUS:END -->
"""

SESSION_STATE_NO_BASELINE = """\
<!-- ECW:STATUS:START -->
- **Risk Level**: P1
- **Baseline Commit**: TBD
<!-- ECW:STATUS:END -->
"""


class TestStaleDiffRange:

    def _make_cwd_input(self, command, cwd):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}

    def _write_session_state(self, tmp_path, content):
        state_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260430-test"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text(content)

    def test_master_head_blocked_when_baseline_present(self, bash_preflight, tmp_path):
        self._write_session_state(tmp_path, SESSION_STATE_WITH_BASELINE)
        inp = self._make_cwd_input("git diff --stat master...HEAD", str(tmp_path))
        action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "abc1234567890def" in msg

    def test_block_message_contains_corrected_command(self, bash_preflight, tmp_path):
        self._write_session_state(tmp_path, SESSION_STATE_WITH_BASELINE)
        inp = self._make_cwd_input("git diff --name-only master...HEAD", str(tmp_path))
        action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "abc1234567890def...HEAD" in msg

    def test_no_session_passes_through(self, bash_preflight, tmp_path):
        inp = self._make_cwd_input("git diff master...HEAD", str(tmp_path))
        action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_tbd_baseline_passes_through(self, bash_preflight, tmp_path):
        self._write_session_state(tmp_path, SESSION_STATE_NO_BASELINE)
        inp = self._make_cwd_input("git diff master...HEAD", str(tmp_path))
        action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_explicit_hash_not_blocked(self, bash_preflight, tmp_path):
        self._write_session_state(tmp_path, SESSION_STATE_WITH_BASELINE)
        inp = self._make_cwd_input("git diff abc999...HEAD", str(tmp_path))
        action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_git_log_not_affected(self, bash_preflight, tmp_path):
        self._write_session_state(tmp_path, SESSION_STATE_WITH_BASELINE)
        inp = self._make_cwd_input("git log master...HEAD", str(tmp_path))
        action, _ = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Fix Gate: hooks/*.py changed without tests/
# ══════════════════════════════════════════════════════

class TestHookCommitGate:

    def _make_cwd_input(self, command, cwd):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}

    def _staged(self, files):
        """Return a mock subprocess.run that returns the given staged file list."""
        from unittest.mock import MagicMock
        result = MagicMock()
        result.returncode = 0
        result.stdout = "\n".join(files) + "\n"
        return result

    def test_hook_staged_no_test_blocks(self, bash_preflight, tmp_path):
        """hooks/foo.py staged, no tests/static/ staged → block."""
        inp = self._make_cwd_input("git commit -m 'fix: something'", tmp_path)
        with patch("subprocess.run", return_value=self._staged(["hooks/verify-completion.py"])):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "Fix Gate" in msg
        assert "verify-completion.py" in msg

    def test_hook_staged_with_test_passes(self, bash_preflight, tmp_path):
        """hooks/foo.py + tests/static/test_foo.py both staged → continue."""
        inp = self._make_cwd_input("git commit -m 'fix: with test'", tmp_path)
        staged = ["hooks/verify-completion.py", "tests/static/test_verify_completion.py"]
        with patch("subprocess.run", return_value=self._staged(staged)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_hook_staged_with_subdir_test_passes(self, bash_preflight, tmp_path):
        """hooks/foo.py + tests/static/hooks/test_foo.py (subdir) both staged → continue."""
        inp = self._make_cwd_input("git commit -m 'fix: with subdir test'", tmp_path)
        staged = ["hooks/verify-completion.py", "tests/static/hooks/test_verify_completion.py"]
        with patch("subprocess.run", return_value=self._staged(staged)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_non_hook_change_not_flagged(self, bash_preflight, tmp_path):
        """skills/ or SKILL.md changes alone don't trigger the hook gate."""
        inp = self._make_cwd_input("git commit -m 'step 1'", tmp_path)
        with patch("subprocess.run", return_value=self._staged(["skills/tdd/SKILL.md"])):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_non_commit_command_not_checked(self, bash_preflight, tmp_path):
        """git push / git status don't trigger the gate."""
        for cmd in ["git push origin main", "git status", "git log -5"]:
            inp = self._make_cwd_input(cmd, tmp_path)
            with patch("subprocess.run", return_value=self._staged(["hooks/foo.py"])):
                os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
                action, _ = bash_preflight.check(inp)
            assert action == "continue", f"Should not block: {cmd}"

    def test_override_bypasses_hook_gate(self, bash_preflight, tmp_path):
        """ECW_ALLOW_DANGEROUS_CMD=1 bypasses the fix gate."""
        inp = self._make_cwd_input("git commit -m 'emergency'", tmp_path)
        with patch("subprocess.run", return_value=self._staged(["hooks/auto-continue.py"])):
            with patch.dict(os.environ, {"ECW_ALLOW_DANGEROUS_CMD": "1"}):
                action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_empty_staged_passes(self, bash_preflight, tmp_path):
        """Nothing staged (e.g. empty commit) → no block."""
        inp = self._make_cwd_input("git commit --allow-empty -m 'chore'", tmp_path)
        with patch("subprocess.run", return_value=self._staged([])):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# Eval Gate: SKILL.md behavioral change without fresh stamp
# ══════════════════════════════════════════════════════

class TestSkillEvalGate:

    _STAMP = os.path.join(".claude", "ecw", "state", "eval-cleared.stamp")

    def _make_cwd_input(self, command, cwd):
        return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}

    def _mock_staged(self, staged_files, diff_content=""):
        """Return side_effect for subprocess.run covering both git diff calls."""
        from unittest.mock import MagicMock
        def _side_effect(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            if "--name-only" in cmd:
                r.stdout = "\n".join(staged_files) + "\n"
            else:
                r.stdout = diff_content
            return r
        return _side_effect

    def test_skill_behavioral_no_stamp_blocks(self, bash_preflight, tmp_path):
        """SKILL.md staged with MUST keyword, no stamp → block."""
        diff = "+## Step\n+MUST invoke downstream skill\n"
        inp = self._make_cwd_input("git commit -m 'step 1'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/tdd/SKILL.md"], diff)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "Eval Gate" in msg
        assert "eval-quick" in msg

    def test_skill_behavioral_fresh_stamp_passes(self, bash_preflight, tmp_path):
        """SKILL.md staged with MUST keyword, stamp newer than file → continue."""
        skill_path = tmp_path / "skills" / "tdd" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("MUST do something")

        stamp_path = tmp_path / ".claude" / "ecw" / "state" / "eval-cleared.stamp"
        stamp_path.parent.mkdir(parents=True)
        stamp_path.write_text("")
        # stamp newer than skill file
        import time
        os.utime(str(stamp_path), (time.time() + 10, time.time() + 10))

        diff = "+MUST invoke downstream skill\n"
        inp = self._make_cwd_input("git commit -m 'step 1'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/tdd/SKILL.md"], diff)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_skill_behavioral_stale_stamp_blocks(self, bash_preflight, tmp_path):
        """stamp older than SKILL.md (edited after eval) → block."""
        skill_path = tmp_path / "skills" / "tdd" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("MUST do something")

        stamp_path = tmp_path / ".claude" / "ecw" / "state" / "eval-cleared.stamp"
        stamp_path.parent.mkdir(parents=True)
        stamp_path.write_text("")
        # stamp older than skill file
        import time
        os.utime(str(stamp_path), (time.time() - 60, time.time() - 60))

        diff = "+MUST invoke downstream skill\n"
        inp = self._make_cwd_input("git commit -m 'step 1'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/tdd/SKILL.md"], diff)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "Eval Gate" in msg

    def test_skill_cosmetic_change_not_blocked(self, bash_preflight, tmp_path):
        """SKILL.md staged but only cosmetic diff (no behavioral keywords) → continue."""
        diff = "+This section explains the background context.\n+See documentation for details.\n"
        inp = self._make_cwd_input("git commit -m 'docs: typo fix'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/tdd/SKILL.md"], diff)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, _ = bash_preflight.check(inp)
        assert action == "continue"

    def test_downstream_handoff_keyword_triggers(self, bash_preflight, tmp_path):
        """'Downstream Handoff' in diff triggers eval gate."""
        diff = "+## Downstream Handoff\n+After completing, route to next skill.\n"
        inp = self._make_cwd_input("git commit -m 'step 2'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/risk-classifier/SKILL.md"], diff)):
            os.environ.pop("ECW_ALLOW_DANGEROUS_CMD", None)
            action, msg = bash_preflight.check(inp)
        assert action == "block"
        assert "Eval Gate" in msg

    def test_override_bypasses_eval_gate(self, bash_preflight, tmp_path):
        """ECW_ALLOW_DANGEROUS_CMD=1 bypasses the eval gate."""
        diff = "+MUST invoke downstream skill\n"
        inp = self._make_cwd_input("git commit -m 'step 1'", tmp_path)
        with patch("subprocess.run", side_effect=self._mock_staged(
                ["skills/tdd/SKILL.md"], diff)):
            with patch.dict(os.environ, {"ECW_ALLOW_DANGEROUS_CMD": "1"}):
                action, _ = bash_preflight.check(inp)
        assert action == "continue"
