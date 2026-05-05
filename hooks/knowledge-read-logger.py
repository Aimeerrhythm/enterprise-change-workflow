#!/usr/bin/env python3
"""PostToolUse(Read) hook — auto-log knowledge file reads.

Fires after every Read tool call. If the read file is under knowledge_root
(from ecw.yml, default: .claude/knowledge/), appends a structured JSONL
record to knowledge-reads.jsonl in the active session-data directory.

Fast path: files without '/knowledge/' in their path are rejected in O(1)
before touching the filesystem — most Read calls are source code files.

Output is always {"result": "continue"} — this hook never blocks.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _knowledge_abs(cwd: str) -> str:
    """Return the absolute knowledge_root path (with trailing os.sep).

    Falls back to .claude/knowledge/ when ecw.yml is absent or has no paths.
    """
    try:
        from ecw_config import read_ecw_config
        cfg = read_ecw_config(cwd)
        root = (cfg.get("paths") or {}).get("knowledge_root", ".claude/knowledge/")
    except Exception:
        root = ".claude/knowledge/"

    if os.path.isabs(root):
        abs_root = root
    else:
        abs_root = os.path.join(cwd, root)

    if not abs_root.endswith(os.sep):
        abs_root += os.sep
    return abs_root


def _should_log(file_path: str, cwd: str, knowledge_abs: str) -> bool:
    """Return True iff file_path is under knowledge_abs.

    Uses startswith for O(1) check — no resolve() needed since Read tool
    always provides absolute paths.
    """
    if not file_path or not knowledge_abs:
        return False
    # Fast reject: no '/knowledge/' substring at all
    if "knowledge" not in file_path:
        return False
    return file_path.startswith(knowledge_abs)


def _relative_path(file_path: str, cwd: str) -> str:
    """Return file_path relative to cwd, or file_path if outside cwd."""
    try:
        cwd_with_sep = cwd if cwd.endswith(os.sep) else cwd + os.sep
        if file_path.startswith(cwd_with_sep):
            return file_path[len(cwd_with_sep):]
    except Exception:
        pass
    return file_path


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"result": "continue"}))
        return

    file_path = (input_data.get("tool_input") or {}).get("file_path", "")
    cwd = input_data.get("cwd", "")

    if not file_path or not cwd:
        print(json.dumps({"result": "continue"}))
        return

    # Only handle Read tool
    if input_data.get("tool_name") != "Read":
        print(json.dumps({"result": "continue"}))
        return

    knowledge_root = _knowledge_abs(cwd)

    if not _should_log(file_path=file_path, cwd=cwd, knowledge_abs=knowledge_root):
        print(json.dumps({"result": "continue"}))
        return

    # Find active session-state.md and derive the session-data dir
    try:
        from marker_utils import find_session_state
        state_path = find_session_state(cwd)
    except Exception:
        state_path = None

    if not state_path:
        print(json.dumps({"result": "continue"}))
        return

    session_dir = os.path.dirname(state_path)
    log_file = os.path.join(session_dir, "knowledge-reads.jsonl")

    rel_path = _relative_path(file_path, cwd)
    record = {
        "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "file": rel_path,
    }

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Never block workflow

    print(json.dumps({"result": "continue"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"result": "continue"}))
