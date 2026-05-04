"""Unit tests for hooks/secret-scan.py

Covers secret pattern detection, sensitive file warnings, override mechanism,
and edge cases for the secret-scan sub-hook.
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
def secret_scan():
    """Import secret-scan.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "secret_scan",
        HOOKS_DIR / "secret-scan.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_write_input(file_path, content):
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "cwd": "/fake/project",
    }


def _make_edit_input(file_path, new_string):
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": new_string, "old_string": "old"},
        "cwd": "/fake/project",
    }


# ══════════════════════════════════════════════════════
# AWS Key Detection
# ══════════════════════════════════════════════════════

class TestAWSKeyDetection:

    def test_akia_key_blocked(self, secret_scan):
        inp = _make_write_input("/project/config.py", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"
        assert "AWS Access Key" in msg

    def test_asia_key_blocked(self, secret_scan):
        inp = _make_edit_input("/project/config.py", 'key = "ASIAXXXXXXXXXEXAMPLE1"')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"
        assert "AWS Access Key" in msg


# ══════════════════════════════════════════════════════
# Private Key Detection
# ══════════════════════════════════════════════════════

class TestPrivateKeyDetection:

    def test_rsa_private_key_blocked(self, secret_scan):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow..."
        inp = _make_write_input("/project/cert.pem", content)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"
        assert "Private Key" in msg

    def test_ec_private_key_blocked(self, secret_scan):
        content = "-----BEGIN EC PRIVATE KEY-----\nMHQCAQ..."
        inp = _make_write_input("/project/key.pem", content)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"

    def test_generic_private_key_blocked(self, secret_scan):
        content = "-----BEGIN PRIVATE KEY-----\nMIIEow..."
        inp = _make_write_input("/project/key.pem", content)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"


# ══════════════════════════════════════════════════════
# GitHub Token Detection
# ══════════════════════════════════════════════════════

class TestGitHubTokenDetection:

    @pytest.mark.parametrize("prefix", ["ghp_", "gho_", "ghu_", "ghs_", "ghr_"])
    def test_github_token_blocked(self, secret_scan, prefix):
        token = prefix + "A" * 40
        inp = _make_write_input("/project/config.js", f'const TOKEN = "{token}";')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"
        assert "GitHub" in msg


# ══════════════════════════════════════════════════════
# Generic Secret Detection
# ══════════════════════════════════════════════════════

class TestGenericSecretDetection:

    @pytest.mark.parametrize("keyword", ["password", "secret", "api_key", "apikey", "access_key"])
    def test_hardcoded_secret_assignment_blocked(self, secret_scan, keyword):
        inp = _make_write_input("/project/app.py", f'{keyword} = "super_secret_value_here"')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "block"
        assert "Hardcoded Secret" in msg or "Secret" in msg

    def test_short_value_not_matched(self, secret_scan):
        """Values shorter than 8 chars should not trigger."""
        inp = _make_write_input("/project/app.py", 'password = "short"')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, _ = secret_scan.check(inp)
        assert action == "continue"

    def test_env_var_reference_not_matched(self, secret_scan):
        """os.environ.get('PASSWORD') should not trigger."""
        inp = _make_write_input("/project/app.py", "password = os.environ.get('PASSWORD')")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, _ = secret_scan.check(inp)
        assert action == "continue"


# ══════════════════════════════════════════════════════
# JWT Detection (warn, not block)
# ══════════════════════════════════════════════════════

class TestJWTDetection:

    def test_jwt_produces_warning_not_block(self, secret_scan):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        inp = _make_write_input("/project/test.py", f'token = "{jwt}"')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert "JWT" in msg


# ══════════════════════════════════════════════════════
# Sensitive File Warnings
# ══════════════════════════════════════════════════════

class TestSensitiveFileWarnings:

    @pytest.mark.parametrize("filename", [".env", "credentials", "credentials.json", ".npmrc"])
    def test_sensitive_file_warned(self, secret_scan, filename):
        inp = _make_write_input(f"/project/{filename}", "SAFE_CONTENT=hello")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert "sensitive file" in msg.lower() or "Sensitive" in msg or "sensitive" in msg

    @pytest.mark.parametrize("ext", [".pem", ".key", ".p12", ".pfx"])
    def test_sensitive_extension_warned(self, secret_scan, ext):
        inp = _make_write_input(f"/project/server{ext}", "safe content")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_ALLOW_SECRETS", None)
            action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert msg  # Some warning produced


# ══════════════════════════════════════════════════════
# Override Mechanism
# ══════════════════════════════════════════════════════

class TestAllowSecretsOverride:

    def test_override_bypasses_detection(self, secret_scan):
        inp = _make_write_input("/project/config.py", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')
        with patch.dict(os.environ, {"ECW_ALLOW_SECRETS": "1"}):
            action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_override_0_still_detects(self, secret_scan):
        inp = _make_write_input("/project/config.py", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"')
        with patch.dict(os.environ, {"ECW_ALLOW_SECRETS": "0"}):
            action, _ = secret_scan.check(inp)
        assert action == "block"


# ══════════════════════════════════════════════════════
# Clean Content Passthrough
# ══════════════════════════════════════════════════════

class TestCleanContent:

    def test_normal_code_passes(self, secret_scan):
        inp = _make_write_input("/project/App.java", 'public class App { }')
        action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert msg == ""

    def test_empty_content_passes(self, secret_scan):
        inp = _make_write_input("/project/empty.py", "")
        action, msg = secret_scan.check(inp)
        assert action == "continue"

    def test_no_file_path_passes(self, secret_scan):
        inp = {"tool_name": "Write", "tool_input": {"content": "x"}, "cwd": "/fake"}
        action, msg = secret_scan.check(inp)
        assert action == "continue"

    def test_edit_new_string_scanned(self, secret_scan):
        """Edit tool should scan new_string, not old_string."""
        inp = _make_edit_input("/project/app.py", 'normal code here')
        action, msg = secret_scan.check(inp)
        assert action == "continue"
        assert msg == ""
