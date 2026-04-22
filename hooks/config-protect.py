#!/usr/bin/env python3
"""ECW config-protect sub-hook — block accidental modification of ECW configuration files.

Dispatcher sub-module registered in SUB_HOOKS for PreToolUse on Edit/Write events.
Protects core ECW configuration files (ecw.yml, domain-registry.md, etc.) from
unintended Agent modifications during implementation.

Override: set ECW_ALLOW_CONFIG_EDIT=1 environment variable to bypass protection.
"""

import os

# ── Protected file basenames ──
# These are the foundational ECW configuration and knowledge files.
# Matched by os.path.basename() to be path-format agnostic.

PROTECTED_BASENAMES = {
    "ecw.yml",
    "domain-registry.md",
    "change-risk-classification.md",
    "ecw-path-mappings.md",
}

EDITABLE_PATH_PREFIXES = (
    ".claude/knowledge/",
    ".claude/ecw/session-data/",
    ".claude/ecw/state/",
    ".claude/plans/",
    "templates/",
)

UPGRADE_MARKER = ".claude/ecw/.config-edit-allowed"

BLOCK_MESSAGE_TEMPLATE = (
    "**[ECW Config Protection]** Blocked modification of `{basename}`. "
    "This is a protected ECW configuration file. "
    "Fix the source code or business logic instead of changing the config. "
    "If you genuinely need to edit this file, ask the user to set "
    "ECW_ALLOW_CONFIG_EDIT=1 or have them edit it manually."
)


def check(input_data, config=None):
    """Check whether an Edit/Write targets a protected ECW config file.

    Args:
        input_data: Hook input dict with tool_name, tool_input, cwd.
        config: ECW config dict (unused by this sub-hook).

    Returns:
        ("block", message) if the target file is protected.
        ("continue", "") otherwise.
    """
    # Check override env var
    if os.environ.get("ECW_ALLOW_CONFIG_EDIT", "").strip() == "1":
        return ("continue", "")

    # Check upgrade marker file (created by ecw-upgrade / ecw-init)
    cwd = input_data.get("cwd", "")
    if cwd and os.path.isfile(os.path.join(cwd, UPGRADE_MARKER)):
        return ("continue", "")

    file_path = input_data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return ("continue", "")

    rel_path = os.path.relpath(file_path, cwd) if cwd else file_path
    rel_path = rel_path.replace(os.sep, "/")

    # Built-in exempt prefixes + user-configured exempt_paths from ecw.yml
    exempt = list(EDITABLE_PATH_PREFIXES)
    if config:
        exempt.extend(config.get("hooks", {}).get("exempt_paths", []))
    if any(rel_path.startswith(prefix) for prefix in exempt):
        return ("continue", "")

    basename = os.path.basename(file_path)
    if basename in PROTECTED_BASENAMES:
        return ("block", BLOCK_MESSAGE_TEMPLATE.format(basename=basename))

    return ("continue", "")
