#!/usr/bin/env python3
"""ECW SessionEnd hook — clean up on session exit.

When a session ends:
1. Clean up stale transient state files

This hook runs once when the Claude session terminates.
"""

import json
import os
import sys

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _cleanup_state_files(cwd):
    """Remove transient state files that don't need to persist across sessions."""
    state_dir = os.path.join(cwd, ".claude", "ecw", "state")
    transient_files = [
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

    _cleanup_state_files(cwd)

    print(json.dumps({"result": "continue"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # SessionEnd hook errors must never block
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
