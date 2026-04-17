#!/usr/bin/env python3
"""ECW Stop hook — auto-persist workflow state + context health advisory.

Runs after every assistant response to:
1. Update session-state.md with last-updated timestamp and activity summary
2. Use marker-based idempotent updates (<!-- ECW:STOP:START/END -->)
3. Detect phase transitions → check context health → write advisory file
4. Never block normal workflow — all errors are swallowed

Input (stdin JSON):
  - stop_hook_active: bool
  - tool_calls: list of {tool_name, ...} from this response
  - cwd: working directory

Marker format in session-state.md:
  <!-- ECW:STOP:START -->
  ... auto-updated content ...
  <!-- ECW:STOP:END -->
"""

import glob
import json
import os
import re
import sys
from datetime import datetime

# Import shared marker utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state, update_marker_section  # noqa: E402

MAX_CONTEXT = 200_000
ADVISORY_FILE = ".claude/ecw/state/context-health.txt"
PHASE_CACHE_FILE = ".claude/ecw/state/.last-phase"


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


def _extract_current_phase(content):
    """Extract Current Phase from session-state.md content."""
    m = re.search(r'\*\*Current Phase\*\*:\s*(.+)', content)
    return m.group(1).strip() if m else None


def _check_context_health(cwd):
    """Check context window usage from session JSONL. Returns (level, pct)."""
    try:
        project_key = cwd.replace("/", "-")
        session_dir = os.path.expanduser(f"~/.claude/projects/{project_key}")
        if not os.path.isdir(session_dir):
            return None, 0

        files = glob.glob(os.path.join(session_dir, "*.jsonl"))
        if not files:
            return None, 0

        latest = max(files, key=os.path.getmtime)
        last_usage = None
        with open(latest, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "assistant":
                    usage = obj.get("message", {}).get("usage", {})
                    if usage:
                        last_usage = usage

        if not last_usage:
            return None, 0

        total = (
            last_usage.get("input_tokens", 0)
            + last_usage.get("cache_creation_input_tokens", 0)
            + last_usage.get("cache_read_input_tokens", 0)
        )
        pct = (total / MAX_CONTEXT) * 100

        if pct > 70:
            return "HIGH", pct
        elif pct > 50:
            return "MEDIUM", pct
        else:
            return "LOW", pct
    except Exception:
        return None, 0


def _update_context_advisory(cwd, state_content):
    """Detect phase transition → check context health → write advisory."""
    try:
        current_phase = _extract_current_phase(state_content)
        if not current_phase:
            return

        # Read cached last phase
        cache_path = os.path.join(cwd, PHASE_CACHE_FILE)
        last_phase = None
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                last_phase = f.read().strip()

        # Write current phase to cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(current_phase)

        advisory_path = os.path.join(cwd, ADVISORY_FILE)

        if current_phase != last_phase and last_phase is not None:
            # Phase transition detected — check context health
            level, pct = _check_context_health(cwd)
            if level == "HIGH":
                with open(advisory_path, "w", encoding="utf-8") as f:
                    f.write(f"HIGH|{pct:.0f}%|{current_phase}")
            else:
                # Not high — clear advisory
                if os.path.exists(advisory_path):
                    os.remove(advisory_path)
        # No phase change — don't touch advisory file
    except Exception:
        pass  # Never block


def _build_stop_section(input_data):
    """Build the marker-enclosed auto-update section."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    activity = _extract_activity_summary(input_data)

    return (
        f"- **Last Updated**: {now}\n"
        f"- **Activity**: {activity}"
    )


def _update_with_markers(content, new_inner):
    """Replace STOP marker section, or append if markers not found."""
    return update_marker_section(content, "STOP", new_inner)


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        print(json.dumps({"result": "continue"}))
        return

    state_path = find_session_state(cwd)
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

        # Check for phase transition → update context health advisory
        _update_context_advisory(cwd, updated)

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
