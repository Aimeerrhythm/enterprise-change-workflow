#!/usr/bin/env python3
"""ECW PreCompact hook — inject state recovery reminder before context compaction.

Reads session-state.md (if it exists) and outputs a systemMessage reminding
Claude to restore workflow context after compaction completes.
"""

import json
import os
import sys


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    # Check if session-state file exists (informational only — message is
    # injected regardless so that post-compaction recovery always works)
    state_file = os.path.join(cwd, ".claude", "ecw", "state", "session-state.md")
    if not os.path.exists(state_file):
        # Also try the canonical path without /state/ subdirectory
        state_file = os.path.join(cwd, ".claude", "ecw", "session-state.md")

    msg = (
        "\u26a0\ufe0f Context compaction occurred. After resuming, read "
        "`.claude/ecw/state/session-state.md` and relevant session-data files "
        "under `.claude/ecw/session-data/` to restore workflow context. "
        "Check TaskList for pending work."
    )

    result = {"result": "continue", "systemMessage": msg}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # hook errors must not block normal workflow
        print(json.dumps({"result": "continue", "systemMessage": f"ECW pre-compact hook error: {e}"}))
        sys.exit(0)
