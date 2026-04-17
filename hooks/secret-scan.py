#!/usr/bin/env python3
"""ECW secret-scan sub-hook — detect secrets and sensitive data in Edit/Write content.

Dispatcher sub-module registered in SUB_HOOKS for PreToolUse on Edit/Write events.
Scans file content for AWS keys, generic secrets, private keys, JWTs, GitHub tokens,
and warns when writing to sensitive file types (.env, .pem, .key, credentials).

Override: set ECW_ALLOW_SECRETS=1 environment variable to bypass scanning.
"""

import os
import re

# ── Secret detection patterns ──
# (compiled_regex, label, severity)
# severity: "block" = hard stop, "warn" = advisory message

SECRET_PATTERNS = [
    (re.compile(r'(?:AKIA|ASIA)[A-Z0-9]{16}'), "AWS Access Key", "block"),
    (re.compile(r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----'), "Private Key", "block"),
    (re.compile(r'ghp_[A-Za-z0-9_]{36,}'), "GitHub Personal Access Token", "block"),
    (re.compile(r'gho_[A-Za-z0-9_]{36,}'), "GitHub OAuth Token", "block"),
    (re.compile(r'ghu_[A-Za-z0-9_]{36,}'), "GitHub User-to-Server Token", "block"),
    (re.compile(r'ghs_[A-Za-z0-9_]{36,}'), "GitHub Server-to-Server Token", "block"),
    (re.compile(r'ghr_[A-Za-z0-9_]{36,}'), "GitHub Refresh Token", "block"),
    (
        re.compile(
            r'(?:password|passwd|secret|api_key|apikey|access_key|secret_key)'
            r'\s*[=:]\s*["\'][^\s"\']{8,}["\']',
            re.IGNORECASE,
        ),
        "Hardcoded Secret Assignment",
        "block",
    ),
    (
        re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
        "JWT Token",
        "warn",
    ),
]

# ── Sensitive file basenames / extensions ──
# Writing to these files produces an advisory warning.

SENSITIVE_BASENAMES = {".env", "credentials", "credentials.json", ".npmrc", ".pypirc"}
SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}

BLOCK_MSG_TEMPLATE = (
    "**[ECW Secret Scan]** Detected `{label}` in content being written to `{filepath}`. "
    "Secrets must not be committed to code. Use environment variables, "
    "a secrets manager, or a configuration center instead. "
    "If this is a false positive, set ECW_ALLOW_SECRETS=1 to bypass."
)

WARN_SENSITIVE_FILE = (
    "**[ECW Secret Scan]** Writing to sensitive file `{filepath}`. "
    "Verify this file is in .gitignore and does not contain real credentials."
)


def _extract_content(input_data):
    """Extract the content being written from Edit or Write tool input."""
    tool_input = input_data.get("tool_input", {})
    tool_name = input_data.get("tool_name", "")

    if tool_name == "Write":
        return tool_input.get("content", "")
    elif tool_name == "Edit":
        return tool_input.get("new_string", "")
    return ""


def check(input_data, config=None):
    """Check Edit/Write content for secrets and sensitive file targets.

    Args:
        input_data: Hook input dict with tool_name, tool_input, cwd.
        config: ECW config dict (unused by this sub-hook).

    Returns:
        ("block", message) if a blocking secret is detected.
        ("continue", message) if only warnings.
        ("continue", "") if clean.
    """
    if os.environ.get("ECW_ALLOW_SECRETS", "").strip() == "1":
        return ("continue", "")

    file_path = input_data.get("tool_input", {}).get("file_path", "")
    content = _extract_content(input_data)

    warnings = []

    # 1. Check content for secret patterns
    if content:
        for pattern, label, severity in SECRET_PATTERNS:
            if pattern.search(content):
                display_path = os.path.basename(file_path) if file_path else "<unknown>"
                if severity == "block":
                    return ("block", BLOCK_MSG_TEMPLATE.format(
                        label=label, filepath=display_path
                    ))
                warnings.append(f"Possible {label} detected in `{display_path}`")

    # 2. Check sensitive file target
    if file_path:
        basename = os.path.basename(file_path).lower()
        _, ext = os.path.splitext(basename)
        if basename in SENSITIVE_BASENAMES or ext in SENSITIVE_EXTENSIONS:
            warnings.append(WARN_SENSITIVE_FILE.format(filepath=basename))

    if warnings:
        return ("continue", "\n".join(warnings))

    return ("continue", "")
