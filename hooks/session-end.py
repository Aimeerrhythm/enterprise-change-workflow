#!/usr/bin/env python3
"""ECW SessionEnd hook — clean up on session exit.

When a session ends:
1. Mark session-state.md status as "ended" with timestamp
2. Clean up stale state files (modified-files.txt)

This hook runs once when the Claude session terminates.
"""

import json
import os
import sys
from datetime import datetime

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state, update_status_fields, _is_json_state, _read_json, _write_json  # noqa: E402


def _mark_session_ended(state_path):
    """Mark session state as ended."""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        if _is_json_state(state_path):
            data = _read_json(state_path) or {}
            data["session_status"] = f"ended ({now})"
            _write_json(state_path, data)
        else:
            with open(state_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            updated = update_status_fields(content, {"session_status": f"ended ({now})"})
            with open(state_path, "w", encoding="utf-8") as f:
                f.write(updated)

    except Exception:
        pass  # Best-effort


def _cleanup_state_files(cwd):
    """Remove transient state files that don't need to persist across sessions."""
    state_dir = os.path.join(cwd, ".claude", "ecw", "state")
    transient_files = [
        "modified-files.txt",
        "tool-call-count.txt",
        "investigated-files.txt",
    ]
    for fname in transient_files:
        try:
            fpath = os.path.join(state_dir, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
        except Exception:
            pass


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd or not os.path.isfile(os.path.join(cwd, ".claude", "ecw", "ecw.yml")):
        print(json.dumps({"result": "continue"}))
        return

    state_path = find_session_state(cwd)
    if state_path:
        _mark_session_ended(state_path)

    _cleanup_state_files(cwd)

    print(json.dumps({"result": "continue"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # SessionEnd hook errors must never block
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
