#!/usr/bin/env python3
"""ECW bash-preflight sub-hook — block dangerous shell commands.

Dispatcher sub-module registered in SUB_HOOKS for PreToolUse on Bash events.
Blocks destructive git operations (--no-verify, force push, hard reset) and
warns about dangerous filesystem/database operations (rm -rf, DROP TABLE).

Override: set ECW_ALLOW_DANGEROUS_CMD=1 environment variable to bypass all checks.
"""

import os
import re


def _parse_guarded_extensions(config):
    """Read gateguard_extensions from config, normalize to set of lowercase dotted extensions."""
    if not config:
        return set()
    raw = config.get("hooks", {}).get("gateguard_extensions", [])
    if not raw:
        return set()
    exts = set()
    for e in raw:
        e = str(e).strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        exts.add(e.lower())
    return exts


def _check_sed_bypass(command, config):
    """Detect sed -i targeting files with guarded extensions. Returns block message or None."""
    guarded_exts = _parse_guarded_extensions(config)
    if not guarded_exts:
        return None
    if not re.search(r'\bsed\b.*\s-i', command):
        return None
    for ext in guarded_exts:
        pattern = re.escape(ext)
        if re.search(pattern + r'(?:\s|$|\'|")', command):
            return (
                f"**[ECW Bash Preflight]** Blocked: `sed -i` targeting `*{ext}` file detected.\n\n"
                f"This file type is protected by ECW Gateguard. Use the Edit tool instead of sed, "
                f"so the gateguard hook can verify you've investigated the file first."
            )
    return None

# ── Tag refspec pattern ──
# Matches common tag patterns: v1.0.0, v2.3, refs/tags/...
_TAG_PATTERN = re.compile(
    r'(?:refs/tags/\S+|(?:^|\s)v\d+\.\d+(?:\.\d+)?(?:[-.\w]*)(?:\s|$))'
)

# ── Blocked command patterns ──
# These commands are hard-blocked — the tool call is denied.
# (compiled_regex, label, guidance)

BLOCKED_PATTERNS = [
    (
        re.compile(r'\bgit\b.+--no-verify\b'),
        "--no-verify flag",
        "Pre-commit hooks exist for a reason. Fix the underlying issue instead of bypassing checks.",
    ),
    (
        re.compile(r'\bgit\s+push\b.+--force(?!-with-lease)\b'),
        "git push --force",
        "Force-push can destroy remote history. Use --force-with-lease for safer alternatives.",
    ),
    (
        re.compile(r'\bgit\s+push\b.*\s-f\b'),
        "git push -f",
        "Force-push can destroy remote history. Use --force-with-lease for safer alternatives.",
    ),
    (
        re.compile(r'\bgit\s+reset\s+--hard\b'),
        "git reset --hard",
        "Hard reset discards uncommitted changes permanently. Consider git stash first.",
    ),
    (
        re.compile(r'\bgit\s+config\b.+core\.hooksPath\b'),
        "core.hooksPath override",
        "Overriding hooksPath can disable project safety hooks. This is not allowed.",
    ),
    (
        re.compile(r'\bgit\s+clean\s+-[a-zA-Z]*f'),
        "git clean -f",
        "git clean -f permanently deletes untracked files. Review what will be deleted first with git clean -n.",
    ),
]

# ── Warning patterns ──
# These produce advisory messages but do not block.
# (compiled_regex, label, guidance)

WARN_PATTERNS = [
    (
        re.compile(r'\brm\s+-[a-zA-Z]*r[a-zA-Z]*f\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r\b'),
        "rm -rf",
        "Recursive force-delete is irreversible. Verify the target path carefully.",
    ),
    (
        re.compile(r'\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b', re.IGNORECASE),
        "DROP TABLE/DATABASE",
        "Dropping database objects is irreversible in production. Verify the target environment.",
    ),
    (
        re.compile(r'\bDELETE\s+FROM\b', re.IGNORECASE),
        "DELETE FROM",
        "Bulk delete without WHERE clause can destroy data. Verify the query scope.",
    ),
    (
        re.compile(r'\bTRUNCATE\s+TABLE\b', re.IGNORECASE),
        "TRUNCATE TABLE",
        "Truncate removes all rows without logging. Verify the target table.",
    ),
    (
        re.compile(r'\bchmod\s+777\b'),
        "chmod 777",
        "World-writable permissions are a security risk. Use more restrictive permissions.",
    ),
]

BLOCK_MSG_TEMPLATE = (
    "**[ECW Bash Preflight]** Blocked: `{label}` detected in command.\n\n"
    "{guidance}\n\n"
    "If you need to run this command, ask the user to set ECW_ALLOW_DANGEROUS_CMD=1."
)

WARN_MSG_TEMPLATE = (
    "**[ECW Bash Preflight]** Warning: `{label}` detected in command. {guidance}"
)


def _is_tag_push(command):
    """Check if a git push command targets a tag (lower risk than branch force-push)."""
    return bool(_TAG_PATTERN.search(command))


def check(input_data, config=None):
    """Check Bash command for dangerous operations.

    Args:
        input_data: Hook input dict with tool_name, tool_input, cwd.
        config: ECW config dict (unused by this sub-hook).

    Returns:
        ("block", message) if a hard-blocked pattern is matched.
        ("continue", message) if only warnings.
        ("continue", "") if clean.
    """
    if os.environ.get("ECW_ALLOW_DANGEROUS_CMD", "").strip() == "1":
        return ("continue", "")

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return ("continue", "")

    # Check for sed -i bypass of gateguard
    sed_block = _check_sed_bypass(command, config)
    if sed_block:
        return ("block", sed_block)

    warnings = []

    # Check blocked patterns first
    for pattern, label, guidance in BLOCKED_PATTERNS:
        if pattern.search(command):
            if ("force" in label.lower() or "-f" in label) and _is_tag_push(command):
                warnings.append(WARN_MSG_TEMPLATE.format(
                    label="force-push tag",
                    guidance="Force-pushing a tag is lower risk but still notable. Verify the tag target.",
                ))
                continue
            return ("block", BLOCK_MSG_TEMPLATE.format(label=label, guidance=guidance))

    # Check warning patterns
    for pattern, label, guidance in WARN_PATTERNS:
        if pattern.search(command):
            warnings.append(WARN_MSG_TEMPLATE.format(label=label, guidance=guidance))

    if warnings:
        return ("continue", "\n\n".join(warnings))

    return ("continue", "")
