"""ECW Skill Data Contract Verification Tests

Validates that the file I/O contracts between skills are consistent:
- Writers produce files that readers expect
- session-state.md fields are a superset of all downstream reads
- Every routing chain satisfies all dependency requirements
- Degradation paths are documented for all read dependencies
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("PyYAML not installed", allow_module_level=True)


ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
TESTS_STATIC = Path(__file__).resolve().parent

KEY_ALIASES = {
    "requirements-summary": [
        "requirements-summary", "requirement summary",
        "requirements-elicitation output", "requirement document",
        "Requirement summary path",
    ],
    "domain-collab-report": [
        "domain-collab-report", "domain-collab report",
        "domain collaboration", "domain-collab",
    ],
    "plan-file": [
        "Plan file", ".claude/plans/", "plan file", "writing-plans",
    ],
    "knowledge-summary": [
        "knowledge-summary", "knowledge summary",
    ],
    "phase2-assessment": [
        "phase2-assessment", "Phase 2",
    ],
    "spec-challenge-report": [
        "spec-challenge-report", "spec-challenge",
    ],
    "impl-verify-findings": [
        "impl-verify-findings", "impl-verify",
    ],
    "debug-evidence": [
        "debug-evidence", "debug evidence",
    ],
    "session-state": [
        "session-state",
    ],
    "calibration-log": [
        "calibration-log",
    ],
    "calibration-history": [
        "calibration-history",
    ],
    "instincts": [
        "instincts",
    ],
}


def _load_yaml(name: str):
    path = TESTS_STATIC / name
    if not path.exists():
        pytest.skip(f"{name} not found")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_skill(skill_name: str) -> str:
    p = SKILLS_DIR / skill_name / "SKILL.md"
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _key_mentioned_in(key: str, content: str) -> bool:
    for alias in KEY_ALIASES.get(key, [key]):
        if alias in content:
            return True
    return False


@pytest.fixture(scope="module")
def contracts():
    return _load_yaml("data_contracts.yaml")["skills"]


@pytest.fixture(scope="module")
def routing_matrix():
    return _load_yaml("routing_matrix.yaml")


@pytest.fixture(scope="module")
def all_skill_dirs():
    if not SKILLS_DIR.exists():
        return set()
    return {
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    }


def _all_writers(contracts: dict) -> dict[str, str]:
    writers = {}
    for skill_name, spec in contracts.items():
        for entry in spec.get("writes", []) or []:
            writers[entry["key"]] = skill_name
    return writers


# ═══════════════════════════════════════════
# Test 1: Writer path patterns exist in SKILL.md
# ═══════════════════════════════════════════

class TestWriterPaths:
    def test_writer_path_exists_in_skill(self, contracts):
        """Every writes entry's path_pattern must appear in the corresponding SKILL.md."""
        missing = []
        for skill_name, spec in contracts.items():
            content = _read_skill(skill_name)
            if not content:
                continue
            for entry in spec.get("writes", []) or []:
                pattern = entry["path_pattern"]
                if pattern not in content:
                    missing.append(
                        f"{skill_name}: writes '{entry['key']}' with "
                        f"path_pattern '{pattern}' not found in SKILL.md"
                    )
        assert not missing, "Writer path patterns missing from SKILL.md:\n" + "\n".join(missing)


# ═══════════════════════════════════════════
# Test 2: Reader references exist in SKILL.md
# ═══════════════════════════════════════════

class TestReaderPaths:
    def test_reader_path_exists_in_skill(self, contracts):
        """Every reads entry's key (or alias) must be findable in the consuming SKILL.md."""
        missing = []
        for skill_name, spec in contracts.items():
            content = _read_skill(skill_name)
            if not content:
                continue
            for entry in spec.get("reads", []) or []:
                key = entry["key"]
                if not _key_mentioned_in(key, content):
                    missing.append(
                        f"{skill_name}: reads '{key}' but no matching "
                        f"reference found in SKILL.md"
                    )
        assert not missing, "Reader references missing from SKILL.md:\n" + "\n".join(missing)


# ═══════════════════════════════════════════
# Test 3: Every reader has an upstream writer
# ═══════════════════════════════════════════

class TestUpstreamWriters:
    def test_reader_has_upstream_writer(self, contracts):
        """Every reads entry (except session-state) must have a producing skill."""
        writers = _all_writers(contracts)
        orphans = []
        for skill_name, spec in contracts.items():
            for entry in spec.get("reads", []) or []:
                key = entry["key"]
                if key == "session-state":
                    continue
                if key not in writers:
                    orphans.append(f"{skill_name} reads '{key}' but no skill writes it")
        assert not orphans, "Orphan reads (no upstream writer):\n" + "\n".join(orphans)


# ═══════════════════════════════════════════
# Test 4: session-state fields superset
# ═══════════════════════════════════════════

class TestSessionStateFields:
    def test_session_state_fields_superset(self, contracts):
        """risk-classifier's required_fields must be a superset of all downstream reads."""
        rc_spec = contracts.get("risk-classifier", {})
        rc_writes = {w["key"]: w for w in (rc_spec.get("writes", []) or [])}
        ss_entry = rc_writes.get("session-state")
        if not ss_entry:
            pytest.skip("risk-classifier has no session-state writes entry")

        producer_fields = set(ss_entry.get("required_fields", []))

        violations = []
        for skill_name, spec in contracts.items():
            if skill_name == "risk-classifier":
                continue
            for entry in spec.get("reads", []) or []:
                if entry["key"] != "session-state":
                    continue
                for field in entry.get("fields", []):
                    if field not in producer_fields:
                        violations.append(
                            f"{skill_name} reads session-state field '{field}' "
                            f"but risk-classifier does not declare it in required_fields"
                        )
        assert not violations, "session-state field gaps:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 5: Routing chain covers all dependencies
# ═══════════════════════════════════════════

def _condition_applies(condition: str, level: str, mode: str, change_type: str) -> bool:
    """Return True if this read dependency is active given the route context."""
    if not condition:
        return True
    c = condition.lower()
    if "if exists" in c or "degradable" in c:
        return False
    if "single-domain" in c and mode == "cross-domain":
        return False
    if "cross-domain" in c and mode == "single-domain":
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


class TestRoutingDependencies:
    @staticmethod
    def _skill_chain_for_route(entry: dict) -> list[str]:
        must_include = entry.get("must_include", [])
        level = entry.get("level", "")
        change_type = entry.get("type", "")

        chain = ["risk-classifier"]

        if change_type == "requirement":
            if "requirements-elicitation" in must_include:
                chain.append("requirements-elicitation")
            if "domain-collab" in must_include:
                chain.append("domain-collab")
            if level in ("P0", "P1"):
                chain.append("risk-classifier-phase2")
            if "writing-plans" in must_include:
                chain.append("writing-plans")
            if "spec-challenge" in must_include:
                chain.append("spec-challenge")
            if "tdd" in must_include:
                chain.append("tdd")
            if "impl-verify" in must_include:
                chain.append("impl-verify")
            if "biz-impact-analysis" in must_include:
                chain.append("biz-impact-analysis")
        elif change_type == "bug":
            if "systematic-debugging" in must_include:
                chain.append("systematic-debugging")
            chain.append("tdd")
            if "impl-verify" in must_include:
                chain.append("impl-verify")
            if "biz-impact-analysis" in must_include:
                chain.append("biz-impact-analysis")
        elif change_type == "fast-track":
            if "impl-verify" in must_include:
                chain.append("impl-verify")
            if "biz-impact-analysis" in must_include:
                chain.append("biz-impact-analysis")

        return chain

    def test_routing_chain_covers_dependencies(self, contracts, routing_matrix):
        """For each routing chain, every active read dependency must have an upstream writer."""
        violations = []

        for entry in routing_matrix:
            level = entry.get("level", "any")
            mode = entry.get("mode", "any")
            ctype = entry.get("type", "")
            route_label = f"{ctype}/{level}/{mode}"

            chain = self._skill_chain_for_route(entry)

            writes_available = {"session-state"}

            for skill_name in chain:
                real_name = skill_name.replace("-phase2", "").replace("-phase3", "")
                spec = contracts.get(real_name, {})

                for read_entry in spec.get("reads", []) or []:
                    key = read_entry["key"]
                    condition = read_entry.get("condition", "")

                    if key == "session-state":
                        continue

                    if not _condition_applies(condition, level, mode, ctype):
                        continue

                    if key not in writes_available:
                        violations.append(
                            f"[{route_label}] {skill_name} reads '{key}' but "
                            f"no upstream skill in chain writes it. "
                            f"Chain: {' → '.join(chain)}"
                        )

                for write_entry in spec.get("writes", []) or []:
                    writes_available.add(write_entry["key"])

        assert not violations, "Routing dependency gaps:\n" + "\n".join(violations)


# ═══════════════════════════════════════════
# Test 6: Degradation paths documented
# ═══════════════════════════════════════════

DEGRADATION_KEYWORDS = [
    "not found", "missing", "degraded", "not exist",
    "缺失", "找不到", "skip", "Skip",
    "unavailable", "warning", "Warning",
]


class TestDegradationPaths:
    def test_degradation_path_documented(self, contracts):
        """Skills that read checkpoint files must document degradation handling."""
        missing = []
        for skill_name, spec in contracts.items():
            content = _read_skill(skill_name)
            if not content:
                continue
            for entry in spec.get("reads", []) or []:
                key = entry["key"]
                if key == "session-state":
                    continue
                has_degradation = any(kw in content for kw in DEGRADATION_KEYWORDS)
                if not has_degradation:
                    missing.append(
                        f"{skill_name}: reads '{key}' but no degradation handling "
                        f"keywords found in SKILL.md"
                    )
        assert not missing, "Missing degradation documentation:\n" + "\n".join(missing)


# ═══════════════════════════════════════════
# Test 7: Contract YAML completeness
# ═══════════════════════════════════════════

class TestContractCompleteness:
    def test_contract_yaml_completeness(self, contracts, all_skill_dirs):
        """data_contracts.yaml must list every skill in skills/ directory."""
        contract_skills = set(contracts.keys())
        missing = all_skill_dirs - contract_skills
        extra = contract_skills - all_skill_dirs
        errors = []
        if missing:
            errors.append(f"Skills in skills/ but not in data_contracts.yaml: {missing}")
        if extra:
            errors.append(f"Skills in data_contracts.yaml but not in skills/: {extra}")
        assert not errors, "\n".join(errors)
