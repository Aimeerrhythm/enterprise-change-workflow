#!/usr/bin/env python3
from __future__ import annotations

"""ECW Plugin Static Structure Linter

Validates the structural integrity of SKILL.md prompt files, cross-references,
routing tables, artifact paths, and configuration consistency.

Usage:
    python tests/static/lint_skills.py          # Run all checks
    python tests/static/lint_skills.py --quiet   # Only show errors
    python tests/static/lint_skills.py --check NAME  # Run specific check

Exit codes:
    0 = all checks passed
    1 = one or more checks failed
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# ── Constants ──

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"
COMMANDS_DIR = ROOT / "commands"
HOOKS_DIR = ROOT / "hooks"
TEMPLATES_DIR = ROOT / "templates"
CLAUDE_MD = ROOT / "CLAUDE.md"
TESTS_STATIC = Path(__file__).resolve().parent

# Approximate tokens per char ratio for English markdown
CHARS_PER_TOKEN = 4
TOKEN_WARNING_THRESHOLD = 20_000


class LintResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str):
        self.errors.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def load_yaml_file(path: Path) -> dict | list | None:
    if yaml is None:
        print("WARNING: PyYAML not installed, skipping YAML-based checks")
        return None
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    fm_text = content[3:end].strip()
    if yaml is None:
        # Fallback: regex extraction for name field
        name_match = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
        desc_match = re.search(r"^description:", fm_text, re.MULTILINE)
        if name_match and desc_match:
            return {"name": name_match.group(1).strip(), "description": "present"}
        return None
    try:
        return yaml.safe_load(fm_text)
    except Exception:
        return None


def get_skill_dirs() -> list[Path]:
    """Return sorted list of skill directories containing SKILL.md."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def read_skill_content(skill_dir: Path) -> str:
    """Read SKILL.md content from a skill directory."""
    return (skill_dir / "SKILL.md").read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════
# CHECK 1: Frontmatter Validation
# ══════════════════════════════════════════════════════

def check_frontmatter(result: LintResult):
    """Every SKILL.md must have valid frontmatter with name matching directory name."""
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        fm = parse_frontmatter(content)
        dir_name = skill_dir.name

        if fm is None:
            result.error(f"[frontmatter] skills/{dir_name}/SKILL.md: missing or invalid frontmatter")
            continue

        if "name" not in fm:
            result.error(f"[frontmatter] skills/{dir_name}/SKILL.md: frontmatter missing 'name' field")
        elif fm["name"].strip() != dir_name:
            result.error(
                f"[frontmatter] skills/{dir_name}/SKILL.md: "
                f"frontmatter name '{fm['name']}' does not match directory '{dir_name}'"
            )

        if "description" not in fm:
            result.error(f"[frontmatter] skills/{dir_name}/SKILL.md: frontmatter missing 'description' field")


# ══════════════════════════════════════════════════════
# CHECK 2: Skill Cross-Reference Integrity
# ══════════════════════════════════════════════════════

def check_skill_references(result: LintResult):
    """All `ecw:xxx` references in SKILL.md/CLAUDE.md must point to existing skill directories."""
    existing_skills = {d.name for d in get_skill_dirs()}

    # Collect all files to scan
    files_to_scan: list[Path] = []

    # All SKILL.md files
    for skill_dir in get_skill_dirs():
        files_to_scan.append(skill_dir / "SKILL.md")
        # Also scan subprompts
        for md in skill_dir.glob("*.md"):
            if md.name != "SKILL.md":
                files_to_scan.append(md)

    # CLAUDE.md
    if CLAUDE_MD.exists():
        files_to_scan.append(CLAUDE_MD)

    # Agent files
    if AGENTS_DIR.exists():
        for md in AGENTS_DIR.glob("*.md"):
            files_to_scan.append(md)

    # Command files
    if COMMANDS_DIR.exists():
        for md in COMMANDS_DIR.glob("*.md"):
            files_to_scan.append(md)

    ref_pattern = re.compile(r"`?ecw:([\w-]+)`?")

    for fpath in files_to_scan:
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8")
        rel = fpath.relative_to(ROOT)

        for match in ref_pattern.finditer(content):
            skill_name = match.group(1)
            if skill_name not in existing_skills:
                result.error(f"[xref] {rel}: references `ecw:{skill_name}` but skills/{skill_name}/ does not exist")


# ══════════════════════════════════════════════════════
# CHECK 3: Artifact Path Consistency
# ══════════════════════════════════════════════════════

def check_artifact_paths(result: LintResult):
    """Artifact paths in SKILL.md files should match the CLAUDE.md artifact table."""
    if not CLAUDE_MD.exists():
        result.error("[artifact] CLAUDE.md not found")
        return

    claude_content = CLAUDE_MD.read_text(encoding="utf-8")

    # Extract artifact paths from CLAUDE.md "ECW Artifact Files" table
    # Format: | `.claude/ecw/session-data/{workflow-id}/session-state.md` | ... |
    artifact_pattern = re.compile(r"\|\s*`([^`]+)`\s*\|")
    claude_artifacts = set()
    in_artifact_section = False
    for line in claude_content.split("\n"):
        if "ECW Artifact Files" in line or "auto-generated" in line:
            in_artifact_section = True
            continue
        if in_artifact_section:
            if line.startswith("#"):
                break
            m = artifact_pattern.search(line)
            if m:
                path = m.group(1)
                if path.startswith(".claude/"):
                    claude_artifacts.add(path)

    if not claude_artifacts:
        result.warn("[artifact] Could not extract artifact paths from CLAUDE.md table")
        return

    # Scan all SKILL.md for .claude/ write paths
    write_indicators = re.compile(
        r"(?:write|output|save|append|create|生成|写入|追加)\s.*?`(\.claude/[\w\-/]+\.[\w]+)`"
        r"|`(\.claude/[\w\-/]+\.[\w]+)`\s.*?(?:write|output|save|append|create|生成|写入|追加)",
        re.IGNORECASE
    )

    skill_artifacts = set()
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        for m in write_indicators.finditer(content):
            path = m.group(1) or m.group(2)
            if path:
                skill_artifacts.add(path)

    # Also check simpler pattern: paths mentioned in session-state context
    session_state_pattern = re.compile(r"`(\.claude/ecw/[\w\-]+\.md)`")
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        for m in session_state_pattern.finditer(content):
            skill_artifacts.add(m.group(1))

    # Check: CLAUDE.md artifacts should be referenced somewhere in skills
    for artifact in claude_artifacts:
        found = False
        for skill_dir in get_skill_dirs():
            content = read_skill_content(skill_dir)
            if artifact in content:
                found = True
                break
        if not found:
            result.warn(f"[artifact] CLAUDE.md lists artifact `{artifact}` but no SKILL.md references it")


# ══════════════════════════════════════════════════════
# CHECK 4: Routing Dependency DAG Validation
# ══════════════════════════════════════════════════════

def check_routing_dag(result: LintResult):
    """Build skill reference graph and report statistics. Cycles are expected
    (skills naturally reference each other in documentation), so only report
    as warnings for awareness, not errors."""
    existing_skills = {d.name for d in get_skill_dirs()}
    ref_pattern = re.compile(r"`?ecw:([\w-]+)`?")

    graph: dict[str, set[str]] = {name: set() for name in existing_skills}

    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        src = skill_dir.name
        for m in ref_pattern.finditer(content):
            target = m.group(1)
            if target in existing_skills and target != src:
                graph[src].add(target)

    # Check for orphan skills (no incoming or outgoing references)
    referenced_by_others = set()
    for src, targets in graph.items():
        referenced_by_others.update(targets)

    for skill in existing_skills:
        if not graph[skill] and skill not in referenced_by_others:
            result.warn(f"[dag] Skill '{skill}' has no cross-references (orphan)")
        elif skill not in referenced_by_others and skill != "risk-classifier":
            result.warn(f"[dag] Skill '{skill}' is never referenced by other skills")


# ══════════════════════════════════════════════════════
# CHECK 5: Anchor Keyword Validation
# ══════════════════════════════════════════════════════

def check_anchor_keywords(result: LintResult):
    """Each skill must contain its critical anchor keywords."""
    anchors_file = TESTS_STATIC / "anchor_keywords.yaml"
    anchors = load_yaml_file(anchors_file)
    if anchors is None:
        result.warn("[anchors] anchor_keywords.yaml not found or PyYAML not installed, skipping")
        return

    for skill_name, keywords in anchors.items():
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_md.exists():
            result.error(f"[anchors] skills/{skill_name}/SKILL.md does not exist")
            continue

        content = skill_md.read_text(encoding="utf-8")
        for kw in keywords:
            if kw not in content:
                result.error(
                    f"[anchors] skills/{skill_name}/SKILL.md: "
                    f"missing required anchor keyword '{kw}'"
                )


# ══════════════════════════════════════════════════════
# CHECK 6: session-state.md Field Contract
# ══════════════════════════════════════════════════════

def check_session_state_contract(result: LintResult):
    """Fields written by risk-classifier must be a superset of fields read by downstream skills."""
    rc_path = SKILLS_DIR / "risk-classifier" / "SKILL.md"
    if not rc_path.exists():
        result.error("[session-state] risk-classifier/SKILL.md not found")
        return

    rc_content = rc_path.read_text(encoding="utf-8")

    # Extract field names from the session-state template in risk-classifier
    # Pattern: - **Field Name**: ...
    producer_fields = set()
    template_pattern = re.compile(r"-\s*\*\*(.+?)\*\*:")
    in_template = False
    for line in rc_content.split("\n"):
        if "# ECW Session State" in line:
            in_template = True
            continue
        if in_template:
            if line.startswith("## ") and "Subagent" not in line:
                break
            m = template_pattern.match(line)
            if m:
                producer_fields.add(m.group(1).strip())

    if not producer_fields:
        result.warn("[session-state] Could not extract session-state fields from risk-classifier template")
        return

    # Scan other skills for session-state field references
    consumer_fields: dict[str, set[str]] = defaultdict(set)
    field_ref_pattern = re.compile(r"session-state.*?`?(\w[\w\s]+?)`?\s*field", re.IGNORECASE)
    bold_field_pattern = re.compile(r"\*\*(Risk Level|Domains|Mode|Routing|Current Phase|Implementation Strategy|Post-Implementation Tasks)\*\*")

    for skill_dir in get_skill_dirs():
        if skill_dir.name == "risk-classifier":
            continue
        content = read_skill_content(skill_dir)
        if "session-state" not in content:
            continue

        for m in bold_field_pattern.finditer(content):
            consumer_fields[skill_dir.name].add(m.group(1))

    # Verify producer >= consumer
    all_consumed = set()
    for skill_name, fields in consumer_fields.items():
        all_consumed.update(fields)
        for field in fields:
            if field not in producer_fields:
                result.error(
                    f"[session-state] skills/{skill_name} reads field '{field}' "
                    f"from session-state.md but risk-classifier does not produce it"
                )


# ══════════════════════════════════════════════════════
# CHECK 7: AskUserQuestion Required Presence
# ══════════════════════════════════════════════════════

def check_ask_user_question(result: LintResult):
    """Critical skills must contain AskUserQuestion invocation."""
    required_skills = [
        "risk-classifier",  # Phase 1 confirmation
        "tdd",              # Skip confirmation
    ]

    for skill_name in required_skills:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        if "AskUserQuestion" not in content:
            result.error(
                f"[ask-user] skills/{skill_name}/SKILL.md: "
                f"missing AskUserQuestion (required for user confirmation points)"
            )


# ══════════════════════════════════════════════════════
# CHECK 8: Cross-Skill Rule Consistency
# ══════════════════════════════════════════════════════

def check_cross_skill_consistency(result: LintResult):
    """Verify rules defined in multiple skills are consistent."""
    # Check 1: TDD enforcement levels must match between risk-classifier and tdd
    rc_path = SKILLS_DIR / "risk-classifier" / "SKILL.md"
    tdd_path = SKILLS_DIR / "tdd" / "SKILL.md"

    if rc_path.exists() and tdd_path.exists():
        rc_content = rc_path.read_text(encoding="utf-8")
        tdd_content = tdd_path.read_text(encoding="utf-8")

        # Check that both mention tdd.enabled config
        # (TDD mandatory levels semantic check deferred to Layer 2 behavioral eval)
        if "tdd.enabled" in rc_content and "tdd.enabled" not in tdd_content:
            result.warn(
                "[consistency] risk-classifier references tdd.enabled but tdd/SKILL.md does not"
            )
        if "tdd.enabled" in tdd_content and "tdd.enabled" not in rc_content:
            result.warn(
                "[consistency] tdd/SKILL.md references tdd.enabled but risk-classifier does not"
            )

    # Check 2: Implementation Strategy thresholds should be consistent
    strategy_skills = ["risk-classifier", "writing-plans", "impl-orchestration"]
    threshold_pattern = re.compile(r"Tasks?\s*[≤<>≥]=?\s*(\d+)")
    thresholds_by_skill: dict[str, set[str]] = {}

    for skill_name in strategy_skills:
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        # Only look in Implementation Strategy sections
        if "Implementation Strategy" in content:
            section_start = content.index("Implementation Strategy")
            section = content[section_start:section_start + 2000]
            matches = threshold_pattern.findall(section)
            thresholds_by_skill[skill_name] = set(matches)

    # Compare threshold values across skills
    if len(thresholds_by_skill) >= 2:
        reference_skill = "risk-classifier"
        if reference_skill in thresholds_by_skill:
            ref_thresholds = thresholds_by_skill[reference_skill]
            for skill_name, thresholds in thresholds_by_skill.items():
                if skill_name != reference_skill and thresholds != ref_thresholds:
                    result.warn(
                        f"[consistency] Implementation Strategy thresholds differ: "
                        f"risk-classifier has {ref_thresholds}, {skill_name} has {thresholds}"
                    )


# ══════════════════════════════════════════════════════
# CHECK 9: ecw.yml Config Key References
# ══════════════════════════════════════════════════════

def check_ecw_yml_keys(result: LintResult):
    """Config keys referenced in SKILL.md must exist in templates/ecw.yml."""
    template_yml = TEMPLATES_DIR / "ecw.yml"
    if not template_yml.exists():
        result.error("[ecw-yml] templates/ecw.yml not found")
        return

    template_content = template_yml.read_text(encoding="utf-8")

    # Known config key patterns referenced in skills
    config_refs = re.compile(r"ecw\.yml\s*[`'\"]?([\w.]+)[`'\"]?")

    # Also match: `ecw.yml paths.risk_factors`, `ecw.yml verification.run_tests`, etc.
    config_refs2 = re.compile(r"`(?:ecw\.yml\s+)?(\w+\.\w+(?:\.\w+)?)`")

    # Extract all top-level keys from template
    known_keys = set()
    # Simple extraction: lines starting with word: (not comments, not indented)
    for line in template_content.split("\n"):
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = re.match(r"^(\w+):", line)
        if m:
            known_keys.add(m.group(1))

    # Extract nested keys
    nested_keys = set()
    current_section = None
    for line in template_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        # Top-level key
        m = re.match(r"^(\w+):", line)
        if m and not line.startswith(" "):
            current_section = m.group(1)
            continue
        # Nested key
        if current_section:
            m = re.match(r"^\s+(\w+):", line)
            if m:
                nested_keys.add(f"{current_section}.{m.group(1)}")

    all_valid_keys = known_keys | nested_keys

    # Scan skills for config references
    checked_refs = set()
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        rel_path = f"skills/{skill_dir.name}/SKILL.md"

        for pattern in [config_refs, config_refs2]:
            for m in pattern.finditer(content):
                ref_key = m.group(1)
                # Skip non-ecw.yml references
                if "." not in ref_key:
                    continue
                # Normalize: paths.risk_factors -> check both section and full key
                section = ref_key.split(".")[0]
                if section not in known_keys:
                    continue
                if ref_key not in checked_refs:
                    checked_refs.add(ref_key)
                    # Skip file extensions mistaken for config keys
                    if re.search(r'\.\w{1,4}$', ref_key) and ref_key.split('.')[-1] in (
                        'md', 'py', 'yml', 'yaml', 'json', 'js', 'ts', 'java', 'go'
                    ):
                        continue
                    if ref_key not in all_valid_keys:
                        result.warn(
                            f"[ecw-yml] {rel_path}: references config key '{ref_key}' "
                            f"not found in templates/ecw.yml"
                        )


# ══════════════════════════════════════════════════════
# CHECK 10: Markdown Table Structure
# ══════════════════════════════════════════════════════

def check_markdown_tables(result: LintResult):
    """Verify markdown tables have consistent column counts."""
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        rel_path = f"skills/{skill_dir.name}/SKILL.md"
        lines = content.split("\n")

        table_start = None
        header_cols = None

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped.startswith("|"):
                # End of table
                table_start = None
                header_cols = None
                continue

            if stripped.endswith("|") and stripped.startswith("|"):
                segments = stripped.split("|")
                col_count = len(segments) - 2  # leading and trailing empty

            if table_start is None:
                table_start = i
                header_cols = col_count
            elif "---" in stripped:
                # Separator row
                sep_cols = col_count
                if sep_cols != header_cols and header_cols > 0 and sep_cols > 0:
                    result.warn(
                        f"[table] {rel_path}:{i}: separator row has {sep_cols} columns "
                        f"but header (line {table_start}) has {header_cols} columns"
                    )
            else:
                if col_count != header_cols and header_cols > 0 and col_count > 0:
                    # Allow tolerance for multi-line cells and complex formatting
                    if abs(col_count - header_cols) > 1:
                        result.warn(
                            f"[table] {rel_path}:{i}: data row has {col_count} columns "
                            f"but header has {header_cols} columns (diff > 1)"
                        )


# ══════════════════════════════════════════════════════
# CHECK 11: Agent/Prompt Template References
# ══════════════════════════════════════════════════════

def check_template_references(result: LintResult):
    """Agent and subprompt template files must exist."""
    # Check agent files
    if AGENTS_DIR.exists():
        for md in AGENTS_DIR.glob("*.md"):
            # Agent files should have frontmatter with name
            content = md.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            if fm is None:
                result.error(f"[template] agents/{md.name}: missing frontmatter")
            elif "name" not in fm:
                result.error(f"[template] agents/{md.name}: frontmatter missing 'name' field")

    # Check impl-orchestration agent references
    impl_orch = SKILLS_DIR / "impl-orchestration"
    if impl_orch.exists():
        impl_orch_content = (impl_orch / "SKILL.md").read_text(encoding="utf-8")
        # Extract agent file references from SKILL.md
        agent_refs = re.findall(r"`?(agents/[\w-]+\.md)`?", impl_orch_content)
        for agent_ref in agent_refs:
            agent_path = ROOT / agent_ref
            if not agent_path.exists():
                result.error(
                    f"[template] {agent_ref} does not exist "
                    f"(referenced by impl-orchestration skill)"
                )

    # Check hooks reference
    hooks_json = HOOKS_DIR / "hooks.json"
    if hooks_json.exists():
        try:
            hooks_data = json.loads(hooks_json.read_text(encoding="utf-8"))
            for event_hooks in hooks_data.get("hooks", {}).values():
                for entry in event_hooks:
                    for hook in entry.get("hooks", []):
                        cmd = hook.get("command", "")
                        # Extract Python file path from command
                        py_match = re.search(r'[\w/\\-]+\.py', cmd)
                        if py_match:
                            py_file = py_match.group(0)
                            # Resolve relative to plugin root
                            full_path = ROOT / py_file
                            if not full_path.exists():
                                # Also try with hooks/ prefix
                                if not (HOOKS_DIR / Path(py_file).name).exists():
                                    result.error(f"[template] hooks.json references '{py_file}' but file not found")
        except (json.JSONDecodeError, Exception) as e:
            result.error(f"[template] hooks.json parse error: {e}")


# ══════════════════════════════════════════════════════
# CHECK 12: CLAUDE.md Skill List Consistency
# ══════════════════════════════════════════════════════

def check_claudemd_consistency(result: LintResult):
    """CLAUDE.md skill trigger table must match actual skills/ directory listing."""
    if not CLAUDE_MD.exists():
        result.error("[claude-md] CLAUDE.md not found")
        return

    content = CLAUDE_MD.read_text(encoding="utf-8")
    existing_skills = {d.name for d in get_skill_dirs()}

    # Extract skill names from Skill Trigger Conditions table
    # Format: | ecw:risk-classifier | ... |
    table_skills = set()
    trigger_pattern = re.compile(r"\|\s*ecw:([\w-]+)\s*\|")
    in_trigger_section = False
    for line in content.split("\n"):
        if "Skill Trigger Conditions" in line:
            in_trigger_section = True
            continue
        if in_trigger_section:
            if line.startswith("#") and "Skill Trigger" not in line:
                break
            m = trigger_pattern.search(line)
            if m:
                table_skills.add(m.group(1))

    if not table_skills:
        result.warn("[claude-md] Could not extract skill names from Skill Trigger Conditions table")
        return

    # Skills in directory but not in CLAUDE.md
    for skill in existing_skills - table_skills:
        result.error(f"[claude-md] Skill '{skill}' exists in skills/ but not in CLAUDE.md trigger table")

    # Skills in CLAUDE.md but not in directory
    for skill in table_skills - existing_skills:
        result.error(f"[claude-md] CLAUDE.md trigger table lists '{skill}' but skills/{skill}/ does not exist")


# ══════════════════════════════════════════════════════
# CHECK 13: Prompt Token Statistics
# ══════════════════════════════════════════════════════

def check_token_stats(result: LintResult):
    """Report token estimates for each SKILL.md and warn if over threshold."""
    stats = []
    for skill_dir in get_skill_dirs():
        content = read_skill_content(skill_dir)
        char_count = len(content)
        token_estimate = char_count // CHARS_PER_TOKEN
        stats.append((skill_dir.name, char_count, token_estimate))

        if token_estimate > TOKEN_WARNING_THRESHOLD:
            result.warn(
                f"[tokens] skills/{skill_dir.name}/SKILL.md: "
                f"~{token_estimate:,} tokens (>{TOKEN_WARNING_THRESHOLD:,} threshold) — "
                f"may reduce LLM adherence"
            )

    return stats


# ══════════════════════════════════════════════════════
# CHECK 14: Routing Matrix Validation
# ══════════════════════════════════════════════════════

def check_routing_matrix(result: LintResult):
    """Verify risk-classifier routing tables match golden routing matrix."""
    matrix_file = TESTS_STATIC / "routing_matrix.yaml"
    matrix = load_yaml_file(matrix_file)
    if matrix is None:
        result.warn("[routing] routing_matrix.yaml not found or PyYAML not installed, skipping")
        return

    rc_path = SKILLS_DIR / "risk-classifier" / "SKILL.md"
    if not rc_path.exists():
        result.error("[routing] risk-classifier/SKILL.md not found")
        return

    rc_content = rc_path.read_text(encoding="utf-8")

    for entry in matrix:
        level = entry.get("level", "")
        mode = entry.get("mode", "")
        change_type = entry.get("type", "")
        must_include = entry.get("must_include", [])
        must_exclude = entry.get("must_exclude", [])

        # Find the relevant routing table section
        if change_type == "requirement":
            if mode == "single-domain":
                section_marker = "Requirement Changes — Single Domain"
            elif mode == "cross-domain":
                section_marker = "Requirement Changes — Cross-Domain"
            else:
                continue
        elif change_type == "bug":
            section_marker = "Bug Fix Changes"
        elif change_type == "fast-track":
            section_marker = "Fast Track Routing Table"
        else:
            continue

        # Find the section
        section_start = rc_content.find(section_marker)
        if section_start == -1:
            # Try alternate markers
            alt_markers = {
                "Requirement Changes — Single Domain": "Single Domain",
                "Requirement Changes — Cross-Domain": "Cross-Domain",
                "Bug Fix Changes": "Bug Fix",
                "Fast Track Routing Table": "Fast Track",
            }
            alt = alt_markers.get(section_marker)
            if alt:
                section_start = rc_content.find(alt)
            if section_start == -1:
                result.error(f"[routing] risk-classifier missing section for '{section_marker}'")
                continue

        # Extract a focused section — stop at next ### heading
        section_end = rc_content.find("\n###", section_start + len(section_marker))
        if section_end == -1:
            section_end = section_start + 3000
        section = rc_content[section_start:min(section_end, section_start + 3000)]

        # For requirement types, find the specific risk level row
        if change_type == "requirement" and level != "any":
            # Look for the level in a table row: | P0 (Critical) | → `ecw:xxx` → ... |
            level_pattern = re.compile(
                rf"\|\s*{re.escape(level)}\s*\([^)]*\)\s*\|(.+?)(?:\n|$)"
            )
            level_match = level_pattern.search(section)
            if level_match:
                row_content = level_match.group(1)
            else:
                result.error(
                    f"[routing] risk-classifier: {section_marker} section missing "
                    f"row for {level}"
                )
                continue
        else:
            # For bug/fast-track, use the whole section
            row_content = section

        # Check must_include
        for skill in must_include:
            if skill not in row_content:
                result.error(
                    f"[routing] risk-classifier {change_type}/{level}/{mode}: "
                    f"routing must include '{skill}' but not found in row"
                )

        # Check must_exclude — only flag when skill appears in a routing chain context
        # (→ ecw:skill or → `ecw:skill`), not in narrative text like "skip ecw:X"
        for skill in must_exclude:
            # Look for skill in routing arrow context: → `ecw:skill` or → ecw:skill
            routing_pattern = re.compile(
                rf"→\s*`?ecw:{re.escape(skill)}`?"
                rf"|`ecw:{re.escape(skill)}`\s*→"
            )
            if change_type == "requirement":
                # For requirement routing tables, a simpler check works:
                # the skill must appear in the specific table row
                if f"ecw:{skill}" in row_content:
                    result.error(
                        f"[routing] risk-classifier {change_type}/{level}/{mode}: "
                        f"routing must NOT include '{skill}' but found in row"
                    )
            else:
                # For bug/fast-track sections, only match in routing table rows (| ... |)
                for line in row_content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("|") and routing_pattern.search(stripped):
                        result.error(
                            f"[routing] risk-classifier {change_type}/{level}/{mode}: "
                            f"routing must NOT include '{skill}' but found in routing table"
                        )
                        break


# ══════════════════════════════════════════════════════
# CHECK 15: Hook shared module enforcement (DC-1, PC-6)
# ══════════════════════════════════════════════════════

FORBIDDEN_DEFINITIONS = {
    "_find_session_state": "marker_utils.find_session_state",
    "find_session_state": "marker_utils.find_session_state",
    "_read_ecw_config": "ecw_config.read_ecw_config",
}
SHARED_MODULES = {"marker_utils.py", "ecw_config.py"}


def check_hook_shared_modules(result: LintResult):
    """Hook files must not re-implement functions that exist in shared modules."""
    for py_file in sorted(HOOKS_DIR.glob("*.py")):
        if py_file.name in SHARED_MODULES or py_file.name.startswith("test_"):
            continue
        content = py_file.read_text(encoding="utf-8")
        for func_name, shared_location in FORBIDDEN_DEFINITIONS.items():
            if re.search(rf"^def\s+{re.escape(func_name)}\s*\(", content, re.MULTILINE):
                result.error(
                    f"[shared-module] hooks/{py_file.name}: defines '{func_name}' locally — "
                    f"must use {shared_location} instead"
                )


# ══════════════════════════════════════════════════════
# CHECK 16: Subagent safety four elements (PC-3)
# ══════════════════════════════════════════════════════

SUBAGENT_REQUIRED_KEYWORDS = {
    "timeout": ["timeout", "Timeout", "超时"],
    "budget": ["budget", "Budget", "cap", "上限", "最大"],
    "stall": ["stall", "Stall", "卡住", "无进展", "not decrease"],
    "escalation": ["escalat", "Escalat", "升级", "通知用户", "AskUserQuestion"],
}


def check_subagent_safety_controls(result: LintResult):
    """Skills dispatching subagents must define timeout, budget, stall detection, escalation."""
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        content = skill_md.read_text(encoding="utf-8")
        dispatches_agents = bool(re.search(
            r"(?:dispatch|Dispatch)\s+(?:one\s+)?(?:Agent|subagent|implementer|verifier)"
            r"|subagent_type\s*[:=]"
            r"|Subagent\s+(?:Dispatch|Ledger|dispatch)"
            r"|并行.*(?:分发|调度).*(?:Agent|子代理)",
            content
        ))
        if not dispatches_agents:
            continue
        for control_name, keywords in SUBAGENT_REQUIRED_KEYWORDS.items():
            if not any(kw in content for kw in keywords):
                result.warn(
                    f"[subagent-safety] skills/{skill_dir.name}/SKILL.md: "
                    f"dispatches subagents but missing '{control_name}' control"
                )


# ══════════════════════════════════════════════════════
# CHECK 17: Eval coverage report (PC-2)
# ══════════════════════════════════════════════════════

EVAL_DIR = ROOT / "tests" / "eval"


def check_eval_coverage(result: LintResult):
    """Report skills without behavioral eval coverage (warning only)."""
    skills_with_eval = set()
    if EVAL_DIR.exists():
        for d in EVAL_DIR.iterdir():
            if d.is_dir() and (d / "promptfooconfig.yaml").exists():
                skills_with_eval.add(d.name)
        if (EVAL_DIR / "scenarios").exists():
            skills_with_eval.add("risk-classifier")

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        if skill_dir.name not in skills_with_eval:
            result.warn(
                f"[eval-coverage] skills/{skill_dir.name}: no behavioral eval — "
                f"Anthropic recommends eval as prerequisite for prompt engineering"
            )


# ══════════════════════════════════════════════════════
# CHECK 18: Mode-switch consistency with session-state-format.md
# ══════════════════════════════════════════════════════

MODE_SWITCH_GOLDEN = {
    "analysis": ["risk-classifier", "requirements-elicitation", "domain-collab"],
    "planning": ["writing-plans", "spec-challenge"],
    "implementation": ["impl-orchestration", "tdd", "systematic-debugging"],
    "verification": ["impl-verify", "biz-impact-analysis"],
}


def check_mode_switch_consistency(result: LintResult):
    """Skills listed in session-state-format.md mode table must have Mode switch instruction."""
    for mode, skills in MODE_SWITCH_GOLDEN.items():
        for skill_name in skills:
            skill_md = SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_md.exists():
                result.error(f"[mode-switch] skills/{skill_name}/SKILL.md not found")
                continue
            content = skill_md.read_text(encoding="utf-8")
            if "Mode switch" not in content:
                result.error(
                    f"[mode-switch] skills/{skill_name}/SKILL.md: "
                    f"missing 'Mode switch' instruction (expected mode: {mode})"
                )
                continue
            idx = content.index("Mode switch")
            nearby = content[idx:idx + 200]
            if mode not in nearby.lower():
                result.error(
                    f"[mode-switch] skills/{skill_name}/SKILL.md: "
                    f"'Mode switch' found but expected mode '{mode}' not in nearby text"
                )


# ══════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════

ALL_CHECKS = {
    "frontmatter": check_frontmatter,
    "skill-refs": check_skill_references,
    "artifact-paths": check_artifact_paths,
    "routing-dag": check_routing_dag,
    "anchor-keywords": check_anchor_keywords,
    "session-state": check_session_state_contract,
    "ask-user": check_ask_user_question,
    "consistency": check_cross_skill_consistency,
    "ecw-yml": check_ecw_yml_keys,
    "tables": check_markdown_tables,
    "templates": check_template_references,
    "claude-md": check_claudemd_consistency,
    "tokens": check_token_stats,
    "routing-matrix": check_routing_matrix,
    "shared-modules": check_hook_shared_modules,
    "subagent-safety": check_subagent_safety_controls,
    "eval-coverage": check_eval_coverage,
    "mode-switch": check_mode_switch_consistency,
}


def main():
    parser = argparse.ArgumentParser(description="ECW Plugin Static Structure Linter")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only show errors, suppress warnings")
    parser.add_argument("--check", "-c", help="Run specific check only", choices=ALL_CHECKS.keys())
    args = parser.parse_args()

    result = LintResult()
    token_stats = None

    checks_to_run = {args.check: ALL_CHECKS[args.check]} if args.check else ALL_CHECKS

    for name, check_fn in checks_to_run.items():
        try:
            ret = check_fn(result)
            if name == "tokens" and ret is not None:
                token_stats = ret
        except Exception as e:
            result.error(f"[{name}] Check crashed: {e}")

    # Output
    if result.errors:
        print(f"\n{'='*60}")
        print(f"  ERRORS: {len(result.errors)}")
        print(f"{'='*60}\n")
        for err in result.errors:
            print(f"  ERROR  {err}")

    if result.warnings and not args.quiet:
        print(f"\n{'='*60}")
        print(f"  WARNINGS: {len(result.warnings)}")
        print(f"{'='*60}\n")
        for warn in result.warnings:
            print(f"  WARN   {warn}")

    if token_stats and not args.quiet:
        print(f"\n{'='*60}")
        print(f"  TOKEN STATISTICS")
        print(f"{'='*60}\n")
        for name, chars, tokens in sorted(token_stats, key=lambda x: -x[2]):
            marker = " ⚠️" if tokens > TOKEN_WARNING_THRESHOLD else ""
            print(f"  {name:30s}  ~{tokens:>6,} tokens  ({chars:>7,} chars){marker}")
        total_tokens = sum(t for _, _, t in token_stats)
        print(f"  {'─'*50}")
        print(f"  {'TOTAL':30s}  ~{total_tokens:>6,} tokens")

    print()
    if result.ok:
        print(f"  ✓ All checks passed ({len(result.warnings)} warnings)")
    else:
        print(f"  ✗ {len(result.errors)} errors, {len(result.warnings)} warnings")

    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
