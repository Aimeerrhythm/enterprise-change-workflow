#!/usr/bin/env python3
"""ECW PreCompact hook — enhanced compaction boundary marker + recovery guidance.

When context compaction occurs:
1. Append a timestamped compaction marker to session-state.md (non-destructive)
2. Scan session-data/ for checkpoint files and list them in recovery instructions
3. Inject a precise systemMessage telling Claude which files to re-read

Marker format appended to session-state.md:
  <!-- ECW:COMPACT:{timestamp} -->
"""

import json
import os
import re
import sys
from datetime import datetime


COMPACT_MARKER_PREFIX = "<!-- ECW:COMPACT:"


def _find_session_state(cwd):
    """Find session-state.md. Returns path or None."""
    candidates = [
        os.path.join(cwd, ".claude", "ecw", "state", "session-state.md"),
        os.path.join(cwd, ".claude", "ecw", "session-state.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _get_session_data_files(cwd):
    """List .md files in session-data/ directory."""
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data_dir):
        return []

    files = []
    try:
        for name in sorted(os.listdir(session_data_dir)):
            full = os.path.join(session_data_dir, name)
            if os.path.isfile(full) and name.endswith(".md"):
                rel = os.path.relpath(full, cwd)
                files.append(rel)
    except Exception:
        pass
    return files


def _append_compact_marker(state_path):
    """Append compaction timestamp marker to session-state.md."""
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        marker = f"\n{COMPACT_MARKER_PREFIX}{now} -->\n"

        with open(state_path, "a", encoding="utf-8") as f:
            f.write(marker)
    except Exception:
        pass  # Best-effort; never block


def _extract_risk_level(state_path):
    """Extract risk level from session-state.md."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(2048)
        m = re.search(r'\*\*Risk Level\*\*:\s*(P[0-3])', content, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        msg = (
            "**Context compaction occurred.** Read `.claude/ecw/state/session-state.md` "
            "and checkpoint files under `.claude/ecw/session-data/` to restore context. "
            "Check TaskList for pending work."
        )
        print(json.dumps({"result": "continue", "systemMessage": msg}))
        return

    state_path = _find_session_state(cwd)
    checkpoint_files = _get_session_data_files(cwd)

    # Append compaction marker to session-state.md
    if state_path:
        _append_compact_marker(state_path)

    # Build recovery message
    parts = ["**Context compaction occurred.** Restore context by reading:"]

    if state_path:
        rel_state = os.path.relpath(state_path, cwd)
        risk = _extract_risk_level(state_path)
        risk_info = f" (risk: {risk})" if risk else ""
        parts.append(f"\n1. **Workflow state**: `{rel_state}`{risk_info}")
    else:
        parts.append("\n1. No active session-state.md found")

    if checkpoint_files:
        parts.append(f"\n2. **Checkpoint files** ({len(checkpoint_files)}):")
        for cf in checkpoint_files:
            parts.append(f"   - `{cf}`")
    else:
        parts.append("\n2. No checkpoint files in session-data/")

    parts.append("\n3. Check **TaskList** for pending work")
    parts.append(
        "\n4. Check `.claude/ecw/state/modified-files.txt` for files "
        "modified before compaction"
    )

    msg = "\n".join(parts)
    result = {"result": "continue", "systemMessage": msg}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # hook errors must not block normal workflow
        print(json.dumps({
            "result": "continue",
            "systemMessage": f"ECW pre-compact hook error: {e}"
        }))
        sys.exit(0)
