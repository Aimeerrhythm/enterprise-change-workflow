#!/usr/bin/env python3
"""ECW PostToolUse auto-continue hook — deterministic skill chaining.

Fires after each Skill tool invocation. When the loaded skill is an ECW skill
and session-state.md has Auto-Continue: yes, injects the remaining routing
chain as a systemMessage so the model chains to the next skill without asking.

Replaces the repeated "CRITICAL — Auto-Continue Rule" prompt blocks that were
scattered across 9+ SKILL.md files (Issue #5).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state, read_marker_section  # noqa: E402

_FIELD_PATTERNS = {
    "auto_continue": r'\*\*Auto-Continue\*\*:\s*(.+)',
    "routing": r'\*\*Routing\*\*:\s*(.+)',
    "next": r'\*\*Next\*\*:\s*(.+)',
    "risk_level": r'\*\*Risk Level\*\*:\s*(P[0-3])',
}


def _parse_field(status_text, field_name):
    pattern = _FIELD_PATTERNS.get(field_name)
    if not pattern:
        return None
    m = re.search(pattern, status_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _remaining_route(routing, current_skill):
    """Extract steps after current_skill in the routing chain.

    Returns [] when current_skill is not found, not the full chain —
    injecting the full chain would cause the model to re-run the entire workflow.
    """
    if not routing:
        return []
    steps = [s.strip() for s in routing.split("→")]
    for i, step in enumerate(steps):
        if current_skill in step or step in current_skill:
            return steps[i + 1:]
    return []


def main():
    input_data = json.load(sys.stdin)

    if input_data.get("tool_name") != "Skill":
        print(json.dumps({"result": "continue"}))
        return

    skill_name = input_data.get("tool_input", {}).get("skill", "")
    if not skill_name.startswith("ecw:"):
        print(json.dumps({"result": "continue"}))
        return

    cwd = input_data.get("cwd", "")
    if not cwd:
        print(json.dumps({"result": "continue"}))
        return

    state_path = find_session_state(cwd)
    if not state_path:
        print(json.dumps({"result": "continue"}))
        return

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(16384)  # STATUS block is near top; 16KB covers large ledger entries
    except Exception:
        print(json.dumps({"result": "continue"}))
        return

    status = read_marker_section(content, "STATUS")
    if not status:
        print(json.dumps({"result": "continue"}))
        return

    auto_continue = _parse_field(status, "auto_continue")
    if auto_continue != "yes":
        print(json.dumps({"result": "continue"}))
        return

    routing = _parse_field(status, "routing") or ""
    risk_level = _parse_field(status, "risk_level") or ""
    next_skill = _parse_field(status, "next") or ""

    remaining = _remaining_route(routing, skill_name)
    remaining_str = " → ".join(remaining) if remaining else ""

    parts = [f"[ECW AUTO-CONTINUE] Workflow auto-continue is active (risk: {risk_level})."]
    if remaining_str:
        parts.append(f"Remaining route after {skill_name}: {remaining_str}.")
    if next_skill and next_skill != skill_name:
        parts.append(f"Current Next target: {next_skill}.")
    parts.append(
        "After completing this skill, update session-state.md Next field "
        "and invoke the next skill immediately. "
        "Do not ask for confirmation or output transition text — "
        "the user already approved the full routing chain during Phase 1."
    )

    print(json.dumps({"systemMessage": " ".join(parts)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"result": "continue"}))
