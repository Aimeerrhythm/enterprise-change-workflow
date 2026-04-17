#!/usr/bin/env python3
"""ECW Stop hook — auto-persist workflow state at end of each response.

Runs after every assistant response to:
1. Update session-state.md with last-updated timestamp and activity summary
2. Use marker-based idempotent updates (<!-- ECW:STOP:START/END -->)
3. Never block normal workflow — all errors are swallowed

Input (stdin JSON):
  - stop_hook_active: bool
  - tool_calls: list of {tool_name, ...} from this response
  - cwd: working directory

Marker format in session-state.md:
  <!-- ECW:STOP:START -->
  ... auto-updated content ...
  <!-- ECW:STOP:END -->
"""

import json
import os
import re
import sys
from datetime import datetime


MARKER_START = "<!-- ECW:STOP:START -->"
MARKER_END = "<!-- ECW:STOP:END -->"


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


def _extract_activity_summary(input_data):
    """Extract a brief activity summary from the stop hook input."""
    tool_calls = input_data.get("tool_calls", [])
    if not tool_calls:
        return "No tool calls in this response"

    # Count tool usage
    tool_counts = {}
    files_modified = set()
    for tc in tool_calls:
        name = tc.get("tool_name", "unknown")
        tool_counts[name] = tool_counts.get(name, 0) + 1
        # Track file modifications
        if name in ("Edit", "Write"):
            fp = tc.get("tool_input", {}).get("file_path", "")
            if fp:
                files_modified.add(os.path.basename(fp))

    parts = []
    for name, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
        parts.append(f"{name}({count})")
    summary = "Tools: " + ", ".join(parts[:8])

    if files_modified:
        files_str = ", ".join(sorted(files_modified)[:5])
        if len(files_modified) > 5:
            files_str += f" +{len(files_modified) - 5} more"
        summary += f" | Files: {files_str}"

    return summary


def _build_stop_section(input_data):
    """Build the marker-enclosed auto-update section."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    activity = _extract_activity_summary(input_data)

    return (
        f"{MARKER_START}\n"
        f"- **Last Updated**: {now}\n"
        f"- **Activity**: {activity}\n"
        f"{MARKER_END}"
    )


def _update_with_markers(content, new_section):
    """Replace marker-enclosed section, or append if markers not found."""
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    if pattern.search(content):
        return pattern.sub(new_section, content)
    else:
        # Append after the first heading block
        return content.rstrip() + "\n\n" + new_section + "\n"


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        print(json.dumps({"result": "continue"}))
        return

    state_path = _find_session_state(cwd)
    if not state_path:
        # No active session-state — nothing to persist
        print(json.dumps({"result": "continue"}))
        return

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Skip if session is already marked as ended
        if re.search(r'\*\*Status\*\*:\s*ended', content, re.IGNORECASE):
            print(json.dumps({"result": "continue"}))
            return

        new_section = _build_stop_section(input_data)
        updated = _update_with_markers(content, new_section)

        with open(state_path, "w", encoding="utf-8") as f:
            f.write(updated)

    except Exception:
        pass  # Stop hook errors must never block workflow

    print(json.dumps({"result": "continue"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Absolute safety — never block
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
