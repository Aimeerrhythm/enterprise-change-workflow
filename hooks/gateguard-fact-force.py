#!/usr/bin/env python3
"""ECW gateguard-fact-force sub-hook — block first edit until file is investigated.

When Claude attempts to Edit/Write a guarded source file,
this hook blocks the action and demands investigation of the file's importers,
callers, and schema before proceeding.

Whitelist mode:
  - Only files matching hooks.gateguard_extensions in ecw.yml are guarded.
  - Empty or missing gateguard_extensions = gateguard fully disabled.
  - Files under .claude/ directory are always exempt.
  - "minimal" profile (P3 risk level) skips gateguard via dispatcher.
"""

import os


def _parse_guarded_extensions(config):
    """Read gateguard_extensions from config and normalize to a set of lowercase dotted extensions."""
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


def _is_exempt(file_path, cwd, config=None):
    if not file_path:
        return True

    rel = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path
    rel = rel.replace(os.sep, "/")
    if rel.startswith(".claude/"):
        return True

    if config:
        for prefix in config.get("hooks", {}).get("exempt_paths", []):
            if rel.startswith(prefix):
                return True

    return False


def check(input_data, config=None):
    """Sub-hook entry point.

    Returns:
        ("block", message) — first touch, demands investigation
        ("continue", "") — file already investigated, exempt, or not guarded
    """
    file_path = input_data.get("tool_input", {}).get("file_path", "")
    cwd = input_data.get("cwd", "")

    if not file_path or not cwd:
        return ("continue", "")

    guarded_exts = _parse_guarded_extensions(config)
    if not guarded_exts:
        return ("continue", "")

    _, ext = os.path.splitext(file_path)
    if ext.lower() not in guarded_exts:
        return ("continue", "")

    if _is_exempt(file_path, cwd, config):
        return ("continue", "")

    if not os.path.exists(file_path):
        return ("continue", "")

    rel_path = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path


    basename = os.path.basename(file_path)
    msg = (
        f"**[ECW Gateguard]** First edit on `{rel_path}`. "
        f"Before modifying this file, investigate its context:\n"
        f"1. **Grep for callers/importers**: find who references `{basename}`\n"
        f"2. **Read the file** to understand its interface and responsibilities\n"
        f"3. **Check related tests** if they exist\n\n"
        f"Once you understand the impact surface, retry the edit."
    )
    return ("block", msg)
