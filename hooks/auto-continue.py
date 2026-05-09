#!/usr/bin/env python3
"""ECW auto-continue hook — deterministic skill chaining (PreToolUse + PostToolUse).

PreToolUse (fires when a Skill is about to be invoked):
  - Updates Current Phase to the in-progress skill name (hard-coded, not LLM-dependent)
  - Updates Next to the next ECW skill in the Routing chain (resolves TDD:RED → ecw:tdd etc.)
  - Updates Working Mode for the current skill

PostToolUse (fires after each Skill tool invocation):
  - Atomically updates Current Phase (completed) and Working Mode in session-state.json
  - After risk-classifier: rebuilds full routing chain from routing[0] + tail(risk_level)
  - Injects the remaining routing chain as a systemMessage so the model chains immediately

Replaces the repeated "CRITICAL — Auto-Continue Rule" prompt blocks (Issue #5).
Fixes stale Current Phase / Working Mode / Next fields (Issue #21, Issue #26).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import (  # noqa: E402
    find_session_state,
    parse_status,
    update_status_fields,
    validate_status,
)
from routes_utils import (  # noqa: E402
    SKILL_COMPLETED_PHASE as _SKILL_COMPLETED_PHASE,
    SKILL_ROUTING_ALIASES as _SKILL_ROUTING_ALIASES,
    ROUTING_STEP_TO_SKILL as _ROUTING_STEP_TO_SKILL,
    OFF_CHAIN_ALLOWED as _OFF_CHAIN_ALLOWED,
    _load_routes_from_file,
    remaining_route as _remaining_route,
    routing_step_to_skill as _routing_step_to_skill,
    check_routing_deviation as _check_routing_deviation,
    next_skill_from_routing as _next_skill_from_routing,
    compute_routing_tail as _compute_routing_tail,
)
from trace_logger import log_trace  # noqa: E402


def _rebuild_routing_chain(state_path, fields_dict):
    """After risk-classifier completes, rebuild full routing chain from routing[0] + tail.

    Tail is derived dynamically from workflow-routes.yml (single source of truth),
    which also correctly handles P2 cross-domain (domain-collab + writing-plans + ...).
    """
    try:
        routing = fields_dict.get("routing") or []
        risk_level = (fields_dict.get("risk_level") or "").strip()

        if isinstance(routing, str):
            routing = [s.strip() for s in routing.split("→") if s.strip()]

        if not routing or not risk_level:
            return

        first_skill = routing[0]
        tail = _compute_routing_tail(risk_level, first_skill)
        update_status_fields(state_path, {"routing": [first_skill] + tail})
    except Exception:
        pass  # Never block workflow


def _handle_pre_tool_use(state_path, skill_name, cwd=""):
    """Update Current Phase (in-progress) and Next at skill entry.

    Returns a dict with read-only state context for injection, or None.
    """
    in_progress_phase = skill_name.replace("ecw:", "") if skill_name.startswith("ecw:") else None

    if not in_progress_phase:
        return None

    try:
        fields_dict = parse_status(state_path) or {}

        routing = fields_dict.get("routing") or []

        # ── Routing deviation detection (before field updates) ─────────────
        auto_continue = fields_dict.get("auto_continue")
        if auto_continue is True and routing:
            expected_next = fields_dict.get("next") or None
            deviation = _check_routing_deviation(routing, skill_name, expected_next)
            if deviation:
                log_trace(cwd, "auto-continue", "PreToolUse",
                          skill=skill_name,
                          action="routing_deviation",
                          deviation=deviation,
                          severity="warn")
                if deviation["type"] == "off-chain":
                    return None

        next_skill = _next_skill_from_routing(routing, skill_name)

        updates = {}
        if in_progress_phase:
            updates["current_phase"] = in_progress_phase
        if next_skill:
            updates["next"] = next_skill

        if updates:
            fields_dict = update_status_fields(state_path, updates)

        log_trace(cwd, "auto-continue", "PreToolUse",
                  skill=skill_name,
                  action="update_fields",
                  fields_updated=updates)

        # Build read-only state context for Skill injection (Issue #62 Part 3)
        risk_level = (fields_dict or {}).get("risk_level") or ""
        remaining = _remaining_route(routing, skill_name)
        return {
            "risk_level": risk_level,
            "next": next_skill or "",
            "routing_remaining": remaining,
        }
    except Exception:
        pass  # Never block workflow
    return None


def _advance_session_state(state_path, skill_name):
    """Atomically update Current Phase after a skill completes."""
    phase = _SKILL_COMPLETED_PHASE.get(skill_name)
    if not phase:
        return

    try:
        update_status_fields(state_path, {"current_phase": phase})
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
        state_ctx = _handle_pre_tool_use(state_path, skill_name, cwd=cwd)

        # Build read-only state context message (Issue #62 Part 3)
        parts = []
        if state_ctx and state_ctx.get("risk_level"):
            ctx_line = (
                f"[ECW STATE — read-only] risk={state_ctx['risk_level']}"
            )
            if state_ctx.get("next"):
                ctx_line += f", next={state_ctx['next']}"
            if state_ctx.get("routing_remaining"):
                ctx_line += f", remaining={' → '.join(state_ctx['routing_remaining'])}"
            parts.append(ctx_line)

        if parts:
            print(json.dumps({"systemMessage": "\n\n".join(parts)}, ensure_ascii=False))
        else:
            print(json.dumps({"result": "continue"}))
        return

    # ── PostToolUse path ──────────────────────────────────────────────────────

    try:
        fields_dict = parse_status(state_path)
    except Exception:
        print(json.dumps({"result": "continue"}))
        return

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

    # After risk-classifier completes, rebuild full routing chain from routing[0] + tail.
    if skill_name == "ecw:risk-classifier":
        _rebuild_routing_chain(state_path, fields_dict)
        # Re-read routing so the systemMessage reflects the full chain.
        try:
            updated = parse_status(state_path)
            if updated:
                routing = updated.get("routing") or routing
        except Exception:
            pass

    # spec-challenge has mandatory per-flaw AskUserQuestion confirmation before proceeding.
    # PostToolUse fires immediately after Skill instructions load (before LLM executes them),
    # so injecting "do not ask for confirmation" would suppress the Fatal Flaw flow.
    if skill_name == "ecw:spec-challenge":
        log_trace(cwd, "auto-continue", "PostToolUse",
                  skill=skill_name, action="skip_inject", reason="spec-challenge")
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
        "After completing this skill, invoke the next skill immediately. "
        "Do not ask for confirmation or output transition text — "
        "the user already approved the full routing chain during the initial risk assessment."
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
