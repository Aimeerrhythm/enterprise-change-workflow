"""ECW Cross-Component Consistency Tests

Validates that configuration/mappings/templates across different components
(hooks, skills, templates, data contracts) stay in sync.

Each test maps to a specific historical bug — no speculative checks.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("PyYAML not installed", allow_module_level=True)


ROOT = Path(__file__).resolve().parent.parent.parent.parent
HOOKS_DIR = ROOT / "hooks"
SKILLS_DIR = ROOT / "skills"
TESTS_STATIC = Path(__file__).resolve().parent.parent


def _load_hook(name: str):
    """Load a hook module by filename (without .py)."""
    path = HOOKS_DIR / f"{name}.py"
    if not path.exists():
        pytest.skip(f"Hook {name}.py not found")
    spec = importlib.util.spec_from_file_location(
        f"ecw_hook_{name.replace('-', '_')}", path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_yaml_file(path: Path):
    if not path.exists():
        pytest.skip(f"{path} not found")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _read_skill_content(skill_name: str) -> str:
    """Read SKILL.md + all prompts/*.md for a skill."""
    skill_dir = SKILLS_DIR / skill_name
    p = skill_dir / "SKILL.md"
    if not p.exists():
        return ""
    content = p.read_text(encoding="utf-8")
    prompts_dir = skill_dir / "prompts"
    if prompts_dir.is_dir():
        for md in sorted(prompts_dir.glob("*.md")):
            content += "\n" + md.read_text(encoding="utf-8")
    return content


# ═══════════════════════════════════════════
# G1: auto-continue _SKILL_COMPLETED_PHASE vs data_contracts skill list
# Historical bug: skill added but not registered → phase not updated after completion
# ═══════════════════════════════════════════

class TestG1AutoContinueVsContracts:
    """Every workflow skill in data_contracts must have a phase mapping in auto-continue."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]
        self.excluded_skills = {"cross-review", "knowledge-audit", "knowledge-track",
                                "knowledge-repomap", "workspace"}

    def test_all_contract_skills_in_phase_mapping(self):
        missing = []
        for skill_name in self.contracts:
            if skill_name in self.excluded_skills:
                continue
            full_name = f"ecw:{skill_name}"
            if full_name not in self.hook._SKILL_COMPLETED_PHASE:
                missing.append(full_name)
        assert not missing, (
            f"Skills in data_contracts but missing from _SKILL_COMPLETED_PHASE: {missing}"
        )

    def test_all_phase_mapping_skills_in_contracts(self):
        extra = []
        for full_name in self.hook._SKILL_COMPLETED_PHASE:
            short = full_name.replace("ecw:", "")
            if short not in self.contracts and short not in self.excluded_skills:
                extra.append(full_name)
        assert not extra, (
            f"Skills in _SKILL_COMPLETED_PHASE but missing from data_contracts: {extra}"
        )


# ═══════════════════════════════════════════
# G2: Three-way mode mapping consistency
# Historical bug: 61b413a — Mode switch marker syntax mismatch across 4 skills
# ═══════════════════════════════════════════

class TestG2ModeMapThreeWaySync:
    """skill→mode mapping must be consistent between auto-continue.py and session-state-format.md."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        self.fmt_content = fmt_path.read_text(encoding="utf-8")
        self.fmt_mode_map = self._parse_mode_table(self.fmt_content)

    @staticmethod
    def _parse_mode_table(content: str) -> dict[str, str]:
        mode_map = {}
        in_table = False
        for line in content.splitlines():
            if "| Mode |" in line or "| mode |" in line:
                in_table = True
                continue
            if in_table and line.strip().startswith("|"):
                if "---" in line:
                    continue
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) < 2:
                    continue
                mode = parts[0].strip("`").strip()
                skills_text = parts[1]
                for skill in re.findall(r'([\w-]+)', skills_text):
                    if skill in ("Set", "by", "Focus", "on", "Design", "Write",
                                 "Review", "code", "Read"):
                        continue
                    if len(skill) > 3:
                        mode_map[skill] = mode
            elif in_table and not line.strip().startswith("|"):
                in_table = False
        return mode_map

    def test_hook_mode_map_matches_format_doc(self):
        mismatches = []
        for full_name, hook_mode in self.hook._SKILL_MODE.items():
            short = full_name.replace("ecw:", "")
            if short in self.fmt_mode_map:
                if hook_mode != self.fmt_mode_map[short]:
                    mismatches.append(
                        f"{short}: hook='{hook_mode}', doc='{self.fmt_mode_map[short]}'"
                    )
        assert not mismatches, (
            "Mode mapping mismatches:\n" + "\n".join(mismatches)
        )

    def test_format_doc_skills_all_in_hook(self):
        missing = []
        for skill, mode in self.fmt_mode_map.items():
            if f"ecw:{skill}" not in self.hook._SKILL_MODE:
                missing.append(f"{skill} (mode: {mode})")
        assert not missing, (
            f"Skills in session-state-format.md mode table but not in _SKILL_MODE: {missing}"
        )


# ═══════════════════════════════════════════
# G4: verify-completion keyword parsing vs impl-verify output template
# Historical bug: e8cba93, 92a384c — impl-verify convergence check failed
# ═══════════════════════════════════════════

class TestG4VerifyCompletionKeywords:
    """Keywords parsed by verify-completion.py must exist in impl-verify output templates."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.template_path = SKILLS_DIR / "impl-verify" / "output-templates.md"
        if not self.template_path.exists():
            pytest.skip("impl-verify output-templates.md not found")
        self.template_content = self.template_path.read_text(encoding="utf-8")

    def test_must_fix_keyword_in_template(self):
        assert "must-fix" in self.template_content, (
            "verify-completion.py parses 'must-fix' but output template lacks this keyword"
        )

    def test_fixed_marker_in_template_or_skill(self):
        skill_content = _read_skill_content("impl-verify")
        combined = self.template_content + "\n" + skill_content
        assert "[FIXED]" in combined, (
            "verify-completion.py parses '[FIXED]' but neither template nor SKILL.md has it"
        )

    def test_table_pipe_format_in_template(self):
        assert "|" in self.template_content and "must-fix" in self.template_content, (
            "verify-completion.py identifies findings by '|' + 'must-fix' in table rows"
        )


# ═══════════════════════════════════════════
# G5: auto-continue routing aliases vs workflow-routes.yml chain steps
# Historical bug: TDD:RED alias not recognized → routing skipped
# ═══════════════════════════════════════════

class TestG5RoutingAliasesVsRoutes:
    """Non-standard routing step names must be registered as aliases in auto-continue."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        routes_data = _load_yaml_file(
            SKILLS_DIR / "risk-classifier" / "workflow-routes.yml"
        )
        self.routes = routes_data["routes"]

    def _is_ecw_skill(self, step: str) -> bool:
        for skill_name in self.hook._SKILL_COMPLETED_PHASE:
            short = skill_name.replace("ecw:", "")
            if short == step.lower() or short == step:
                return True
        return False

    def _is_phase_marker(self, step: str) -> bool:
        phase_patterns = ["Phase", "lean plan", "Implementation + mvn",
                          "Phase 1 quick", "Implementation(GREEN)", "Fix(GREEN)"]
        return any(p.lower() in step.lower() for p in phase_patterns)

    def test_all_non_standard_steps_have_alias(self):
        all_steps = set()
        for route in self.routes:
            for step in route.get("chain", []):
                all_steps.add(step)

        known_aliases = set()
        for aliases in self.hook._SKILL_ROUTING_ALIASES.values():
            known_aliases.update(aliases)
        for alias in self.hook._ROUTING_STEP_TO_SKILL:
            known_aliases.add(alias)

        unmapped = []
        for step in sorted(all_steps):
            if self._is_ecw_skill(step) or self._is_phase_marker(step):
                continue
            if step in known_aliases:
                continue
            unmapped.append(step)

        assert not unmapped, (
            f"Routing steps not recognized as skills, phases, or aliases: {unmapped}"
        )

    def test_alias_targets_are_valid_skills(self):
        invalid = []
        for alias, skill in self.hook._ROUTING_STEP_TO_SKILL.items():
            if skill not in self.hook._SKILL_COMPLETED_PHASE:
                invalid.append(f"'{alias}' → '{skill}'")
        assert not invalid, (
            f"_ROUTING_STEP_TO_SKILL targets not valid skills: {invalid}"
        )


# ═══════════════════════════════════════════
# G9: Marker format consistency across all SKILL.md files
# Historical bug: a52aab6 — marker enforcement, 61b413a — marker syntax
# ═══════════════════════════════════════════

class TestG9MarkerFormatConsistency:
    """All SKILL.md files must use the exact marker format that marker_utils.py expects."""

    EXPECTED_MARKERS = {
        "STATUS": ("<!-- ECW:STATUS:START -->", "<!-- ECW:STATUS:END -->"),
        "MODE": ("<!-- ECW:MODE:START -->", "<!-- ECW:MODE:END -->"),
        "LEDGER": ("<!-- ECW:LEDGER:START -->", "<!-- ECW:LEDGER:END -->"),
        "STOP": ("<!-- ECW:STOP:START -->", "<!-- ECW:STOP:END -->"),
    }

    def test_marker_format_in_skills(self):
        violations = []
        marker_re = re.compile(r'<!--\s*ECW:(\w+):(START|END)\s*-->')

        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            content = _read_skill_content(skill_dir.name)
            if not content:
                continue

            for m in marker_re.finditer(content):
                name, tag = m.group(1), m.group(2)
                actual = m.group(0)
                if name in self.EXPECTED_MARKERS:
                    expected = self.EXPECTED_MARKERS[name][0 if tag == "START" else 1]
                    if actual != expected:
                        violations.append(
                            f"skills/{skill_dir.name}: '{actual}' != '{expected}'"
                        )

        assert not violations, (
            "Marker format inconsistencies:\n" + "\n".join(violations)
        )

    def test_session_state_format_uses_correct_markers(self):
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        content = fmt_path.read_text(encoding="utf-8")

        for name, (start, end) in self.EXPECTED_MARKERS.items():
            if name == "STOP":
                continue
            assert start in content, f"Missing marker '{start}'"
            assert end in content, f"Missing marker '{end}'"


# ═══════════════════════════════════════════
# G11: parse_status (YAML) vs session-state-format.md
# Historical bug: auto-continue regex didn't match changed field format (Issue #40: migrated to YAML)
# ═══════════════════════════════════════════

class TestG11FieldPatternsVsTemplate:
    """parse_status must correctly parse YAML fields that appear in the session-state template."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        self.fmt_content = fmt_path.read_text(encoding="utf-8")

    def test_parse_status_extracts_required_fields(self):
        """parse_status must correctly extract all routing-critical fields from YAML STATUS."""
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("marker_utils", ROOT / "hooks" / "marker_utils.py")
        mu = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mu)

        synthetic_status = (
            "<!-- ECW:STATUS:START -->\n"
            "risk_level: P1\n"
            "auto_continue: true\n"
            "routing: [ecw:risk-classifier, ecw:writing-plans]\n"
            "next: ecw:writing-plans\n"
            "current_phase: phase1-complete\n"
            "<!-- ECW:STATUS:END -->\n"
        )
        fields = mu.parse_status(synthetic_status)
        assert fields is not None, "parse_status must succeed on valid YAML STATUS"
        assert fields.get("risk_level") == "P1"
        assert fields.get("auto_continue") is True
        assert isinstance(fields.get("routing"), list)
        assert "ecw:writing-plans" in fields.get("routing", [])
        assert fields.get("next") == "ecw:writing-plans"

    def test_field_names_exist_in_template(self):
        """YAML field names used by parse_status must appear in the session-state template."""
        required_yaml_keys = ["risk_level", "auto_continue", "routing", "next", "current_phase"]
        missing = []
        for key in required_yaml_keys:
            if key not in self.fmt_content:
                missing.append(key)
        assert not missing, (
            f"YAML keys used by parse_status but missing from template: {missing}"
        )
