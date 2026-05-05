#!/usr/bin/env python3
"""ECW auto-continue hook — deterministic skill chaining (PreToolUse + PostToolUse).

PreToolUse (fires when a Skill is about to be invoked):
  - Updates Current Phase to the in-progress skill name (hard-coded, not LLM-dependent)
  - Updates Next to the next ECW skill in the Routing chain (resolves TDD:RED → ecw:tdd etc.)
  - Updates Working Mode for the current skill

PostToolUse (fires after each Skill tool invocation):
  - Atomically updates Current Phase (completed) and Working Mode in session-state.md
  - Injects the remaining routing chain as a systemMessage so the model chains immediately
  - After biz-impact-analysis: triggers ecw:knowledge-track if knowledge_root is configured
    and knowledge-track is not already in the Routing chain (backward compatibility)

Replaces the repeated "CRITICAL — Auto-Continue Rule" prompt blocks (Issue #5).
Fixes stale Current Phase / Working Mode / Next fields (Issue #21, Issue #26).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import (  # noqa: E402
    append_timeline_entry,
    find_session_state,
    parse_status,
    update_mode,
    update_status_fields,
    validate_status,
)
from trace_logger import log_trace  # noqa: E402

# Completed-phase value written to Current Phase after a skill finishes.
# Key: ECW skill name (as passed in tool_input.skill).
# Value: the phase string to record in the STATUS block.
_SKILL_COMPLETED_PHASE = {
    "ecw:risk-classifier":          "phase1-loaded",   # Phase 2 overrides via its own write; SKILL.md writes phase1-complete when done
    "ecw:requirements-elicitation": "requirements-loaded",
    "ecw:domain-collab":            "domain-collab-loaded",
    "ecw:writing-plans":            "plan-loaded",
    "ecw:spec-challenge":           "spec-challenge-loaded",
    "ecw:tdd":                      "tdd-loaded",
    "ecw:impl-orchestration":       "impl-loaded",
    "ecw:systematic-debugging":     "impl-loaded",
    "ecw:impl-verify":              "verify-loaded",
    "ecw:biz-impact-analysis":      "biz-impact-loaded",
    "ecw:knowledge-track":          "knowledge-track-loaded",
}

# Working Mode associated with each skill while it is active.
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
    "ecw:knowledge-track":          "verification",
}

# Skills whose Routing-chain entry does not match their short name.
# E.g., ecw:tdd appears as "TDD:RED" (and related phase steps) in the Routing string.
_SKILL_ROUTING_ALIASES = {
    "ecw:tdd": ["TDD:RED", "Implementation(GREEN)", "Fix(GREEN)"],
}

# Routing chain steps that map to an ECW skill name but cannot be derived from the
# skill's own short name.  Only entries that need special treatment live here;
# all other skills are matched by their short name (strip "ecw:" prefix).
_ROUTING_STEP_TO_SKILL = {
    "TDD:RED": "ecw:tdd",
}

# Skills that are legitimately invoked outside the Routing chain (manual-only tools).
# These are whitelisted from deviation detection.
_OFF_CHAIN_ALLOWED = {
    "ecw:cross-review",
    "ecw:knowledge-audit",
    "ecw:knowledge-repomap",
    "ecw:workspace",
}


def _remaining_route(routing, current_skill):
    """Extract steps after current_skill in the routing list.

    routing: list of step strings (YAML routing list from session-state.md).
    Returns [] when current_skill is not found, not the full chain —
    injecting the full chain would cause the model to re-run the entire workflow.
    """
    if not routing:
        return []
    if isinstance(routing, str):
        # Legacy: accept string for backward compatibility during migration
        routing = [s.strip() for s in routing.split("→")]

    aliases = _SKILL_ROUTING_ALIASES.get(current_skill, [])
    short_name = current_skill.replace("ecw:", "").lower() if current_skill.startswith("ecw:") else ""

    # Use last-match so multi-step skills (e.g., TDD:RED + Implementation(GREEN))
    # correctly return what follows their final alias step.
    last_match = -1
    for i, step in enumerate(routing):
        step_lower = step.lower()
        if current_skill == step or (short_name and short_name == step_lower):
            last_match = i
        else:
            for alias in aliases:
                if alias.lower() == step_lower:
                    last_match = i
                    break

    return routing[last_match + 1:] if last_match != -1 else []


def _routing_step_to_skill(step):
    """Convert a single Routing chain step to an ECW skill name.

    Returns None for non-skill steps (Phase 2, Phase 3, Implementation(GREEN), etc.).
    """
    step_stripped = step.strip()
    if not step_stripped:
        return None

    # Direct match against known full skill names (e.g. "ecw:impl-verify")
    if step_stripped in _SKILL_COMPLETED_PHASE:
        return step_stripped

    # Static alias table (e.g. "TDD:RED" → "ecw:tdd")
    step_lower = step_stripped.lower()
    for alias, skill in _ROUTING_STEP_TO_SKILL.items():
        if alias.lower() == step_lower:
            return skill

    # Short-name match: strip "ecw:" from known skills and compare
    for skill_name in _SKILL_COMPLETED_PHASE:
        short = skill_name.replace("ecw:", "").lower()
        if short == step_lower:
            return skill_name

    return None  # non-skill step


def _check_routing_deviation(routing_list, current_skill, expected_next):
    """Check if current_skill deviates from the Routing chain.

    Args:
        routing_list: Routing chain as a list of steps (from session-state.md).
        current_skill: The skill being invoked now (e.g., "ecw:impl-verify").
        expected_next: The skill that was expected next (from fields_dict["next"]).

    Returns:
        dict with {"type": "off-chain"|"out-of-order", "detail": str} if deviation detected.
        None if no deviation.
    """
    # Whitelist: manual-only tools are legitimately off-chain
    if current_skill in _OFF_CHAIN_ALLOWED:
        return None

    # Empty or None routing: no chain to validate
    if not routing_list:
        return None

    # Build set of all skills in the routing chain
    chain_skills = set()
    for step in routing_list:
        skill = _routing_step_to_skill(step)
        if skill:
            chain_skills.add(skill)

    # Check if current skill is off-chain
    if current_skill not in chain_skills:
        return {
            "type": "off-chain",
            "detail": f"Skill '{current_skill}' not found in routing chain {routing_list}",
        }

    # Check if current skill is out-of-order (expected_next exists and doesn't match)
    if expected_next and current_skill != expected_next:
        return {
            "type": "out-of-order",
            "detail": f"Expected '{expected_next}' but got '{current_skill}'",
        }

    return None


def _next_skill_from_routing(routing, current_skill):
    """Find the next ECW skill to invoke after current_skill in the routing chain.

    routing: list of step strings (YAML routing list from session-state.md).
    Handles Routing aliases (e.g., TDD:RED → ecw:tdd, Implementation(GREEN) is still tdd).
    Returns the full ECW skill name (e.g., 'ecw:impl-verify') or None if not found.
    """
    if not routing:
        return None
    if isinstance(routing, str):
        # Legacy: accept string for backward compatibility during migration
        routing = [s.strip() for s in routing.split("→")]

    aliases = _SKILL_ROUTING_ALIASES.get(current_skill, [])
    short_name = current_skill.replace("ecw:", "").lower() if current_skill.startswith("ecw:") else ""

    # Find the LAST position where current_skill (or any of its aliases) appears.
    # Using last-match so multi-step skills like tdd (TDD:RED + Implementation(GREEN))
    # correctly find what follows their final alias.
    last_match_idx = -1
    for i, step in enumerate(routing):
        step_lower = step.lower()
        if current_skill == step:
            last_match_idx = i
            continue
        if short_name and short_name == step_lower:
            last_match_idx = i
            continue
        for alias in aliases:
            if alias.lower() == step_lower:
                last_match_idx = i
                break

    if last_match_idx == -1:
        return None

    # Walk remaining steps and return the first that resolves to an ECW skill.
    for step in routing[last_match_idx + 1:]:
        skill = _routing_step_to_skill(step)
        if skill:
            return skill

    return None


def _handle_pre_tool_use(state_path, skill_name, cwd=""):
    """Update Current Phase (in-progress), Next, and Working Mode at skill entry.

    Hard-codes the in-progress state so these fields are always accurate regardless
    of whether the SKILL.md prompt is followed — fixes Issue #26.
    """
    in_progress_phase = skill_name.replace("ecw:", "") if skill_name.startswith("ecw:") else None
    mode = _SKILL_MODE.get(skill_name)

    if not in_progress_phase and not mode:
        return

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        fields_dict = parse_status(content)
        routing = (fields_dict or {}).get("routing") or []

        # ── Routing deviation detection (before field updates) ─────────────
        # Only check when auto_continue is active and a routing chain is set.
        auto_continue = (fields_dict or {}).get("auto_continue")
        if auto_continue is True and routing:
            # expected_next is what the previous skill wrote as the next step
            expected_next = (fields_dict or {}).get("next") or None
            deviation = _check_routing_deviation(routing, skill_name, expected_next)
            if deviation:
                log_trace(cwd, "auto-continue", "PreToolUse",
                          skill=skill_name,
                          action="routing_deviation",
                          deviation=deviation,
                          severity="warn")

        next_skill = _next_skill_from_routing(routing, skill_name)

        fields = {}
        if in_progress_phase:
            fields["current_phase"] = in_progress_phase
        if next_skill:
            fields["next"] = next_skill
        if fields:
            content = update_status_fields(content, fields)
        if mode:
            content = update_mode(content, mode)

        # Append TIMELINE entry (backfills previous entry's end/duration_s automatically).
        # Only for skills we track in _SKILL_MODE — same guard as STATUS updates above.
        if skill_name in _SKILL_MODE:
            phase = skill_name.replace("ecw:", "") if skill_name.startswith("ecw:") else skill_name
            content = append_timeline_entry(content, phase)

        with open(state_path, "w", encoding="utf-8") as f:
            f.write(content)

        log_trace(cwd, "auto-continue", "PreToolUse",
                  skill=skill_name,
                  action="update_fields",
                  fields_updated={**({"current_phase": in_progress_phase} if in_progress_phase else {}),
                                  **({"next": next_skill} if next_skill else {}),
                                  **({"mode": mode} if mode else {})})
    except Exception:
        pass  # Never block workflow


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
            content = update_status_fields(content, {"current_phase": phase})
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

    # Route to PreToolUse or PostToolUse handler based on hook event.
    # Default to PostToolUse to preserve backward compatibility with tests that
    # omit hook_event_name.
    hook_event = input_data.get("hook_event_name", "PostToolUse")

    if hook_event == "PreToolUse":
        _handle_pre_tool_use(state_path, skill_name, cwd=cwd)
        print(json.dumps({"result": "continue"}))
        return

    # ── PostToolUse path ──────────────────────────────────────────────────────

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read(16384)  # STATUS block is near top; 16KB covers large ledger entries
    except Exception:
        print(json.dumps({"result": "continue"}))
        return

    fields_dict = parse_status(content)
    if not fields_dict:
        print(json.dumps({"result": "continue"}))
        return

    errors = validate_status(fields_dict)
    if errors:
        print(f"[auto-continue] STATUS validation warnings: {errors}", file=sys.stderr)

    auto_continue = fields_dict.get("auto_continue")
    if auto_continue is not True:
        print(json.dumps({"result": "continue"}))
        return

    routing = fields_dict.get("routing") or []
    risk_level = fields_dict.get("risk_level") or ""
    next_skill = fields_dict.get("next") or ""

    # Advance phase and mode atomically before injecting the routing message.
    _advance_session_state(state_path, skill_name)

    # spec-challenge has mandatory per-flaw AskUserQuestion confirmation before proceeding.
    # Phase/mode updates (above) still apply; only skip systemMessage injection so the
    # "do not ask for confirmation" directive does not override the SKILL.md flow.
    if skill_name == "ecw:spec-challenge":
        log_trace(cwd, "auto-continue", "PostToolUse",
                  skill=skill_name, action="skip_inject", reason="spec-challenge")
        print(json.dumps({"result": "continue"}))
        return

    remaining = _remaining_route(routing, skill_name)

    # knowledge-track fallback: after biz-impact-analysis, if knowledge-track is NOT already
    # in the remaining Routing chain (old sessions), check ecw.yml and inject it when needed.
    if skill_name == "ecw:biz-impact-analysis":
        has_kt = any(_routing_step_to_skill(s) == "ecw:knowledge-track" for s in remaining)
        if not has_kt and risk_level in ("P0", "P1"):
            try:
                from ecw_config import read_ecw_config  # noqa: PLC0415
                cfg = read_ecw_config(cwd)
                knowledge_root = (cfg.get("paths") or {}).get("knowledge_root")
            except Exception:
                knowledge_root = None
            if knowledge_root:
                kt_msg = (
                    "[ECW AUTO-CONTINUE] Knowledge utilization tracking required for "
                    f"{risk_level} workflow. "
                    "Invoke ecw:knowledge-track immediately to record which knowledge files "
                    "were used (hit/miss/redundant/misleading). "
                    "Do not ask for confirmation."
                )
                log_trace(cwd, "auto-continue", "PostToolUse",
                          skill=skill_name, action="inject_knowledge_track",
                          risk_level=risk_level)
                print(json.dumps({"systemMessage": kt_msg}, ensure_ascii=False))
                return

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

    log_trace(cwd, "auto-continue", "PostToolUse",
              skill=skill_name, action="inject_system_message",
              next_target=next_skill or None,
              routing_remaining=remaining or None)

    print(json.dumps({"systemMessage": " ".join(parts)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"result": "continue"}))
