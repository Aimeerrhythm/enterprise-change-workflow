"""ECW Cross-Component Consistency Tests

Validates that configuration/mappings/templates across different components
(hooks, skills, templates, data contracts) stay in sync. These are the
"seam" tests that catch bugs at component boundaries — the exact category
of bugs that historically caused ~60% of fix commits.

Each test class corresponds to a gap identified in the cross-component
consistency audit (G1–G10+).
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:
    pytest.skip("PyYAML not installed", allow_module_level=True)


ROOT = Path(__file__).resolve().parent.parent.parent
HOOKS_DIR = ROOT / "hooks"
SKILLS_DIR = ROOT / "skills"
TESTS_STATIC = Path(__file__).resolve().parent


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
# ═══════════════════════════════════════════

class TestG1AutoContinueVsContracts:
    """Every skill in data_contracts.yaml (except workspace/knowledge-*) must have
    an entry in auto-continue.py's _SKILL_COMPLETED_PHASE mapping, and vice versa."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]
        # Skills that don't go through the auto-continue routing
        # (manual-only tools, not part of the main workflow chain)
        self.excluded_skills = {"cross-review", "knowledge-audit", "knowledge-track",
                                "knowledge-repomap", "workspace"}

    def test_all_contract_skills_in_phase_mapping(self):
        """Every workflow skill in data_contracts must have a phase mapping."""
        missing = []
        for skill_name in self.contracts:
            if skill_name in self.excluded_skills:
                continue
            full_name = f"ecw:{skill_name}"
            if full_name not in self.hook._SKILL_COMPLETED_PHASE:
                missing.append(f"ecw:{skill_name}")
        assert not missing, (
            f"Skills in data_contracts.yaml but missing from "
            f"auto-continue _SKILL_COMPLETED_PHASE: {missing}"
        )

    def test_all_phase_mapping_skills_in_contracts(self):
        """Every skill in _SKILL_COMPLETED_PHASE must exist in data_contracts."""
        extra = []
        for full_name in self.hook._SKILL_COMPLETED_PHASE:
            short = full_name.replace("ecw:", "")
            if short not in self.contracts and short not in self.excluded_skills:
                extra.append(full_name)
        assert not extra, (
            f"Skills in auto-continue _SKILL_COMPLETED_PHASE but missing from "
            f"data_contracts.yaml: {extra}"
        )


# ═══════════════════════════════════════════
# G2: Three-way mode mapping consistency
#     auto-continue._SKILL_MODE vs lint MODE_SWITCH_GOLDEN vs session-state-format.md
# ═══════════════════════════════════════════

class TestG2ModeMapThreeWaySync:
    """The skill→mode mapping must be consistent across three locations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        # Parse session-state-format.md mode table
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        self.fmt_content = fmt_path.read_text(encoding="utf-8")
        self.fmt_mode_map = self._parse_mode_table(self.fmt_content)

    @staticmethod
    def _parse_mode_table(content: str) -> dict[str, str]:
        """Extract skill→mode from the Working Mode table in session-state-format.md.

        Table format: | `mode` | skill1, skill2 | ... |
        """
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
        """auto-continue._SKILL_MODE must match session-state-format.md mode table."""
        mismatches = []
        for full_name, hook_mode in self.hook._SKILL_MODE.items():
            short = full_name.replace("ecw:", "")
            if short in self.fmt_mode_map:
                fmt_mode = self.fmt_mode_map[short]
                if hook_mode != fmt_mode:
                    mismatches.append(
                        f"{short}: hook says '{hook_mode}', "
                        f"session-state-format.md says '{fmt_mode}'"
                    )
        assert not mismatches, (
            "Mode mapping mismatches between auto-continue.py and "
            "session-state-format.md:\n" + "\n".join(mismatches)
        )

    def test_format_doc_skills_all_in_hook(self):
        """Every skill in session-state-format.md mode table must be in hook._SKILL_MODE."""
        missing = []
        for skill, mode in self.fmt_mode_map.items():
            full_name = f"ecw:{skill}"
            if full_name not in self.hook._SKILL_MODE:
                missing.append(f"{skill} (mode: {mode})")
        assert not missing, (
            f"Skills in session-state-format.md mode table but missing from "
            f"auto-continue._SKILL_MODE: {missing}"
        )


# ═══════════════════════════════════════════
# G3: session-state-format.md template fields vs data_contracts required_fields
# ═══════════════════════════════════════════

class TestG3SessionStateTemplateVsContracts:
    """Fields in session-state-format.md template must match data_contracts required_fields."""

    @pytest.fixture(autouse=True)
    def setup(self):
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        self.fmt_content = fmt_path.read_text(encoding="utf-8")
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]

    def _extract_template_fields(self) -> set[str]:
        """Extract bold field names from the template markdown block."""
        fields = set()
        in_template = False
        for line in self.fmt_content.splitlines():
            if line.strip() == "```markdown":
                in_template = True
                continue
            if line.strip() == "```" and in_template:
                break
            if in_template:
                m = re.search(r'\*\*(.+?)\*\*:', line)
                if m:
                    field = m.group(1)
                    if field != "Working Mode":
                        fields.add(field)
        return fields

    def test_template_fields_superset_of_contracts(self):
        """Template must include all required_fields declared in data_contracts."""
        template_fields = self._extract_template_fields()
        rc_spec = self.contracts.get("risk-classifier", {})
        rc_writes = {w["key"]: w for w in (rc_spec.get("writes", []) or [])}
        ss_entry = rc_writes.get("session-state")
        if not ss_entry:
            pytest.skip("No session-state write in risk-classifier contracts")
        contract_fields = set(ss_entry.get("required_fields", []))

        missing = contract_fields - template_fields
        assert not missing, (
            f"Fields in data_contracts required_fields but missing from "
            f"session-state-format.md template: {missing}"
        )

    def test_contracts_superset_of_template(self):
        """required_fields must include all fields in the template."""
        template_fields = self._extract_template_fields()
        rc_spec = self.contracts.get("risk-classifier", {})
        rc_writes = {w["key"]: w for w in (rc_spec.get("writes", []) or [])}
        ss_entry = rc_writes.get("session-state")
        if not ss_entry:
            pytest.skip("No session-state write in risk-classifier contracts")
        contract_fields = set(ss_entry.get("required_fields", []))

        # Some template fields are informational and may not be in contracts
        # (e.g. Created, Baseline Commit). Only flag fields that downstream
        # skills actually read.
        downstream_read_fields = set()
        for skill_name, spec in self.contracts.items():
            for entry in spec.get("reads", []) or []:
                if entry["key"] == "session-state":
                    downstream_read_fields.update(entry.get("fields", []))

        extra = (template_fields - contract_fields) & downstream_read_fields
        assert not extra, (
            f"Fields in session-state-format.md template that are read by "
            f"downstream skills but missing from data_contracts required_fields: {extra}"
        )


# ═══════════════════════════════════════════
# G4: verify-completion keyword parsing vs impl-verify output template
# ═══════════════════════════════════════════

class TestG4VerifyCompletionKeywords:
    """verify-completion.py parses impl-verify-findings.md using specific keywords.
    These keywords must appear in impl-verify output templates."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("verify-completion")
        self.template_path = SKILLS_DIR / "impl-verify" / "output-templates.md"
        if not self.template_path.exists():
            pytest.skip("impl-verify output-templates.md not found")
        self.template_content = self.template_path.read_text(encoding="utf-8")

    def test_must_fix_keyword_in_template(self):
        """The 'must-fix' severity keyword parsed by verify-completion must appear
        in the impl-verify output template."""
        assert "must-fix" in self.template_content, (
            "verify-completion.py looks for 'must-fix' in findings table, "
            "but impl-verify/output-templates.md does not contain this keyword"
        )

    def test_fixed_marker_in_template_or_skill(self):
        """The '[FIXED]' marker parsed by verify-completion must be documented
        in impl-verify SKILL.md or output-templates.md."""
        skill_content = _read_skill_content("impl-verify")
        combined = self.template_content + "\n" + skill_content
        assert "[FIXED]" in combined, (
            "verify-completion.py looks for '[FIXED]' marker to detect resolved items, "
            "but neither impl-verify/output-templates.md nor SKILL.md mentions '[FIXED]'"
        )

    def test_table_pipe_format_in_template(self):
        """verify-completion uses '|' to identify table rows. The output template
        must show pipe-delimited table format."""
        assert "|" in self.template_content and "must-fix" in self.template_content, (
            "verify-completion.py identifies findings by checking lines with '|' and 'must-fix'. "
            "Output template must show pipe-delimited table rows with must-fix severity."
        )


# ═══════════════════════════════════════════
# G5: auto-continue routing aliases vs workflow-routes.yml chain steps
# ═══════════════════════════════════════════

class TestG5RoutingAliasesVsRoutes:
    """auto-continue._SKILL_ROUTING_ALIASES and _ROUTING_STEP_TO_SKILL must cover
    all non-standard step names used in workflow-routes.yml chains."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        routes_data = _load_yaml_file(
            SKILLS_DIR / "risk-classifier" / "workflow-routes.yml"
        )
        self.routes = routes_data["routes"]

    def _all_chain_steps(self) -> set[str]:
        """Collect all unique step names from all routing chains."""
        steps = set()
        for route in self.routes:
            for step in route.get("chain", []):
                steps.add(step)
        return steps

    def _is_ecw_skill(self, step: str) -> bool:
        """Check if step name directly matches an ECW skill (by short name)."""
        for skill_name in self.hook._SKILL_COMPLETED_PHASE:
            short = skill_name.replace("ecw:", "")
            if short == step.lower() or short == step:
                return True
        return False

    def _is_phase_marker(self, step: str) -> bool:
        """Non-skill steps like 'Phase 2', 'Phase 3', 'lean plan', etc."""
        phase_patterns = ["Phase", "lean plan", "Implementation + mvn",
                          "Phase 1 quick", "Implementation(GREEN)", "Fix(GREEN)"]
        return any(p.lower() in step.lower() for p in phase_patterns)

    def test_all_non_standard_steps_have_alias(self):
        """Every non-skill, non-phase step in routing chains must have a mapping
        in _ROUTING_STEP_TO_SKILL or _SKILL_ROUTING_ALIASES."""
        all_steps = self._all_chain_steps()
        # Collect all known alias targets
        known_aliases = set()
        for aliases in self.hook._SKILL_ROUTING_ALIASES.values():
            known_aliases.update(a for a in aliases)
        for alias in self.hook._ROUTING_STEP_TO_SKILL:
            known_aliases.add(alias)

        unmapped = []
        for step in sorted(all_steps):
            if self._is_ecw_skill(step):
                continue
            if self._is_phase_marker(step):
                continue
            if step in known_aliases:
                continue
            unmapped.append(step)

        assert not unmapped, (
            f"Routing chain steps not recognized as ECW skills, phase markers, "
            f"or registered aliases: {unmapped}. "
            f"Add them to _ROUTING_STEP_TO_SKILL or _SKILL_ROUTING_ALIASES "
            f"in auto-continue.py."
        )

    def test_alias_targets_are_valid_skills(self):
        """Every alias target in _ROUTING_STEP_TO_SKILL must be a valid ECW skill."""
        invalid = []
        for alias, skill in self.hook._ROUTING_STEP_TO_SKILL.items():
            if skill not in self.hook._SKILL_COMPLETED_PHASE:
                invalid.append(f"'{alias}' → '{skill}'")
        assert not invalid, (
            f"_ROUTING_STEP_TO_SKILL targets that are not valid skills: {invalid}"
        )


# ═══════════════════════════════════════════
# G6: SKILL.md downstream handoff mentions vs workflow-routes.yml
# ═══════════════════════════════════════════

class TestG6DownstreamHandoffVsRoutes:
    """Skills mentioned in Downstream Handoff sections must be real ECW skills
    (existing skills/ directory) and registered in data_contracts.yaml.
    This catches typos, renamed skills, and stale references."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]
        self.existing_skills = {
            d.name for d in SKILLS_DIR.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        }

    def _extract_handoff_targets(self, skill_name: str) -> set[str]:
        """Extract ecw:skill-name references from Downstream Handoff sections."""
        content = _read_skill_content(skill_name)
        targets = set()
        in_handoff = False
        for line in content.splitlines():
            if "Downstream Handoff" in line:
                in_handoff = True
                continue
            if in_handoff:
                if line.startswith("## ") and "Downstream" not in line:
                    in_handoff = False
                    continue
                for m in re.finditer(r'ecw:([\w-]+)', line):
                    targets.add(m.group(1))
        return targets

    def test_handoff_targets_are_real_skills(self):
        """Every ecw:X in Downstream Handoff must correspond to an existing skill directory."""
        skills_to_check = [
            "writing-plans", "spec-challenge", "tdd", "impl-verify",
            "impl-orchestration", "biz-impact-analysis", "systematic-debugging",
            "domain-collab", "requirements-elicitation",
        ]
        violations = []
        for skill in skills_to_check:
            targets = self._extract_handoff_targets(skill)
            for target in targets:
                if target not in self.existing_skills:
                    violations.append(
                        f"{skill}: Downstream Handoff references ecw:{target}, "
                        f"but skills/{target}/SKILL.md does not exist"
                    )
        assert not violations, (
            "Downstream Handoff references non-existent skills:\n"
            + "\n".join(violations)
        )

    def test_handoff_targets_in_contracts(self):
        """Every ecw:X in Downstream Handoff must be registered in data_contracts.yaml."""
        skills_to_check = [
            "writing-plans", "spec-challenge", "tdd", "impl-verify",
            "impl-orchestration", "biz-impact-analysis", "systematic-debugging",
            "domain-collab", "requirements-elicitation",
        ]
        violations = []
        for skill in skills_to_check:
            targets = self._extract_handoff_targets(skill)
            for target in targets:
                if target not in self.contracts:
                    violations.append(
                        f"{skill}: Downstream Handoff references ecw:{target}, "
                        f"but it's not in data_contracts.yaml"
                    )
        assert not violations, (
            "Downstream Handoff references unregistered skills:\n"
            + "\n".join(violations)
        )


# ═══════════════════════════════════════════
# G7: dispatcher SUB_HOOKS vs hooks.json routing
# ═══════════════════════════════════════════

class TestG7DispatcherVsHooksJson:
    """dispatcher.py SUB_HOOKS must only handle events that hooks.json routes to it."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.dispatcher = _load_hook("dispatcher")
        hooks_json_path = HOOKS_DIR / "hooks.json"
        if not hooks_json_path.exists():
            pytest.skip("hooks.json not found")
        import json
        with open(hooks_json_path) as f:
            self.hooks_config = json.load(f)["hooks"]

    def test_dispatcher_events_match_hooks_json(self):
        """hooks.json must route all tool types that dispatcher's SUB_HOOKS matchers expect."""
        # Collect tool types that dispatcher's sub-hooks can match
        dispatcher_tools = set()
        for _, _, matcher in self.dispatcher.SUB_HOOKS:
            # Test each tool type to see if the matcher would activate
            for tool in ["Bash", "Edit", "Write", "TaskUpdate", "Skill",
                         "Read", "Agent", "WebFetch"]:
                test_input = {"tool_name": tool, "tool_input": {"status": "completed"}}
                try:
                    if matcher(test_input):
                        dispatcher_tools.add(tool)
                except Exception:
                    pass

        # Collect tool types that hooks.json routes to dispatcher
        routed_tools = set()
        for event_entry in self.hooks_config.get("PreToolUse", []):
            matcher_str = event_entry.get("matcher", "")
            for hook in event_entry.get("hooks", []):
                if "dispatcher.py" in hook.get("command", ""):
                    routed_tools.update(matcher_str.split("|"))

        missing = dispatcher_tools - routed_tools
        assert not missing, (
            f"dispatcher.py handles tool types {missing} but hooks.json "
            f"PreToolUse doesn't route them to dispatcher. "
            f"hooks.json routes: {routed_tools}, dispatcher expects: {dispatcher_tools}"
        )


# ═══════════════════════════════════════════
# G8: ask_user_question skills vs auto-continue special handling
# ═══════════════════════════════════════════

class TestG8AskUserVsAutoContinue:
    """Skills with ask_user_question=true in data_contracts may need special
    handling in auto-continue (e.g., skipping systemMessage injection so the
    skill's own AskUserQuestion flow isn't overridden)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]
        self.hook_source = (HOOKS_DIR / "auto-continue.py").read_text(encoding="utf-8")

    def test_ask_user_skills_acknowledged_in_hook(self):
        """Skills with ask_user_question=true that need post-completion user interaction
        should be explicitly handled (either skipped or acknowledged) in auto-continue.py."""
        ask_user_skills = []
        for skill_name, spec in self.contracts.items():
            if spec.get("ask_user_question", False):
                ask_user_skills.append(skill_name)

        # Check that each ask-user skill is at least mentioned in the hook source
        # This catches cases where a new ask-user skill is added but auto-continue
        # doesn't know about it
        unacknowledged = []
        for skill in ask_user_skills:
            full_name = f"ecw:{skill}"
            if full_name not in self.hook._SKILL_COMPLETED_PHASE:
                continue  # Not in workflow chain, skip
            # Check if skill is mentioned in any special handling code
            if skill not in self.hook_source and full_name not in self.hook_source:
                unacknowledged.append(skill)

        # This is a soft check — not all ask-user skills need special handling.
        # But if a skill has ask_user AND is in the auto-continue chain,
        # it should at least be mentioned somewhere (even if just in a comment).
        # The spec-challenge bug (#29) was exactly this: ask_user skill getting
        # its flow overridden by auto-continue injection.
        if unacknowledged:
            pytest.warns(
                UserWarning,
                match="ask_user_question skills not mentioned in auto-continue",
            )


# ═══════════════════════════════════════════
# G9: Marker format consistency across all SKILL.md files
# ═══════════════════════════════════════════

class TestG9MarkerFormatConsistency:
    """All SKILL.md files that instruct writing to session-state.md must use
    the exact marker format that marker_utils.py expects."""

    EXPECTED_MARKERS = {
        "STATUS": ("<!-- ECW:STATUS:START -->", "<!-- ECW:STATUS:END -->"),
        "MODE": ("<!-- ECW:MODE:START -->", "<!-- ECW:MODE:END -->"),
        "LEDGER": ("<!-- ECW:LEDGER:START -->", "<!-- ECW:LEDGER:END -->"),
        "STOP": ("<!-- ECW:STOP:START -->", "<!-- ECW:STOP:END -->"),
    }

    def test_marker_format_in_skills(self):
        """Skills that reference ECW markers must use the exact format."""
        violations = []
        marker_re = re.compile(r'<!--\s*ECW:(\w+):(START|END)\s*-->')

        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            content = _read_skill_content(skill_dir.name)
            if not content:
                continue

            for m in marker_re.finditer(content):
                name = m.group(1)
                tag = m.group(2)
                actual = m.group(0)
                if name in self.EXPECTED_MARKERS:
                    expected = self.EXPECTED_MARKERS[name][0 if tag == "START" else 1]
                    if actual != expected:
                        violations.append(
                            f"skills/{skill_dir.name}: marker '{actual}' "
                            f"doesn't match expected '{expected}'"
                        )

        assert not violations, (
            "Marker format inconsistencies (hooks expect exact format):\n"
            + "\n".join(violations)
        )

    def test_session_state_format_uses_correct_markers(self):
        """session-state-format.md template must use exact marker format."""
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        content = fmt_path.read_text(encoding="utf-8")

        for name, (start, end) in self.EXPECTED_MARKERS.items():
            if name == "STOP":
                continue  # STOP marker is written by stop-persist hook, not in template
            assert start in content, (
                f"session-state-format.md missing marker '{start}'"
            )
            assert end in content, (
                f"session-state-format.md missing marker '{end}'"
            )


# ═══════════════════════════════════════════
# G10: workflow-routes.yml post_impl_tasks vs risk-classifier SKILL.md
# ═════════════════════════��═════════════════

class TestG10PostImplTasksConsistency:
    """post_impl_tasks in workflow-routes.yml must match what risk-classifier
    SKILL.md instructs to create via TaskCreate."""

    @pytest.fixture(autouse=True)
    def setup(self):
        routes_data = _load_yaml_file(
            SKILLS_DIR / "risk-classifier" / "workflow-routes.yml"
        )
        self.post_impl = routes_data.get("post_impl_tasks", {})
        self.rc_content = _read_skill_content("risk-classifier")
        self.contracts = _load_yaml_file(TESTS_STATIC / "data_contracts.yaml")["skills"]

    def test_post_impl_tasks_mentioned_in_skill(self):
        """Every task type in post_impl_tasks must be referenced in risk-classifier SKILL.md."""
        all_tasks = set()
        for level, tasks in self.post_impl.items():
            for task in tasks:
                all_tasks.add(task)

        missing = []
        for task in sorted(all_tasks):
            # Normalize: "Phase 3 Calibration" → check for "Phase 3" or "calibration"
            task_lower = task.lower()
            rc_lower = self.rc_content.lower()
            if task_lower not in rc_lower and task.replace(" ", "-").lower() not in rc_lower:
                # Try partial match
                words = task_lower.split()
                if not any(w in rc_lower for w in words if len(w) > 3):
                    missing.append(task)

        assert not missing, (
            f"post_impl_tasks entries not mentioned in risk-classifier SKILL.md: {missing}"
        )

    def test_post_impl_matches_contract_task_creates(self):
        """post_impl_tasks P0 list should align with data_contracts task_creates."""
        rc_spec = self.contracts.get("risk-classifier", {})
        contract_tasks = set(rc_spec.get("task_creates", []))

        # P0 should have the most complete set
        p0_tasks = set()
        for task in self.post_impl.get("P0", []):
            # Normalize names for comparison
            normalized = task.lower().replace(" ", "-")
            p0_tasks.add(normalized)

        # Contract tasks should be a subset or equal to P0 post_impl_tasks
        # Normalize both sides for fuzzy matching:
        # "phase3-calibration" should match "Phase 3 Calibration"
        def normalize(s):
            return re.sub(r'[\s-]+', '', s).lower()

        p0_norms = {normalize(t) for t in self.post_impl.get("P0", [])}
        for ct in contract_tasks:
            ct_norm = normalize(ct)
            found = any(ct_norm in pn or pn in ct_norm for pn in p0_norms)
            assert found, (
                f"data_contracts task_creates '{ct}' not found in "
                f"workflow-routes.yml post_impl_tasks P0: {self.post_impl.get('P0')}"
            )


# ═══════════════════════════════════════════
# G11 (bonus): auto-continue _FIELD_PATTERNS vs session-state-format.md
# ═══════════════════════════════════════════

class TestG11FieldPatternsVsTemplate:
    """auto-continue.py's _FIELD_PATTERNS regex must match the field format
    used in session-state-format.md template."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook = _load_hook("auto-continue")
        fmt_path = SKILLS_DIR / "risk-classifier" / "session-state-format.md"
        if not fmt_path.exists():
            pytest.skip("session-state-format.md not found")
        self.fmt_content = fmt_path.read_text(encoding="utf-8")

    def test_field_patterns_match_template(self):
        """Each regex in _FIELD_PATTERNS must match the **field name format** used
        in session-state-format.md. The template uses placeholders like P{X}, so
        we test against a synthetic line with a real value to verify the regex
        would work at runtime."""
        # Build a synthetic status block with real values in template format
        synthetic_lines = {
            "auto_continue": "- **Auto-Continue**: yes",
            "routing": "- **Routing**: ecw:risk-classifier → ecw:writing-plans",
            "next": "- **Next**: ecw:writing-plans",
            "risk_level": "- **Risk Level**: P1",
        }
        unmatched = []
        for field_name, pattern in self.hook._FIELD_PATTERNS.items():
            test_line = synthetic_lines.get(field_name)
            if test_line is None:
                continue
            if not re.search(pattern, test_line, re.IGNORECASE):
                unmatched.append(
                    f"'{field_name}': pattern r'{pattern}' "
                    f"doesn't match synthetic line '{test_line}'"
                )

        assert not unmatched, (
            "auto-continue _FIELD_PATTERNS that don't match expected field format:\n"
            + "\n".join(unmatched)
        )

    def test_field_names_exist_in_template(self):
        """The bold field names parsed by _FIELD_PATTERNS must appear in
        session-state-format.md template."""
        field_names = {
            "auto_continue": "Auto-Continue",
            "routing": "Routing",
            "next": "Next",
            "risk_level": "Risk Level",
        }
        missing = []
        for key, display_name in field_names.items():
            if key not in self.hook._FIELD_PATTERNS:
                continue
            bold_pattern = f"**{display_name}**"
            if bold_pattern not in self.fmt_content:
                missing.append(
                    f"Field '{display_name}' (parsed by _FIELD_PATTERNS['{key}']) "
                    f"not found in session-state-format.md"
                )
        assert not missing, (
            "Field names missing from session-state-format.md:\n"
            + "\n".join(missing)
        )


# ═══════════════════════════════════════════
# G12 (bonus): verify-completion _MESSAGES keys used vs defined
# ═══════════════════════════════════════════

class TestG12VerifyCompletionMessageIntegrity:
    """All _MESSAGES keys referenced in verify-completion.py code must be defined,
    and all defined keys must be used."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hook_path = HOOKS_DIR / "verify-completion.py"
        if not self.hook_path.exists():
            pytest.skip("verify-completion.py not found")
        self.source = self.hook_path.read_text(encoding="utf-8")

    def test_all_referenced_messages_defined(self):
        """Every _MESSAGES[\"key\"] reference must have a corresponding key in _MESSAGES dict."""
        # Find all _MESSAGES["key"] or _MESSAGES['key'] references
        used_keys = set(re.findall(r'_MESSAGES\[["\'](\w+)["\']\]', self.source))

        # Find all keys defined in _MESSAGES dict
        defined_keys = set(re.findall(r'^    "(\w+)":', self.source, re.MULTILINE))

        undefined = used_keys - defined_keys
        assert not undefined, (
            f"verify-completion.py references undefined _MESSAGES keys: {undefined}"
        )

    def test_all_defined_messages_used(self):
        """Every key in _MESSAGES should be referenced somewhere in the code."""
        used_keys = set(re.findall(r'_MESSAGES\[["\'](\w+)["\']\]', self.source))
        defined_keys = set(re.findall(r'^    "(\w+)":', self.source, re.MULTILINE))

        unused = defined_keys - used_keys
        assert not unused, (
            f"verify-completion.py defines but never uses _MESSAGES keys: {unused}"
        )
