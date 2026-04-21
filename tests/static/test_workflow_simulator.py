"""ECW Workflow Simulator — Cross-Validation Tests

Verifies consistency between routing_matrix.yaml, data_contracts.yaml,
and workflow_traces.yaml golden fixtures. No LLM calls required.

Tests:
1. Trace skill chains satisfy routing_matrix must_include/must_exclude
2. Mode transitions are monotonically non-decreasing
3. Checkpoint writes match data_contracts.yaml declarations
4. Read dependencies are satisfied by upstream writers in each chain
5. Ask-user skills match data_contracts.yaml ask_user_question flags
6. Every routing_matrix entry has a corresponding trace
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("PyYAML not installed", allow_module_level=True)


ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_STATIC = Path(__file__).resolve().parent

MODE_ORDER = {"analysis": 0, "planning": 1, "implementation": 2, "verification": 3}

MODE_MAP = {
    "risk-classifier": "analysis",
    "risk-classifier-phase2": "analysis",
    "risk-classifier-phase3": "verification",
    "requirements-elicitation": "analysis",
    "domain-collab": "analysis",
    "writing-plans": "planning",
    "spec-challenge": "planning",
    "tdd": "implementation",
    "impl-orchestration": "implementation",
    "systematic-debugging": "implementation",
    "impl-verify": "verification",
    "biz-impact-analysis": "verification",
    "cross-review": "verification",
}


def _load_yaml(name: str):
    path = TESTS_STATIC / name
    if not path.exists():
        pytest.skip(f"{name} not found")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _condition_active(condition: str, level: str, domain_scope: str, change_type: str) -> bool:
    if not condition:
        return True
    c = condition.lower()
    if "degradable" in c or "if exists" in c:
        return False
    if domain_scope != "any":
        if "single-domain" in c and domain_scope == "cross-domain":
            return False
        if "cross-domain" in c and domain_scope == "single-domain":
            return False
    if "p0/p1" in c and level not in ("P0", "P1", "any"):
        return False
    if "not bug" in c and change_type == "bug":
        return False
    if "not fast-track" in c and change_type == "fast-track":
        return False
    if "requirement" in c and "not" not in c and change_type != "requirement":
        return False
    return True


@pytest.fixture(scope="module")
def traces():
    return _load_yaml("workflow_traces.yaml")["traces"]


@pytest.fixture(scope="module")
def routing_matrix():
    return _load_yaml("routing_matrix.yaml")


@pytest.fixture(scope="module")
def contracts():
    return _load_yaml("data_contracts.yaml")["skills"]


# ═══════════════════════════════════════════
# Test 1: Trace skill chains vs routing matrix
# ═══════════════════════════════════════════

class TestTraceRoutingConsistency:
    """Traces must satisfy routing_matrix must_include/must_exclude."""

    @staticmethod
    def _find_route(routing_matrix, level, mode, change_type):
        for entry in routing_matrix:
            e_level = entry.get("level", "any")
            e_mode = entry.get("mode", "any")
            e_type = entry.get("type", "")
            level_match = (e_level == level or e_level == "any" or level == "any")
            mode_match = (e_mode == mode or e_mode == "any" or mode == "any")
            type_match = (e_type == change_type)
            if level_match and mode_match and type_match:
                return entry
        return None

    def test_trace_satisfies_routing_matrix(self, traces, routing_matrix):
        violations = []
        for trace in traces:
            inp = trace["input"]
            chain = trace["expected"]["skill_chain"]
            chain_skills = {s.replace("-phase2", "").replace("-phase3", "") for s in chain}

            route = self._find_route(
                routing_matrix, inp["risk_level"], inp["domain_scope"], inp["change_type"]
            )
            if route is None:
                violations.append(f"{trace['name']}: no matching route in routing_matrix")
                continue

            for skill in route.get("must_include", []):
                if skill not in chain_skills:
                    violations.append(
                        f"{trace['name']}: must_include '{skill}' missing from chain"
                    )

            for skill in route.get("must_exclude", []):
                if skill in chain_skills:
                    violations.append(
                        f"{trace['name']}: must_exclude '{skill}' present in chain"
                    )

        assert not violations, "Routing violations:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 2: Mode transition monotonicity
# ═══════════════════════════════════════════

class TestModeTransitions:
    """Mode transitions must be monotonically non-decreasing."""

    def test_mode_transitions_monotonic(self, traces):
        violations = []
        for trace in traces:
            chain = trace["expected"]["skill_chain"]
            prev_order = -1
            prev_mode = None
            for skill in chain:
                mode = MODE_MAP.get(skill)
                if mode is None:
                    continue
                order = MODE_ORDER[mode]
                if order < prev_order:
                    violations.append(
                        f"{trace['name']}: mode regression {prev_mode} → {mode} "
                        f"at skill '{skill}'"
                    )
                prev_order = order
                prev_mode = mode

        assert not violations, "Mode regressions:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 3: Checkpoint writes vs data contracts
# ═══════════════════════════════════════════

class TestCheckpointConsistency:
    """Checkpoint writes in traces must match data_contracts.yaml declarations."""

    def test_checkpoint_writes_declared_in_contracts(self, traces, contracts):
        """Every checkpoint write in a trace must be declared in data_contracts.yaml."""
        violations = []
        for trace in traces:
            for w in trace["expected"].get("checkpoint_writes", []):
                real_skill = w["skill"].replace("-phase2", "").replace("-phase3", "")
                spec = contracts.get(real_skill, {})
                declared_keys = {entry["key"] for entry in (spec.get("writes", []) or [])}
                if w["key"] not in declared_keys:
                    violations.append(
                        f"{trace['name']}: checkpoint ({w['skill']}, {w['key']}) "
                        f"not declared in data_contracts.yaml for '{real_skill}'"
                    )

        assert not violations, "Undeclared checkpoint writes:\n" + "\n".join(violations)

    def test_mandatory_writes_present_in_trace(self, traces, contracts):
        """Unconditional writes for skills in chain must appear in trace checkpoint_writes."""
        violations = []
        for trace in traces:
            chain = trace["expected"]["skill_chain"]
            trace_writes = {(w["skill"], w["key"]) for w in trace["expected"].get("checkpoint_writes", [])}

            for skill in chain:
                real_skill = skill.replace("-phase2", "").replace("-phase3", "")
                spec = contracts.get(real_skill, {})

                for entry in spec.get("writes", []) or []:
                    condition = entry.get("condition", "")
                    if condition:
                        continue
                    if (skill, entry["key"]) not in trace_writes and \
                       (real_skill, entry["key"]) not in trace_writes:
                        violations.append(
                            f"{trace['name']}: {skill} must write '{entry['key']}' "
                            f"(unconditional) but not in trace checkpoint_writes"
                        )

        assert not violations, "Missing mandatory writes:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 4: Read dependency satisfaction
# ═══════════════════════════════════════════

class TestDependencySatisfaction:
    """Every active read dependency must be satisfied by a prior write in the chain."""

    def test_read_dependencies_satisfied(self, traces, contracts):
        violations = []
        for trace in traces:
            inp = trace["input"]
            chain = trace["expected"]["skill_chain"]
            writes_available = {"session-state"}

            for skill in chain:
                real_skill = skill.replace("-phase2", "").replace("-phase3", "")
                spec = contracts.get(real_skill, {})

                for read_entry in spec.get("reads", []) or []:
                    key = read_entry["key"]
                    if key == "session-state":
                        continue
                    condition = read_entry.get("condition", "")
                    if not _condition_active(
                        condition, inp["risk_level"], inp["domain_scope"], inp["change_type"]
                    ):
                        continue
                    if key not in writes_available:
                        violations.append(
                            f"{trace['name']}: {skill} reads '{key}' "
                            f"but not produced by upstream. Available: {writes_available}"
                        )

                for write_entry in spec.get("writes", []) or []:
                    writes_available.add(write_entry["key"])

        assert not violations, "Unsatisfied dependencies:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 5: Ask-user skill consistency
# ═══════════════════════════════════════════

class TestAskUserConsistency:
    """Ask-user skills in traces must match data_contracts.yaml ask_user_question flags."""

    def test_ask_user_skills_consistent(self, traces, contracts):
        violations = []
        for trace in traces:
            chain = trace["expected"]["skill_chain"]
            trace_ask = set(trace["expected"].get("ask_user_skills", []))

            for skill in chain:
                real_skill = skill.replace("-phase2", "").replace("-phase3", "")
                spec = contracts.get(real_skill, {})
                expects_ask = spec.get("ask_user_question", False)

                if skill != real_skill:
                    continue

                if expects_ask and skill not in trace_ask:
                    violations.append(
                        f"{trace['name']}: {skill} has ask_user_question=true "
                        f"but not in trace ask_user_skills"
                    )
                if not expects_ask and skill in trace_ask:
                    violations.append(
                        f"{trace['name']}: {skill} has ask_user_question=false "
                        f"but listed in trace ask_user_skills"
                    )

        assert not violations, "Ask-user inconsistencies:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 6: Route completeness
# ═══════════════════════════════════════════

class TestRouteCompleteness:
    """Every routing_matrix entry must have at least one matching trace."""

    def test_all_routes_covered(self, traces, routing_matrix):
        uncovered = []
        for entry in routing_matrix:
            level = entry.get("level", "any")
            mode = entry.get("mode", "any")
            change_type = entry.get("type", "")

            found = False
            for trace in traces:
                inp = trace["input"]
                level_match = (level == "any" or inp["risk_level"] == "any" or inp["risk_level"] == level)
                mode_match = (mode == "any" or inp["domain_scope"] == "any" or inp["domain_scope"] == mode)
                type_match = (inp["change_type"] == change_type)
                if level_match and mode_match and type_match:
                    found = True
                    break

            if not found:
                uncovered.append(f"{change_type}/{level}/{mode}")

        assert not uncovered, f"Routing entries without traces: {uncovered}"
