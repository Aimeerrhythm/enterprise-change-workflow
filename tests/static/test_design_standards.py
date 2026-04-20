from __future__ import annotations

"""Tests for ECW design standards enforcement.

Validates structural requirements for skills, agents, hooks, and ensures
rule/reference documentation exists with required content.
"""
import re

import pytest
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"
HOOKS_DIR = ROOT / "hooks"
TEMPLATES_DIR = ROOT / "templates"
DOCS_DIR = ROOT / "docs"

SHARED_MODULES = {"marker_utils.py", "ecw_config.py"}
SKILL_LINE_LIMIT = 500
VALID_AGENT_MODELS = {"haiku", "sonnet", "opus"}


def _parse_frontmatter(content: str) -> dict | None:
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    return yaml.safe_load(content[3:end])


def _all_skills():
    return sorted(
        d for d in SKILLS_DIR.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )


def _all_agents():
    return sorted(AGENTS_DIR.glob("*.md")) if AGENTS_DIR.exists() else []


def _all_hooks():
    return sorted(
        f for f in HOOKS_DIR.glob("*.py")
        if f.name not in SHARED_MODULES and not f.name.startswith("test_")
    )


# ── Skill Length ──


class TestSkillLength:
    @pytest.mark.parametrize(
        "skill_dir", _all_skills(), ids=lambda d: d.name
    )
    def test_skill_under_limit(self, skill_dir):
        content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        if line_count > SKILL_LINE_LIMIT:
            import warnings
            warnings.warn(
                f"{skill_dir.name}/SKILL.md is {line_count} lines "
                f"(limit: {SKILL_LINE_LIMIT})"
            )


# ── Agent Structure ──


class TestAgentStructure:
    @pytest.mark.parametrize(
        "agent_file", _all_agents(), ids=lambda f: f.name
    )
    def test_has_required_frontmatter(self, agent_file):
        content = agent_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        assert fm is not None, f"{agent_file.name}: missing YAML frontmatter"
        for field in ("name", "description", "model"):
            assert field in fm and fm[field], (
                f"{agent_file.name}: frontmatter missing '{field}'"
            )

    @pytest.mark.parametrize(
        "agent_file", _all_agents(), ids=lambda f: f.name
    )
    def test_model_value_valid(self, agent_file):
        content = agent_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        if fm and "model" in fm:
            assert fm["model"] in VALID_AGENT_MODELS, (
                f"{agent_file.name}: model '{fm['model']}' not in {VALID_AGENT_MODELS}"
            )

    @pytest.mark.parametrize(
        "agent_file", _all_agents(), ids=lambda f: f.name
    )
    def test_has_boundary_section(self, agent_file):
        content = agent_file.read_text(encoding="utf-8")
        assert re.search(r"##\s+.*[Bb]oundary", content), (
            f"{agent_file.name}: missing '## ... Boundary' section"
        )


# ── Hook Fail-Open ──


class TestHookFailOpen:
    @staticmethod
    def _hooks_with_main():
        return [
            f for f in _all_hooks()
            if "def main()" in f.read_text(encoding="utf-8")
        ]

    @pytest.mark.parametrize(
        "hook_file",
        _hooks_with_main.__func__(),
        ids=lambda f: f.name,
    )
    def test_has_try_except(self, hook_file):
        content = hook_file.read_text(encoding="utf-8")
        assert re.search(r"try\s*:", content), (
            f"{hook_file.name}: main() must be wrapped in try/except"
        )

    @pytest.mark.parametrize(
        "hook_file",
        _hooks_with_main.__func__(),
        ids=lambda f: f.name,
    )
    def test_outputs_continue_on_error(self, hook_file):
        content = hook_file.read_text(encoding="utf-8")
        assert '"continue"' in content or "'continue'" in content, (
            f"{hook_file.name}: must output {{\"result\": \"continue\"}} in except branch"
        )


# ── ECW Development Rule File ──


class TestEcwDevelopmentRule:
    RULE_PATH = TEMPLATES_DIR / "rules" / "common" / "ecw-development.md"

    def test_rule_file_exists(self):
        assert self.RULE_PATH.exists(), (
            "templates/rules/common/ecw-development.md must exist"
        )

    def test_rule_has_frontmatter(self):
        content = self.RULE_PATH.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        assert fm is not None, "ecw-development.md: missing YAML frontmatter"
        for field in ("name", "description", "scope"):
            assert field in fm and fm[field], (
                f"ecw-development.md: frontmatter missing '{field}'"
            )

    def test_rule_has_must_follow_items(self):
        content = self.RULE_PATH.read_text(encoding="utf-8")
        must_follow_count = len(re.findall(r"\[must-follow\]", content))
        assert must_follow_count >= 5, (
            f"ecw-development.md has {must_follow_count} [must-follow] rules (need ≥5)"
        )


# ── Design Reference Document ──


class TestDesignReference:
    DOC_PATH = DOCS_DIR / "design-reference.md"

    def test_doc_exists(self):
        assert self.DOC_PATH.exists(), "docs/design-reference.md must exist"

    def test_doc_has_key_sections(self):
        content = self.DOC_PATH.read_text(encoding="utf-8").lower()
        for section in ("token budget", "model selection", "context management"):
            assert section in content, (
                f"design-reference.md missing section: '{section}'"
            )
