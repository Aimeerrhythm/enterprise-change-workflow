#!/usr/bin/env python3
"""ECW routing utilities — dynamic mapping tables from workflow-routes.yml.

Loaded once at import time. All mapping tables are generated from the single
source of truth (workflow-routes.yml). Adding/modifying a skill only requires
editing that file.
"""

import os

import yaml

_ROUTES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "skills", "risk-classifier", "workflow-routes.yml",
)


def _load_routes_from_file(routes_path=None):
    """Parse workflow-routes.yml and generate all mapping tables.

    Returns dict with keys: completed_phase, routing_aliases, step_to_skill, off_chain.
    """
    path = routes_path or _ROUTES_FILE
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    metadata = data.get("skill_metadata", {})
    off_chain_list = data.get("off_chain_skills", [])

    completed_phase = {}
    routing_aliases = {}
    step_to_skill = {}

    for skill_key, meta in metadata.items():
        full_name = f"ecw:{skill_key}"
        phase_name = meta.get("phase_name", skill_key)
        completed_phase[full_name] = f"{phase_name}-loaded"

        aliases = meta.get("routing_aliases", [])
        if aliases:
            routing_aliases[full_name] = aliases
            for alias in aliases:
                step_to_skill[alias] = full_name

    off_chain = {f"ecw:{s}" for s in off_chain_list}

    return {
        "completed_phase": completed_phase,
        "routing_aliases": routing_aliases,
        "step_to_skill": step_to_skill,
        "off_chain": off_chain,
    }


try:
    _mappings = _load_routes_from_file()
except Exception:
    _mappings = {
        "completed_phase": {}, "routing_aliases": {},
        "step_to_skill": {}, "off_chain": set(),
    }

SKILL_COMPLETED_PHASE = _mappings["completed_phase"]
SKILL_ROUTING_ALIASES = _mappings["routing_aliases"]
ROUTING_STEP_TO_SKILL = _mappings["step_to_skill"]
OFF_CHAIN_ALLOWED = _mappings["off_chain"]


def routing_step_to_skill(step):
    """Convert a single Routing chain step to an ECW skill name.

    Returns None for non-skill steps (e.g. Implementation(GREEN), lean plan, etc.).
    """
    step_stripped = step.strip()
    if not step_stripped:
        return None

    if step_stripped in SKILL_COMPLETED_PHASE:
        return step_stripped

    step_lower = step_stripped.lower()
    for alias, skill in ROUTING_STEP_TO_SKILL.items():
        if alias.lower() == step_lower:
            return skill

    for skill_name in SKILL_COMPLETED_PHASE:
        short = skill_name.replace("ecw:", "").lower()
        if short == step_lower:
            return skill_name

    return None


def remaining_route(routing, current_skill):
    """Extract steps after current_skill in the routing list.

    Returns [] when current_skill is not found — not the full chain.
    """
    if not routing:
        return []
    if isinstance(routing, str):
        routing = [s.strip() for s in routing.split("→")]

    aliases = SKILL_ROUTING_ALIASES.get(current_skill, [])
    short_name = current_skill.replace("ecw:", "").lower() if current_skill.startswith("ecw:") else ""

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


def check_routing_deviation(routing_list, current_skill, expected_next):
    """Check if current_skill deviates from the Routing chain.

    Returns dict with type/detail if deviation detected, None otherwise.
    """
    if current_skill in OFF_CHAIN_ALLOWED:
        return None

    if not routing_list:
        return None

    chain_skills = set()
    for step in routing_list:
        skill = routing_step_to_skill(step)
        if skill:
            chain_skills.add(skill)

    if current_skill not in chain_skills:
        return {
            "type": "off-chain",
            "detail": f"Skill '{current_skill}' not found in routing chain {routing_list}",
        }

    if expected_next and current_skill != expected_next:
        return {
            "type": "out-of-order",
            "detail": f"Expected '{expected_next}' but got '{current_skill}'",
        }

    return None


def next_skill_from_routing(routing, current_skill):
    """Find the next ECW skill to invoke after current_skill in the routing chain.

    Returns the full ECW skill name (e.g., 'ecw:impl-verify') or None.
    """
    if not routing:
        return None
    if isinstance(routing, str):
        routing = [s.strip() for s in routing.split("→")]

    aliases = SKILL_ROUTING_ALIASES.get(current_skill, [])
    short_name = current_skill.replace("ecw:", "").lower() if current_skill.startswith("ecw:") else ""

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

    for step in routing[last_match_idx + 1:]:
        skill = routing_step_to_skill(step)
        if skill:
            return skill

    return None
