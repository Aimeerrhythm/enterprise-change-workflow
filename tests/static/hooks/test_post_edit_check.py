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

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


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


@pytest.fixture
def ecw_project(tmp_path):
    """Create a minimal ECW project structure in tmp_path."""
    ecw_dir = tmp_path / ".claude" / "ecw"
    ecw_dir.mkdir(parents=True)
    (ecw_dir / "ecw.yml").write_text("project:\n  name: test\n")
    return tmp_path


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

class TestSessionStateYamlValidation:
    """post-edit-check must warn when session-state.md contains invalid YAML."""

    @pytest.fixture
    def post_edit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "post_edit_check",
            Path(__file__).resolve().parent.parent.parent.parent / "hooks" / "post-edit-check.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_valid_json_no_warning(self, post_edit, tmp_path):
        """Valid JSON produces no warning."""
        valid_content = '{"risk_level": "P0", "routing": [], "current_phase": "risk-assessment-complete"}'
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "session-state.json"),
                "content": valid_content,
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert "JSON Error" not in message

    def test_invalid_json_status_produces_warning(self, post_edit, ecw_project):
        """Invalid JSON in session-state.json triggers JSON Error warning."""
        invalid_content = '{"risk_level": "P0", "unclosed_array": [unclosed'
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(ecw_project / "session-state.json"),
                "content": invalid_content,
            },
            "cwd": str(ecw_project),
        }
        action, message = post_edit.check(input_data)
        assert action == "continue"
        assert "JSON Error" in message

    def test_non_session_state_file_not_checked(self, post_edit, tmp_path):
        """JSON validation only applies to session-state.json, not other files."""
        invalid_content = '{"bad": [unclosed}'
        input_data = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(tmp_path / "other.json"),
                "content": invalid_content,
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert "JSON Error" not in message

    def test_edit_reads_actual_file_for_validation(self, post_edit, ecw_project):
        """Edit on session-state.json reads the actual file for JSON validation."""
        state_file = ecw_project / "session-state.json"
        state_file.write_text('{"risk_level": "P0", "unclosed_array": [unclosed')
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(state_file),
                "old_string": '"P0"',
                "new_string": '"P1"',
            },
            "cwd": str(ecw_project),
        }
        action, message = post_edit.check(input_data)
        assert "JSON Error" in message

    def test_edit_valid_file_no_warning(self, post_edit, tmp_path):
        """Edit on session-state.json with valid JSON on disk produces no warning."""
        state_file = tmp_path / "session-state.json"
        state_file.write_text('{"risk_level": "P0"}')
        input_data = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(state_file),
                "old_string": '"P0"',
                "new_string": '"P1"',
            },
            "cwd": str(tmp_path),
        }
        action, message = post_edit.check(input_data)
        assert "JSON Error" not in message

