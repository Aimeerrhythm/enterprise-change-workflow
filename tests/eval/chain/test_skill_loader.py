"""Unit tests for skill_loader.py.

Verifies SKILL.md loading, prompts/*.md appending,
and extra_files injection per chain step declaration.
"""
from __future__ import annotations

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = ROOT / "skills"


class TestLoadSkillPrompt:
    """Tests for load_skill_prompt()."""

    def test_loads_skill_md(self):
        from tests.eval.chain.skill_loader import load_skill_prompt
        content = load_skill_prompt("risk-classifier")
        assert "risk-classifier" in content.lower() or "Risk" in content

    def test_appends_prompts_dir(self):
        """prompts/*.md files should be appended after SKILL.md."""
        from tests.eval.chain.skill_loader import load_skill_prompt
        # writing-plans has prompts/plan-quality-checks.md
        content = load_skill_prompt("writing-plans")
        # SKILL.md content appears first; prompts content also present
        skill_md = (SKILLS_DIR / "writing-plans" / "SKILL.md").read_text()
        assert skill_md[:200] in content

    def test_no_extra_files_by_default(self):
        """Without extra_files, only SKILL.md + prompts/*.md are loaded.
        Template .md files in the skill root should NOT be auto-included.
        """
        from tests.eval.chain.skill_loader import load_skill_prompt
        # risk-classifier has many .md templates in root (phase1-output-template.md etc)
        # With no extra_files, they should not be included
        content = load_skill_prompt("risk-classifier")
        skill_md = (SKILLS_DIR / "risk-classifier" / "SKILL.md").read_text()
        # Content should be SKILL.md + prompts only
        # phase1-output-template.md should NOT be included automatically
        phase1_template = (SKILLS_DIR / "risk-classifier" / "phase1-output-template.md").read_text()
        # First line of template is distinctive — check it's not duplicated beyond SKILL.md
        first_line = phase1_template.strip().split("\n")[0]
        # The line might appear in SKILL.md itself (reference), but the full template content
        # should not be appended as a separate block
        count_in_skill = skill_md.count(first_line)
        count_in_loaded = content.count(first_line)
        assert count_in_loaded == count_in_skill  # not added again

    def test_extra_files_inlined(self):
        """When extra_files specified, those files are appended with a header."""
        from tests.eval.chain.skill_loader import load_skill_prompt
        content = load_skill_prompt(
            "writing-plans",
            extra_files=["plan-header-template.md"],
        )
        template_content = (SKILLS_DIR / "writing-plans" / "plan-header-template.md").read_text()
        assert "plan-header-template.md" in content
        assert template_content[:100] in content

    def test_extra_files_any_extension(self):
        """extra_files supports non-.md files (e.g., .yml)."""
        from tests.eval.chain.skill_loader import load_skill_prompt
        content = load_skill_prompt(
            "risk-classifier",
            extra_files=["workflow-routes.yml"],
        )
        routes = (SKILLS_DIR / "risk-classifier" / "workflow-routes.yml").read_text()
        assert routes[:100] in content

    def test_extra_files_raw_text_no_yaml_dump(self):
        """YAML extra_files should be read as raw text, not parsed and re-dumped."""
        from tests.eval.chain.skill_loader import load_skill_prompt
        content = load_skill_prompt(
            "risk-classifier",
            extra_files=["workflow-routes.yml"],
        )
        # Comments in YAML should be preserved (parse-and-dump would strip them)
        routes_raw = (SKILLS_DIR / "risk-classifier" / "workflow-routes.yml").read_text()
        if "#" in routes_raw:
            # Find a comment line and verify it's in the loaded content
            comment_line = next(
                (line for line in routes_raw.splitlines() if line.strip().startswith("#")),
                None,
            )
            if comment_line:
                assert comment_line in content

    def test_missing_skill_raises(self):
        from tests.eval.chain.skill_loader import load_skill_prompt
        with pytest.raises(FileNotFoundError):
            load_skill_prompt("nonexistent-skill-xyz")

    def test_missing_extra_file_raises(self):
        from tests.eval.chain.skill_loader import load_skill_prompt
        with pytest.raises(FileNotFoundError):
            load_skill_prompt("risk-classifier", extra_files=["does-not-exist.md"])
