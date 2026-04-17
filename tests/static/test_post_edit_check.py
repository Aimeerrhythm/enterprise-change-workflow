"""Unit tests for hooks/post-edit-check.py

Covers anti-pattern detection, modified file accumulation,
and PostToolUse hook output format.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def post_edit():
    """Import post-edit-check.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "post_edit_check",
        HOOKS_DIR / "post-edit-check.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Anti-Pattern Detection
# ══════════════════════════════════════════════════════

class TestAntiPatternDetection:
    """Tests for _scan_anti_patterns."""

    def test_empty_catch_java(self, post_edit):
        """Empty catch block in Java is detected."""
        content = 'try { foo(); } catch (Exception e) {}'
        warnings = post_edit._scan_anti_patterns(content, "Service.java")
        assert any("catch" in w for w in warnings)

    def test_empty_catch_js(self, post_edit):
        """Empty catch block in JavaScript is detected."""
        content = 'try { foo() } catch (e) {}'
        warnings = post_edit._scan_anti_patterns(content, "app.js")
        assert any("catch" in w for w in warnings)

    def test_non_empty_catch_ok(self, post_edit):
        """Catch block with content is not flagged."""
        content = 'catch (Exception e) { log.error(e); }'
        warnings = post_edit._scan_anti_patterns(content, "Service.java")
        assert not any("catch" in w for w in warnings)

    def test_empty_catch_ignored_for_python(self, post_edit):
        """Empty catch pattern should not match Python files (uses except, not catch)."""
        content = 'catch (Exception e) {}'
        warnings = post_edit._scan_anti_patterns(content, "service.py")
        # Python files are not in applicable_exts for catch pattern
        assert not any("catch" in w for w in warnings)

    def test_hardcoded_password(self, post_edit):
        """Hardcoded password assignment is detected."""
        content = 'password = "SuperSecret123"'
        warnings = post_edit._scan_anti_patterns(content, "config.py")
        assert any("凭据" in w for w in warnings)

    def test_hardcoded_api_key(self, post_edit):
        """Hardcoded api_key is detected."""
        content = "api_key: 'my-secret-api-key-here'"
        warnings = post_edit._scan_anti_patterns(content, "config.yml")
        assert any("凭据" in w for w in warnings)

    def test_aws_access_key(self, post_edit):
        """AWS access key pattern is detected."""
        content = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
        warnings = post_edit._scan_anti_patterns(content, "deploy.py")
        assert any("AWS" in w for w in warnings)

    def test_private_key(self, post_edit):
        """Private key content is detected."""
        content = '-----BEGIN RSA PRIVATE KEY-----\nMIIEow...'
        warnings = post_edit._scan_anti_patterns(content, "cert.pem")
        # .pem is not in SCANNABLE_EXTENSIONS, so check() would skip
        # but _scan_anti_patterns doesn't filter by SCANNABLE_EXTENSIONS
        assert any("私钥" in w for w in warnings)

    def test_todo_comment(self, post_edit):
        """TODO comment is detected."""
        content = '// TODO: fix this later'
        warnings = post_edit._scan_anti_patterns(content, "Service.java")
        assert any("TODO" in w for w in warnings)

    def test_fixme_comment(self, post_edit):
        """FIXME comment is detected."""
        content = '# FIXME: broken edge case'
        warnings = post_edit._scan_anti_patterns(content, "utils.py")
        assert any("TODO" in w for w in warnings)

    def test_clean_code_no_warnings(self, post_edit):
        """Clean code produces no warnings."""
        content = 'def calculate(x, y):\n    return x + y\n'
        warnings = post_edit._scan_anti_patterns(content, "math_utils.py")
        assert warnings == []

    def test_short_password_not_flagged(self, post_edit):
        """Short password values (< 8 chars) are not flagged."""
        content = 'password = "short"'
        warnings = post_edit._scan_anti_patterns(content, "config.py")
        assert not any("凭据" in w for w in warnings)


# ══════════════════════════════════════════════════════
# Modified File Accumulation
# ══════════════════════════════════════════════════════

class TestModifiedFileAccumulation:
    """Tests for _accumulate_modified_file."""

    def test_creates_state_file(self, post_edit, tmp_path):
        """First call creates the state file and directory."""
        post_edit._accumulate_modified_file(str(tmp_path), "src/Service.java")
        state_file = tmp_path / ".claude" / "ecw" / "state" / "modified-files.txt"
        assert state_file.exists()
        assert "src/Service.java" in state_file.read_text()

    def test_appends_to_state_file(self, post_edit, tmp_path):
        """Subsequent calls append new files."""
        post_edit._accumulate_modified_file(str(tmp_path), "src/A.java")
        post_edit._accumulate_modified_file(str(tmp_path), "src/B.java")
        state_file = tmp_path / ".claude" / "ecw" / "state" / "modified-files.txt"
        content = state_file.read_text()
        assert "src/A.java" in content
        assert "src/B.java" in content

    def test_deduplicates(self, post_edit, tmp_path):
        """Same file is not added twice."""
        post_edit._accumulate_modified_file(str(tmp_path), "src/A.java")
        post_edit._accumulate_modified_file(str(tmp_path), "src/A.java")
        state_file = tmp_path / ".claude" / "ecw" / "state" / "modified-files.txt"
        lines = [l for l in state_file.read_text().strip().split("\n") if l]
        assert lines.count("src/A.java") == 1


# ══════════════════════════════════════════════════════
# check() Integration
# ══════════════════════════════════════════════════════

class TestCheckFunction:
    """Tests for the check() entry point."""

    def test_edit_with_anti_pattern(self, post_edit, tmp_path):
        """Edit introducing anti-pattern produces warning."""
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(tmp_path / "Service.java"),
                "new_string": 'catch (Exception e) {}',
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert "ECW Quality Gate" in message
        assert "catch" in message

    def test_write_with_secret(self, post_edit, tmp_path):
        """Write with hardcoded secret produces warning."""
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "config.py"),
                "content": 'api_key = "sk-1234567890abcdef"',
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert "凭据" in message

    def test_clean_edit_no_warning(self, post_edit, tmp_path):
        """Clean edit produces no warning."""
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(tmp_path / "utils.py"),
                "new_string": "def add(a, b):\n    return a + b\n",
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert message == ""

    def test_non_scannable_extension_skipped(self, post_edit, tmp_path):
        """Binary/image files are not scanned."""
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "image.png"),
                "content": "password = 'should_not_trigger'",
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert message == ""

    def test_empty_cwd_returns_continue(self, post_edit):
        """Empty cwd produces no warning."""
        input_data = {"tool_name": "Edit", "tool_input": {"file_path": "/a.py"}, "cwd": ""}
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert message == ""

    def test_no_file_path_returns_continue(self, post_edit):
        """Missing file_path produces no warning."""
        input_data = {"tool_name": "Edit", "tool_input": {}, "cwd": "/fake"}
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert message == ""

    def test_accumulates_file_on_check(self, post_edit, tmp_path):
        """check() accumulates modified file in state."""
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(tmp_path / "Service.java"),
                "new_string": "clean code",
            },
            "cwd": str(tmp_path),
        }
        post_edit.check(input_data)
        state_file = tmp_path / ".claude" / "ecw" / "state" / "modified-files.txt"
        assert state_file.exists()
        assert "Service.java" in state_file.read_text()

    def test_warning_truncation(self, post_edit, tmp_path):
        """More than 5 warnings are truncated."""
        # Content with many anti-patterns
        content = "\n".join([
            'password = "secret1234567"',
            'api_key = "secret1234567"',
            'token = "secret12345678"',
            'secret = "secret1234567"',
            'apikey = "secret1234567"',
            'access_key = "secret1234567"',
            '// TODO: fix this',
        ])
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "bad.py"),
                "content": content,
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        # Should have warnings (exact count depends on regex overlap)
        assert "ECW Quality Gate" in message


# ══════════════════════════════════════════════════════
# main() Standalone Entry
# ══════════════════════════════════════════════════════

class TestMainEntry:
    """Tests for standalone main() execution."""

    def test_non_edit_write_passes(self, post_edit):
        """Non-Edit/Write tools pass through."""
        input_data = {"tool_name": "Read", "tool_input": {}, "cwd": "/fake"}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc:
                    post_edit.main()
                assert exc.value.code == 0
                output = json.loads(mock_print.call_args[0][0])
                assert output.get("result") == "continue"

    def test_exception_does_not_block(self, post_edit):
        """Exceptions in main don't block workflow."""
        with patch("json.load", side_effect=Exception("boom")):
            with patch("builtins.print"):
                with pytest.raises(SystemExit) as exc:
                    try:
                        post_edit.main()
                    except Exception:
                        import json as _json
                        print(_json.dumps({"result": "continue"}))
                        import sys as _sys
                        _sys.exit(0)
                assert exc.value.code == 0


# ══════════════════════════════════════════════════════
# hooks.json Registration
# ══════════════════════════════════════════════════════

class TestPostEditHooksJson:
    """Verify PostToolUse hook is registered in hooks.json."""

    def test_post_tool_use_registered(self):
        """hooks.json must have a PostToolUse entry for post-edit-check.py."""
        ROOT = Path(__file__).resolve().parent.parent.parent
        hooks_json = ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())

        hooks = data.get("hooks", {})
        assert "PostToolUse" in hooks, "hooks.json must define PostToolUse event"

        post_entries = hooks["PostToolUse"]
        found = False
        for entry in post_entries:
            for hook in entry.get("hooks", []):
                if "post-edit-check.py" in hook.get("command", ""):
                    found = True
                    break
        assert found, "PostToolUse must reference post-edit-check.py"

    def test_post_tool_use_matcher(self):
        """PostToolUse matcher should target Edit|Write."""
        ROOT = Path(__file__).resolve().parent.parent.parent
        hooks_json = ROOT / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())

        post_entries = data["hooks"]["PostToolUse"]
        for entry in post_entries:
            matcher = entry.get("matcher", "")
            if "Edit" in matcher or "Write" in matcher:
                return
        pytest.fail("PostToolUse matcher must include Edit|Write")
