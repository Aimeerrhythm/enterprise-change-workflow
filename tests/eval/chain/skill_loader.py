"""Load ECW skill prompts for chain eval.

Mirrors _read_skill() from tests/static/consistency/test_data_contracts.py but adds
an explicit extra_files parameter so each chain step controls what gets inlined.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "skills"


def load_skill_prompt(skill_name: str, extra_files: list[str] | None = None) -> str:
    """Read SKILL.md + prompts/*.md for a given skill, then inline any extra_files.

    Args:
        skill_name: Subdirectory name under skills/ (e.g. 'risk-classifier').
        extra_files: Paths relative to the skill directory to append verbatim
            (e.g. ['plan-header-template.md', 'workflow-routes.yml']).
            All files are read as raw text — YAML files are NOT parsed/re-dumped.

    Raises:
        FileNotFoundError: If SKILL.md or any extra_file doesn't exist.
    """
    skill_dir = SKILLS_DIR / skill_name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md not found: {skill_md}")

    content = skill_md.read_text(encoding="utf-8")

    prompts_dir = skill_dir / "prompts"
    if prompts_dir.is_dir():
        for md in sorted(prompts_dir.glob("*.md")):
            content += "\n\n" + md.read_text(encoding="utf-8")

    for rel_path in extra_files or []:
        path = skill_dir / rel_path
        if not path.exists():
            raise FileNotFoundError(f"extra_file not found: {path}")
        extra_text = path.read_text(encoding="utf-8")
        content += f"\n\n## [Inlined: {rel_path}]\n\n{extra_text}"

    return content
