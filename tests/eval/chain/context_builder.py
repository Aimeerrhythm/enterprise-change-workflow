"""Build simulated context for chain eval steps.

Handles from_step references (dict syntax) that inject prior step artifacts,
and loads fixture files as raw text (no YAML parse-and-re-dump).
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CHAIN_DIR = Path(__file__).parent


def _load_fixture(path_ref: str) -> str:
    """Load a fixture file as raw text. YAML files are NOT parsed/re-dumped."""
    if path_ref.startswith("fixtures/"):
        p = CHAIN_DIR / path_ref
    else:
        p = Path(path_ref)
    return p.read_text(encoding="utf-8")


def build_context(
    context_spec: dict,
    prior_artifacts: dict[str, dict[str, str]],
) -> str:
    """Build context string from fixtures and prior step artifacts.

    context_spec values can be:
      - A plain string: used verbatim as the section content.
      - A string starting with 'fixtures/': loaded from the fixtures directory.
      - A dict with 'from_step' key: resolved from prior step artifacts.
          {'from_step': 'skill-name'}                  → full tool_result (or text_output)
          {'from_step': 'skill-name', 'field': 'name'} → specific field value
          Special case: when the context key is 'session_state' and no 'field' is
          given, the tool_result is converted to session-state.md format.
    """
    sections = []

    for key, value in context_spec.items():
        if isinstance(value, dict) and "from_step" in value:
            content = _resolve_from_step(key, value, prior_artifacts)
            sections.append(f"### {key}\n{content}")
        elif isinstance(value, str) and value.startswith("fixtures/"):
            content = _load_fixture(value)
            sections.append(f"### {key}\n{content}")
        else:
            sections.append(f"### {key}\n{value}")

    return "\n\n".join(sections)


def _resolve_from_step(
    context_key: str,
    spec: dict,
    prior_artifacts: dict[str, dict[str, str]],
) -> str:
    step_name = spec["from_step"]
    step_artifacts = prior_artifacts.get(step_name, {})
    field = spec.get("field")

    if field is not None:
        return step_artifacts.get(f"field:{field}", "")

    # No field specified — return whole tool_result (or text_output as fallback)
    raw = step_artifacts.get("tool_result", step_artifacts.get("text_output", ""))

    # Special case: session_state key triggers session-state.md format reconstruction
    if context_key == "session_state":
        return _build_session_state_from_rc(raw)

    return raw


def _build_session_state_from_rc(tool_result_json: str) -> str:
    """Convert a risk-classifier tool_result JSON to session-state.md format.

    This is a convenience helper for chain steps that pass risk-classifier output
    directly to writing-plans as a session_state context. The format mirrors
    skills/risk-classifier/session-state-format.md.
    """
    try:
        result = json.loads(tool_result_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return "<!-- ECW:STATUS:START -->\n(parse error)\n<!-- ECW:STATUS:END -->"

    routing_str = " → ".join(result.get("routing") or [])
    domains_list = result.get("domains") or []
    domains_str = ", ".join(domains_list)

    return f"""<!-- ECW:STATUS:START -->
- **Risk Level**: {result.get('risk_level', 'P2')}
- **Domains**: {domains_str}
- **Mode**: {result.get('mode', 'single-domain')}
- **Routing**: {routing_str}
- **Current Phase**: phase1-complete
- **Created**: 2026-05-04
- **Workflow ID**: 20260504-eval
- **Baseline Commit**: eval-mock
- **Implementation Strategy**: TBD
- **Post-Implementation Tasks**: TBD
- **Auto-Continue**: yes
- **Next**: writing-plans
<!-- ECW:STATUS:END -->

<!-- ECW:MODE:START -->
- **Working Mode**: analysis
<!-- ECW:MODE:END -->

<!-- ECW:LEDGER:START -->
## Subagent Ledger

| Phase | Agent | Type | Model | Est. Scale | Started | Duration |
|-------|-------|------|-------|-----------|---------|----------|
<!-- ECW:LEDGER:END -->"""
