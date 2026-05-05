"""Load ECW skill prompts for chain eval.

Mirrors _read_skill() from tests/static/consistency/test_data_contracts.py but adds
an explicit extra_files parameter so each chain step controls what gets inlined.
"""
from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "skills"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def load_skill_prompt(
    skill_name: str,
    extra_files: list[str] | None = None,
    prompt_file: str | None = None,
) -> str:
    """Read skill prompt content, then inline any extra_files.

    By default, loads SKILL.md + prompts/*.md from skills/{skill_name}/.
    When prompt_file is given, loads that single file instead (relative to
    PROJECT_ROOT), skipping SKILL.md and prompts/ auto-glob. This is used
    when a skill's review agent instructions live in agents/ rather than
    skills/ (e.g. spec-challenge uses agents/spec-challenge.md).

    Args:
        skill_name: Subdirectory name under skills/ (e.g. 'risk-classifier').
        extra_files: Paths relative to the skill directory to append verbatim
            (e.g. ['plan-header-template.md', 'workflow-routes.yml']).
            Applied after prompt_file or SKILL.md content.
        prompt_file: Path relative to PROJECT_ROOT to use as the base prompt
            instead of SKILL.md + prompts/*.md (e.g. 'agents/spec-challenge.md').

    Raises:
        FileNotFoundError: If SKILL.md, prompt_file, or any extra_file doesn't exist.
    """
    if prompt_file is not None:
        base_path = PROJECT_ROOT / prompt_file
        if not base_path.exists():
            raise FileNotFoundError(f"prompt_file not found: {base_path}")
        content = base_path.read_text(encoding="utf-8")
    else:
        skill_dir = SKILLS_DIR / skill_name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found: {skill_md}")
        content = skill_md.read_text(encoding="utf-8")
        prompts_dir = skill_dir / "prompts"
        if prompts_dir.is_dir():
            for md in sorted(prompts_dir.glob("*.md")):
                content += "\n\n" + md.read_text(encoding="utf-8")

    skill_dir = SKILLS_DIR / skill_name
    for rel_path in extra_files or []:
        path = skill_dir / rel_path
        if not path.exists():
            raise FileNotFoundError(f"extra_file not found: {path}")
        extra_text = path.read_text(encoding="utf-8")
        content += f"\n\n## [Inlined: {rel_path}]\n\n{extra_text}"

    return content
