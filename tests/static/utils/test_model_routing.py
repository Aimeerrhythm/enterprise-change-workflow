"""Tests for dynamic model routing infrastructure.

Validates:
1. ecw.yml template has models section with correct structure
2. All dispatching SKILL.md files reference ecw.yml model config
3. session-start.py injects non-default model config
"""
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = ROOT / "templates"
SKILLS_DIR = ROOT / "skills"
HOOKS_DIR = ROOT / "hooks"

VALID_MODELS = {"opus", "sonnet", "haiku"}
EXPECTED_TIERS = {"analysis", "planning", "implementation", "verification", "mechanical"}

DISPATCHING_SKILLS = [
    "domain-collab",
    "writing-plans",
    "spec-challenge",
    "biz-impact-analysis",
    "risk-classifier",
    "requirements-elicitation",
    "impl-verify",
    "impl-orchestration",
    "tdd",
]


def _load_ecw_yml():
    return yaml.safe_load((TEMPLATES_DIR / "ecw.yml").read_text(encoding="utf-8"))


def _read_skill(name: str) -> str:
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


class TestEcwYmlModelsSection:
    """ecw.yml template must define a models section with valid structure."""

    def test_ecw_yml_has_models_section(self):
        cfg = _load_ecw_yml()
        assert "models" in cfg, "ecw.yml missing 'models' section"

    def test_models_has_defaults(self):
        cfg = _load_ecw_yml()
        defaults = cfg["models"]["defaults"]
        assert isinstance(defaults, dict)
        for tier in EXPECTED_TIERS:
            assert tier in defaults, f"models.defaults missing tier '{tier}'"

    def test_defaults_values_are_valid(self):
        cfg = _load_ecw_yml()
        defaults = cfg["models"]["defaults"]
        for tier, model in defaults.items():
            assert model in VALID_MODELS, (
                f"models.defaults.{tier} = '{model}' not in {VALID_MODELS}"
            )

    def test_models_has_overrides(self):
        cfg = _load_ecw_yml()
        overrides = cfg["models"]["overrides"]
        assert isinstance(overrides, dict), "models.overrides must be a dict"


class TestSkillModelReferences:
    """Dispatching SKILL.md files must reference model config."""

    # Skills that use models.defaults.* dot-notation references
    STRICT_MODEL_SKILLS = [
        "domain-collab",
        "writing-plans",
        "biz-impact-analysis",
        "risk-classifier",
        "impl-verify",
        "tdd",
    ]

    # Skills that delegate model selection to prompt files or use inline model strings
    DELEGATED_MODEL_SKILLS = {
        "spec-challenge": r"review-prompt-template\.md|model selection|opus",
        "requirements-elicitation": r"sonnet|model",
        "impl-orchestration": r"ecw\.yml.*models|models.*config|model:",
    }

    @pytest.mark.parametrize("skill", STRICT_MODEL_SKILLS)
    def test_skill_references_ecw_yml_models(self, skill):
        content = _read_skill(skill)
        assert re.search(
            r"models\.defaults|configurable via ecw\.yml", content
        ), f"{skill}/SKILL.md: missing reference to ecw.yml model config"

    @pytest.mark.parametrize("skill,pattern", DELEGATED_MODEL_SKILLS.items())
    def test_delegated_skill_references_model(self, skill, pattern):
        content = _read_skill(skill)
        assert re.search(pattern, content, re.IGNORECASE), (
            f"{skill}/SKILL.md: missing model reference (pattern: {pattern})"
        )

    def test_impl_orchestration_respects_ecw_yml_models(self):
        content = _read_skill("impl-orchestration")
        assert re.search(r"ecw\.yml.*models|models.*config", content), (
            "impl-orchestration/SKILL.md: must reference ecw.yml models config"
        )
        # Must have multiple model tiers referenced (sonnet, haiku, opus)
        model_refs = sum(1 for m in ["sonnet", "haiku", "opus"] if m in content.lower())
        assert model_refs >= 2, (
            "impl-orchestration/SKILL.md: must reference at least 2 model tiers"
        )


class TestSessionStartModelsInjection:
    """session-start.py must inject non-default model config into context."""

    @pytest.fixture
    def session_start(self):
        spec = importlib.util.spec_from_file_location(
            "session_start", HOOKS_DIR / "session-start.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_non_default_models_injected(self, session_start, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        (ecw_dir / "ecw.yml").write_text(
            "project:\n  name: test\n  language: java\n"
            "models:\n  defaults:\n    analysis: sonnet\n    planning: opus\n"
            "    implementation: sonnet\n    verification: sonnet\n    mechanical: haiku\n"
            "  overrides: {}\n"
        )
        info = session_start._get_project_info(str(tmp_path))
        assert "model_config" in info, (
            "Non-default model config should be injected"
        )

    def test_default_models_not_injected(self, session_start, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        (ecw_dir / "ecw.yml").write_text(
            "project:\n  name: test\n  language: java\n"
            "models:\n  defaults:\n    analysis: opus\n    planning: opus\n"
            "    implementation: sonnet\n    verification: sonnet\n    mechanical: haiku\n"
            "  overrides: {}\n"
        )
        info = session_start._get_project_info(str(tmp_path))
        assert "model_config" not in info, (
            "Default model config should produce zero noise"
        )
