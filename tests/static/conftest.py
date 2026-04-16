"""Shared pytest fixtures for ECW static tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks directory to path so we can import verify-completion
HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def hook_module():
    """Import verify-completion.py as a module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "verify_completion",
        HOOKS_DIR / "verify-completion.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def make_stdin():
    """Create a factory for mocking stdin with JSON input."""
    def _make(tool_name="TaskUpdate", status="completed", cwd="/fake/project"):
        data = {
            "tool_name": tool_name,
            "tool_input": {"status": status},
            "cwd": cwd,
        }
        return json.dumps(data)
    return _make


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with minimal ECW structure."""
    # Create .claude/ecw/ directory
    ecw_dir = tmp_path / ".claude" / "ecw"
    ecw_dir.mkdir(parents=True)

    # Create minimal ecw.yml
    ecw_yml = ecw_dir / "ecw.yml"
    ecw_yml.write_text(
        "project:\n  name: test\n  language: java\n"
        "verification:\n  run_tests: true\n  test_timeout: 60\n"
        "tdd:\n  enabled: true\n  check_test_files: false\n"
        "paths:\n  knowledge_root: .claude/knowledge/\n"
        "  path_mappings: .claude/ecw/ecw-path-mappings.md\n"
    )

    # Create knowledge directory
    (tmp_path / ".claude" / "knowledge").mkdir(parents=True)

    return tmp_path


@pytest.fixture
def git_mock():
    """Mock subprocess.run for git commands."""
    def _make(modified=None, deleted=None):
        modified = modified or []
        deleted = deleted or []

        def side_effect(cmd, **kwargs):
            result = MagicMock()
            result.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "ACMR" in cmd_str:
                result.stdout = "\n".join(modified) if modified else ""
            elif "--diff-filter=D" in cmd_str:
                result.stdout = "\n".join(deleted) if deleted else ""
            else:
                result.stdout = ""
            result.stderr = ""
            return result

        return side_effect
    return _make
