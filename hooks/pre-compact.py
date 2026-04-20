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

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state  # noqa: E402


COMPACT_MARKER_PREFIX = "<!-- ECW:COMPACT:"


def _get_session_data_files(cwd):
    """List .md files in session-data/ directory.

    Supports workflow-id subdirectories (D-3 isolation): scans the most recent
    subdirectory first. Falls back to root session-data/ for backward compat.
    """
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data_dir):
        return []

    files = []
    try:
        # Check for workflow-id subdirectories
        subdirs = []
        root_files = []
        for name in sorted(os.listdir(session_data_dir)):
            full = os.path.join(session_data_dir, name)
            if os.path.isdir(full):
                subdirs.append((full, os.path.getmtime(full), name))
            elif os.path.isfile(full) and name.endswith(".md"):
                rel = os.path.relpath(full, cwd)
                root_files.append(rel)

        if subdirs:
            # Use the most recent subdirectory
            subdirs.sort(key=lambda x: x[1], reverse=True)
            latest_dir = subdirs[0][0]
            for name in sorted(os.listdir(latest_dir)):
                full = os.path.join(latest_dir, name)
                if os.path.isfile(full) and name.endswith(".md"):
                    rel = os.path.relpath(full, cwd)
                    files.append(rel)
        else:
            files = root_files
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


def _extract_current_phase(state_path):
    """Extract current phase from session-state.md."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(2048)
        m = re.search(r'\*\*Current Phase\*\*:\s*(.+)', content)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def _extract_next_skill(state_path):
    """Extract next skill from session-state.md Next field."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(2048)
        m = re.search(r'\*\*Next\*\*:\s*(.+)', content)
        if m:
            val = m.group(1).strip()
            if val and val.lower() not in ('tbd', 'none', 'complete', ''):
                return val
    except Exception:
        pass
    return None


def _build_recovery_message(state_path, checkpoint_files, cwd):
    """Build the recovery systemMessage with auto-continue as the primary directive."""
    parts = []

    rel_state = None
    risk = None
    phase = None
    next_skill = None
    if state_path:
        rel_state = os.path.relpath(state_path, cwd)
        risk = _extract_risk_level(state_path)
        phase = _extract_current_phase(state_path)
        next_skill = _extract_next_skill(state_path)

    # Auto-continue directive FIRST — this is the primary instruction
    parts.append(
        "**MANDATORY: Auto-continue after compaction.** "
        "Do NOT wait for user input. Do NOT ask for confirmation. "
        "Immediately execute the recovery steps below, then resume "
        "the ECW workflow from where it left off."
    )

    # Recovery steps — concise, actionable
    parts.append("\n**Recovery steps:**")

    if rel_state:
        risk_info = f" ({risk})" if risk else ""
        parts.append(
            f"\n1. Read `{rel_state}`{risk_info} — "
            "find **Routing** (next skill) and **Current Phase**"
        )
    else:
        parts.append(
            "\n1. List `.claude/ecw/session-data/` subdirs, "
            "read `session-state.md` from the most recent one"
        )

    parts.append("\n2. Run **TaskList** — find pending/in-progress tasks")

    if checkpoint_files:
        non_state = [f for f in checkpoint_files if "session-state" not in f]
        if non_state:
            files_str = ", ".join(f"`{f}`" for f in non_state[:5])
            parts.append(f"\n3. Read checkpoint files if needed: {files_str}")

    # Explicit next action
    if next_skill:
        parts.append(
            f"\n**NEXT ACTION:** Invoke `{next_skill}` immediately. "
            "This was the next skill in the routing chain before compaction."
        )
    elif phase:
        parts.append(
            f"\n**NEXT ACTION:** Phase before compaction was `{phase}`. "
            "Read session-state.md, determine exact next step, execute it now."
        )
    else:
        parts.append(
            "\n**NEXT ACTION:** Read session-state.md, determine the current "
            "phase and next step from Routing, execute it now."
        )

    return "\n".join(parts)


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        msg = (
            "**MANDATORY: Auto-continue after compaction.** "
            "Do NOT wait for user input. "
            "List `.claude/ecw/session-data/` subdirectories, "
            "read `session-state.md` from the most recent one, "
            "run TaskList, then resume the ECW workflow immediately."
        )
        print(json.dumps({"result": "continue", "systemMessage": msg}))
        return

    state_path = find_session_state(cwd)
    checkpoint_files = _get_session_data_files(cwd)

    if state_path:
        _append_compact_marker(state_path)

    msg = _build_recovery_message(state_path, checkpoint_files, cwd)
    print(json.dumps({"result": "continue", "systemMessage": msg}, ensure_ascii=False))


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
