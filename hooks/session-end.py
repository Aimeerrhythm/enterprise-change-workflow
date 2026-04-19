#!/usr/bin/env python3
"""ECW SessionEnd hook — clean up on session exit.

When a session ends:
1. Mark session-state.md status as "ended" with timestamp
2. Clean up stale state files (modified-files.txt)

This hook runs once when the Claude session terminates.
"""

import json
import os
import re
import sys
from datetime import datetime

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state  # noqa: E402


def _mark_session_ended(state_path):
    """Update session-state.md to mark status as ended."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Update or add Status field
        status_pattern = r'(\*\*(?:Current Phase|Status)\*\*:\s*).+'
        if re.search(r'\*\*Status\*\*:', content):
            content = re.sub(
                r'(\*\*Status\*\*:\s*).+',
                f'\\1ended ({now})',
                content,
            )
        elif re.search(r'\*\*Current Phase\*\*:', content):
            # Add Status after Current Phase
            content = re.sub(
                r'(\*\*Current Phase\*\*:\s*.+)',
                f'\\1\n- **Status**: ended ({now})',
                content,
            )
        else:
            # Append to end of header section
            content = content.rstrip() + f"\n- **Status**: ended ({now})\n"

        with open(state_path, "w", encoding="utf-8") as f:
            f.write(content)

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

    if not cwd:
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
