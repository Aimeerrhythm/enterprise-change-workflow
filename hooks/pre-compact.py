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
from marker_utils import find_session_state, CheckpointStore, parse_status  # noqa: E402


COMPACT_MARKER_PREFIX = "<!-- ECW:COMPACT:"


def _get_session_data_files(cwd):
    """List .md files in session-data/ directory as relative paths."""
    store = CheckpointStore.from_latest_workflow(cwd)
    if store is None:
        return []
    return [
        os.path.relpath(p, cwd)
        for p in store.list(return_paths=True)
    ]


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
    """Extract risk level from session-state.md STATUS section (YAML format)."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(4096)
        fields = parse_status(content)
        if fields:
            return fields.get("risk_level") or None
    except Exception:
        pass
    return None


def _extract_current_phase(state_path):
    """Extract current phase from session-state.md STATUS section (YAML format)."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(4096)
        fields = parse_status(content)
        if fields:
            return fields.get("current_phase") or None
    except Exception:
        pass
    return None


def _extract_next_skill(state_path):
    """Extract next skill from session-state.md STATUS section (YAML format)."""
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(4096)
        fields = parse_status(content)
        if fields:
            val = fields.get("next", "")
            if val and str(val).lower() not in ('tbd', 'none', 'complete', ''):
                return str(val)
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
        try:
            with open(state_path, encoding="utf-8", errors="ignore") as f:
                state_content = f.read()
            fields = parse_status(state_content)
            if fields:
                risk = fields.get("risk_level") or None
                phase = fields.get("current_phase") or None
                val = fields.get("next", "")
                if val and str(val).lower() not in ("tbd", "none", "complete", ""):
                    next_skill = str(val)
        except Exception:
            pass

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
