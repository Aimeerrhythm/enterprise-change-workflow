#!/usr/bin/env python3
"""ECW PostToolUse auto-continue hook — deterministic skill chaining.

Fires after each Skill tool invocation. When the loaded skill is an ECW skill
and session-state.md has Auto-Continue: yes:
  1. Atomically updates Current Phase and Working Mode in session-state.md
     (single read-modify-write — no scattered patches from skill prompts).
  2. Injects the remaining routing chain as a systemMessage so the model
     chains to the next skill without asking.

Replaces the repeated "CRITICAL — Auto-Continue Rule" prompt blocks that were
scattered across 9+ SKILL.md files (Issue #5).
Fixes stale Current Phase / Working Mode fields (Issue #21).
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import (  # noqa: E402
    find_session_state,
    read_marker_section,
    update_mode,
    update_status_fields,
)

_FIELD_PATTERNS = {
    "auto_continue": r'\*\*Auto-Continue\*\*:\s*(.+)',
    "routing": r'\*\*Routing\*\*:\s*(.+)',
    "next": r'\*\*Next\*\*:\s*(.+)',
    "risk_level": r'\*\*Risk Level\*\*:\s*(P[0-3])',
}

# Completed-phase value written to Current Phase after a skill finishes.
# Key: ECW skill name (as passed in tool_input.skill).
# Value: the phase string to record in the STATUS block.
_SKILL_COMPLETED_PHASE = {
    "ecw:risk-classifier":          "phase1-complete",   # Phase 2 overrides via its own write
    "ecw:requirements-elicitation": "requirements-complete",
    "ecw:domain-collab":            "domain-collab-complete",
    "ecw:writing-plans":            "plan-complete",
    "ecw:spec-challenge":           "spec-challenge-complete",
    "ecw:tdd":                      "tdd-complete",
    "ecw:impl-orchestration":       "impl-complete",
    "ecw:systematic-debugging":     "impl-complete",
    "ecw:impl-verify":              "verify-complete",
    "ecw:biz-impact-analysis":      "biz-impact-complete",
}

# Working Mode associated with each skill while it is active.
# This is written when the skill *completes* (so the next skill sees the correct
# incoming mode) rather than at entry, ensuring MODE and STATUS are always
# consistent with each other.
_SKILL_MODE = {
    "ecw:risk-classifier":          "analysis",
    "ecw:requirements-elicitation": "analysis",
    "ecw:domain-collab":            "analysis",
    "ecw:writing-plans":            "planning",
    "ecw:spec-challenge":           "planning",
    "ecw:tdd":                      "implementation",
    "ecw:impl-orchestration":       "implementation",
    "ecw:systematic-debugging":     "implementation",
    "ecw:impl-verify":              "verification",
    "ecw:biz-impact-analysis":      "verification",
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


def _advance_session_state(state_path, skill_name):
    """Atomically update Current Phase and Working Mode after a skill completes.

    Single read → in-memory transform → single write. No partial patches.
    Silently no-ops when the skill has no entry in the mapping tables or the
    file cannot be read/written — hook errors must never block the workflow.
    """
    phase = _SKILL_COMPLETED_PHASE.get(skill_name)
    mode = _SKILL_MODE.get(skill_name)
    if not phase and not mode:
        return

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if phase:
            content = update_status_fields(content, {"Current Phase": phase})
        if mode:
            content = update_mode(content, mode)

        with open(state_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        pass  # Never block workflow


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

    # Advance phase and mode atomically before injecting the routing message.
    _advance_session_state(state_path, skill_name)

    # spec-challenge has mandatory per-flaw AskUserQuestion confirmation before proceeding.
    # Phase/mode updates (above) still apply; only skip systemMessage injection so the
    # "do not ask for confirmation" directive does not override the SKILL.md flow.
    if skill_name == "ecw:spec-challenge":
        print(json.dumps({"result": "continue"}))
        return

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

