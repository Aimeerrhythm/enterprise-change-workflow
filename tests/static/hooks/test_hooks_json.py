"""Unit tests for ECW hook registration architecture.

Architecture: hooks are no longer registered globally in hooks/hooks.json.
Instead, they are registered per-project via:
  - templates/settings.ecw.json  — hook command template (uses hook-runner.sh)
  - templates/hook-runner.sh     — runtime resolver for ECW plugin path
  - scripts/merge-settings.py    — idempotent merge into .claude/settings.local.json

hooks/hooks.json must be empty (no global registration).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SETTINGS_TEMPLATE = ROOT / "templates" / "settings.ecw.json"
HOOK_RUNNER = ROOT / "templates" / "hook-runner.sh"
MERGE_SCRIPT = ROOT / "scripts" / "merge-settings.py"

REQUIRED_EVENTS = [
    "SessionStart",
    "Stop",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
    "SessionEnd",
]

REQUIRED_SCRIPTS = [
    "session-start.py",
    "stop-persist.py",
    "dispatcher.py",
    "auto-continue.py",
    "eval-gate.py",
    "post-edit-check.py",
    "knowledge-read-logger.py",
    "pre-compact.py",
    "session-end.py",
]


@pytest.fixture
def settings_data():
    assert SETTINGS_TEMPLATE.exists(), f"settings.ecw.json not found at {SETTINGS_TEMPLATE}"
    return json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))


@pytest.fixture
def hooks_data():
    assert HOOKS_JSON.exists(), f"hooks.json not found at {HOOKS_JSON}"
    return json.loads(HOOKS_JSON.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════
# hooks.json must be empty (no global registration)
# ══════════════════════════════════════════════════════

class TestHooksJsonValidity:
    def test_hooks_json_valid(self):
        """hooks.json must be valid JSON with a top-level 'hooks' key."""
        assert HOOKS_JSON.exists(), "hooks.json must exist"
        data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "hooks" in data

    def test_hooks_json_is_empty(self, hooks_data):
        """hooks.json must have an empty hooks object — global registration removed.

        Hooks are now project-scoped via templates/settings.ecw.json.
        Any entry here would activate for ALL projects, defeating the purpose.
        """
        hooks = hooks_data.get("hooks", {})
        assert hooks == {}, (
            "hooks/hooks.json must be empty. "
            "ECW hooks are now registered per-project via scripts/merge-settings.py. "
            f"Found unexpected events: {list(hooks.keys())}"
        )


# ══════════════════════════════════════════════════════
# templates/settings.ecw.json — project-scope hook template
# ══════════════════════════════════════════════════════

class TestSettingsTemplate:
    def test_settings_template_exists(self):
        assert SETTINGS_TEMPLATE.exists(), "templates/settings.ecw.json must exist"

    def test_settings_template_valid_json(self):
        data = json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "hooks" in data

    def test_settings_template_has_all_required_events(self, settings_data):
        hooks = settings_data.get("hooks", {})
        for event in REQUIRED_EVENTS:
            assert event in hooks, f"settings.ecw.json must define '{event}' event"

    def test_settings_template_uses_hook_runner(self, settings_data):
        """All hook commands must use hook-runner.sh (not ${CLAUDE_PLUGIN_ROOT})."""
        hooks = settings_data.get("hooks", {})
        for event, entries in hooks.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    assert "hook-runner.sh" in cmd, (
                        f"{event}: command must use hook-runner.sh, got: {cmd!r}"
                    )
                    assert "CLAUDE_PLUGIN_ROOT" not in cmd, (
                        f"{event}: must not use ${{CLAUDE_PLUGIN_ROOT}} — "
                        f"it is undefined in project-level hooks: {cmd!r}"
                    )

    def test_settings_template_uses_claude_project_dir(self, settings_data):
        """hook-runner.sh path must be anchored with ${CLAUDE_PROJECT_DIR}."""
        hooks = settings_data.get("hooks", {})
        for event, entries in hooks.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "hook-runner.sh" in cmd:
                        assert "CLAUDE_PROJECT_DIR" in cmd, (
                            f"{event}: hook-runner.sh path must use ${{CLAUDE_PROJECT_DIR}}, "
                            f"got: {cmd!r}"
                        )

    def test_settings_template_all_scripts_referenced(self, settings_data):
        """All required hook scripts must appear somewhere in settings.ecw.json."""
        hooks = settings_data.get("hooks", {})
        all_commands = [
            hook.get("command", "")
            for entries in hooks.values()
            for entry in entries
            for hook in entry.get("hooks", [])
        ]
        combined = " ".join(all_commands)
        for script in REQUIRED_SCRIPTS:
            assert script in combined, (
                f"settings.ecw.json must reference '{script}'"
            )

    def test_settings_template_has_permissions(self, settings_data):
        """settings.ecw.json must include ECW write permissions."""
        perms = settings_data.get("permissions", {}).get("allow", [])
        required = [
            "Write(.claude/ecw/**)",
            "Write(.claude/knowledge/**)",
            "Write(.claude/plans/**)",
        ]
        for p in required:
            assert p in perms, f"settings.ecw.json must include permission: {p}"

    def test_all_hooks_have_timeout(self, settings_data):
        hooks = settings_data.get("hooks", {})
        for event, entries in hooks.items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    assert hook.get("timeout") is not None, (
                        f"{event}: hook command must have a timeout: {hook.get('command')!r}"
                    )
                    assert hook["timeout"] > 0


# ══════════════════════════════════════════════════════
# templates/hook-runner.sh
# ══════════════════════════════════════════════════════

class TestHookRunner:
    def test_hook_runner_exists(self):
        assert HOOK_RUNNER.exists(), "templates/hook-runner.sh must exist"

    def test_hook_runner_references_ecw_cache(self):
        content = HOOK_RUNNER.read_text()
        assert "enterprise-change-workflow/ecw" in content, (
            "hook-runner.sh must reference the ECW plugin cache path"
        )

    def test_hook_runner_finds_latest_version(self):
        content = HOOK_RUNNER.read_text()
        assert "sort -V" in content, (
            "hook-runner.sh must sort versions with 'sort -V' to find the latest"
        )

    def test_hook_runner_exits_cleanly_when_no_plugin(self):
        """hook-runner.sh must exit 0 (not error) if ECW plugin is not installed."""
        result = subprocess.run(
            ["bash", str(HOOK_RUNNER), "nonexistent-hook.py"],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": "/nonexistent_home_for_test"},
        )
        assert result.returncode == 0, (
            f"hook-runner.sh must exit 0 when plugin not installed, "
            f"got {result.returncode}: {result.stderr}"
        )


# ══════════════════════════════════════════════════════
# scripts/merge-settings.py
# ══════════════════════════════════════════════════════

class TestMergeSettings:
    def test_merge_script_exists(self):
        assert MERGE_SCRIPT.exists(), "scripts/merge-settings.py must exist"

    def test_merge_creates_settings_json(self, tmp_path):
        """merge-settings.py must create .claude/settings.local.json from template."""
        result = subprocess.run(
            [sys.executable, str(MERGE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"merge-settings.py failed: {result.stderr}"
        out = json.loads(result.stdout)
        assert out["status"] == "created"
        settings_path = tmp_path / ".claude" / "settings.local.json"
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        assert "hooks" in data
        assert "SessionStart" in data["hooks"]

    def test_merge_is_idempotent(self, tmp_path):
        """Running merge-settings.py twice must not change anything on second run."""
        subprocess.run([sys.executable, str(MERGE_SCRIPT), str(tmp_path)], capture_output=True)
        result = subprocess.run(
            [sys.executable, str(MERGE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        out = json.loads(result.stdout)
        assert out["status"] == "unchanged"

    def test_merge_preserves_unrelated_settings(self, tmp_path):
        """merge-settings.py must not overwrite unrelated project settings."""
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir()
        existing = {
            "permissions": {"allow": ["Bash(custom-cmd:*)"]},
            "hooks": {
                "UserPromptSubmit": [{"matcher": "*", "hooks": [{"type": "command", "command": "custom.sh"}]}]
            }
        }
        (settings_dir / "settings.local.json").write_text(json.dumps(existing), encoding="utf-8")

        subprocess.run([sys.executable, str(MERGE_SCRIPT), str(tmp_path)], capture_output=True)

        merged = json.loads((settings_dir / "settings.local.json").read_text())
        assert "Bash(custom-cmd:*)" in merged["permissions"]["allow"]
        assert "UserPromptSubmit" in merged["hooks"]

    def test_merge_installs_hook_runner(self, tmp_path):
        """merge-settings.py must copy hook-runner.sh to .claude/ecw/."""
        subprocess.run([sys.executable, str(MERGE_SCRIPT), str(tmp_path)], capture_output=True)
        runner = tmp_path / ".claude" / "ecw" / "scripts" / "hook-runner.sh"
        assert runner.exists(), ".claude/ecw/scripts/hook-runner.sh must be installed by merge-settings.py"
        assert os.access(runner, os.X_OK), "hook-runner.sh must be executable"


# ══════════════════════════════════════════════════════
# Sub-hook scripts still exist (loaded by dispatcher at runtime)
# ══════════════════════════════════════════════════════

class TestSubHookScripts:
    def test_verify_completion_script_exists(self):
        """verify-completion.py must exist as a dispatcher sub-hook."""
        assert (ROOT / "hooks" / "verify-completion.py").exists()

    def test_dispatcher_script_exists(self):
        assert (ROOT / "hooks" / "dispatcher.py").exists()
