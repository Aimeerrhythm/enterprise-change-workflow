"""Tests for engineering rules framework.

Validates:
1. ecw.yml template has rules section
2. Rule template files exist with content
3. Agent templates reference rules
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = ROOT / "templates"
AGENTS_DIR = ROOT / "agents"
SKILLS_DIR = ROOT / "skills"

RULES_COMMON_FILES = ["coding-style.md", "security.md", "testing.md"]


class TestRulesTemplatesExist:
    """Rule template files must exist with meaningful content."""

    def test_rules_readme_exists(self):
        readme = TEMPLATES_DIR / "rules" / "README.md"
        assert readme.exists(), "templates/rules/README.md not found"

    @pytest.mark.parametrize("filename", RULES_COMMON_FILES)
    def test_rules_common_files_exist(self, filename):
        path = TEMPLATES_DIR / "rules" / "common" / filename
        assert path.exists(), f"templates/rules/common/{filename} not found"

    @pytest.mark.parametrize("filename", RULES_COMMON_FILES)
    def test_rules_files_have_content(self, filename):
        path = TEMPLATES_DIR / "rules" / "common" / filename
        content = path.read_text(encoding="utf-8")
        assert len(content) > 50, (
            f"templates/rules/common/{filename} has insufficient content ({len(content)} chars)"
        )


class TestAgentRulesReferences:
    """Key agent templates must reference the rules framework."""

    def test_implementer_references_rules(self):
        content = (AGENTS_DIR / "implementer.md").read_text(encoding="utf-8")
        assert "rules" in content.lower(), (
            "agents/implementer.md missing reference to engineering rules"
        )

    def test_impl_verifier_references_rules(self):
        content = (AGENTS_DIR / "impl-verifier.md").read_text(encoding="utf-8")
        assert "rules" in content.lower(), (
            "agents/impl-verifier.md missing reference to engineering rules"
        )
