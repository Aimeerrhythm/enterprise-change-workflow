#!/usr/bin/env python3
"""ECW gateguard-fact-force sub-hook — block first edit until file is investigated.

When Claude attempts to Edit/Write a source file for the first time in a session,
this hook blocks the action and demands investigation of the file's importers,
callers, and schema before proceeding.

State file: .claude/ecw/state/investigated-files.txt
  - One relative path per line
  - Cleared at session end

Exemptions:
  - Non-source files (.md, .json, .yml, .yaml, .txt, .toml, .cfg, .ini, .lock)
  - Files under .claude/ directory (ECW artifacts)
  - ECW_GATEGUARD_DISABLED=1 environment variable
  - "minimal" profile (P3 risk level)
"""

import os

EXEMPT_EXTENSIONS = {
    ".md", ".json", ".yml", ".yaml", ".txt", ".toml",
    ".cfg", ".ini", ".lock", ".csv", ".xml", ".html",
}

STATE_FILENAME = "investigated-files.txt"


def _get_state_path(cwd):
    return os.path.join(cwd, ".claude", "ecw", "state", STATE_FILENAME)


def _read_investigated(cwd):
    state_path = _get_state_path(cwd)
    try:
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                return {line.strip() for line in f if line.strip()}
    except Exception:
        pass
    return set()


def _record_investigated(cwd, rel_path):
    state_path = _get_state_path(cwd)
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "a", encoding="utf-8") as f:
            f.write(rel_path + "\n")
    except Exception:
        pass


def _is_exempt(file_path, cwd, config=None):
    if not file_path:
        return True

    _, ext = os.path.splitext(file_path)
    if ext.lower() in EXEMPT_EXTENSIONS:
        return True

    rel = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path
    rel = rel.replace(os.sep, "/")
    if rel.startswith(".claude/"):
        return True

    # User-configured exempt paths from ecw.yml
    if config:
        for prefix in config.get("hooks", {}).get("exempt_paths", []):
            if rel.startswith(prefix):
                return True

    return False


def check(input_data, config=None):
    """Sub-hook entry point.

    Returns:
        ("block", message) — first touch, demands investigation
        ("continue", "") — file already investigated or exempt
    """
    if os.environ.get("ECW_GATEGUARD_DISABLED", "").strip() == "1":
        return ("continue", "")

    file_path = input_data.get("tool_input", {}).get("file_path", "")
    cwd = input_data.get("cwd", "")

    if not file_path or not cwd:
        return ("continue", "")

    if _is_exempt(file_path, cwd, config):
        return ("continue", "")

    if not os.path.exists(file_path):
        return ("continue", "")

    rel_path = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path

    investigated = _read_investigated(cwd)
    if rel_path in investigated:
        return ("continue", "")

    _record_investigated(cwd, rel_path)

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
