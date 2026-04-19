"""Unit tests for hooks/gateguard-fact-force.py

Validates:
1. First edit blocks with investigation message
2. Second edit passes (file already recorded)
3. Exempt files are not blocked
4. State file management
"""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def gateguard():
    """Import gateguard-fact-force.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "gateguard_fact_force",
        HOOKS_DIR / "gateguard-fact-force.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFirstEditBlocks:
    def test_first_edit_source_file_blocks(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
            "cwd": str(tmp_path),
        }
        action, msg = gateguard.check(input_data)
        assert action == "block"
        assert "Gateguard" in msg
        assert "main.py" in msg

    def test_first_edit_java_file_blocks(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "src" / "Service.java")},
            "cwd": str(tmp_path),
        }
        action, msg = gateguard.check(input_data)
        assert action == "block"
        assert "Service.java" in msg


class TestSecondEditPasses:
    def test_recorded_file_passes(self, gateguard, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "investigated-files.txt").write_text("src/main.py\n")

        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "main.py")},
            "cwd": str(tmp_path),
        }
        action, msg = gateguard.check(input_data)
        assert action == "continue"
        assert msg == ""

    def test_block_then_pass(self, gateguard, tmp_path):
        """First call blocks and records; second call passes."""
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "app.ts")},
            "cwd": str(tmp_path),
        }
        action1, _ = gateguard.check(input_data)
        assert action1 == "block"

        action2, msg2 = gateguard.check(input_data)
        assert action2 == "continue"
        assert msg2 == ""


class TestExemptions:
    @pytest.mark.parametrize("filename", [
        "README.md", "config.json", "settings.yml", "data.yaml",
        "notes.txt", "pyproject.toml", "app.cfg", "setup.ini",
        "package-lock.lock",
    ])
    def test_non_source_files_exempt(self, gateguard, tmp_path, filename):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / filename)},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(input_data)
        assert action == "continue"

    def test_claude_dir_exempt(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / ".claude" / "ecw" / "state.py")},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(input_data)
        assert action == "continue"

    def test_disabled_via_env(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "src" / "core.py")},
            "cwd": str(tmp_path),
        }
        with patch.dict(os.environ, {"ECW_GATEGUARD_DISABLED": "1"}):
            action, _ = gateguard.check(input_data)
        assert action == "continue"


class TestEdgeCases:
    def test_empty_path_continues(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": ""},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(input_data)
        assert action == "continue"

    def test_empty_cwd_continues(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/some/file.py"},
            "cwd": "",
        }
        action, _ = gateguard.check(input_data)
        assert action == "continue"

    def test_no_tool_input_continues(self, gateguard, tmp_path):
        input_data = {"tool_name": "Edit", "cwd": str(tmp_path)}
        action, _ = gateguard.check(input_data)
        assert action == "continue"


class TestStateFileManagement:
    def test_block_creates_state_file(self, gateguard, tmp_path):
        input_data = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "module.py")},
            "cwd": str(tmp_path),
        }
        gateguard.check(input_data)
        state_file = tmp_path / ".claude" / "ecw" / "state" / "investigated-files.txt"
        assert state_file.exists()
        assert "module.py" in state_file.read_text()

    def test_multiple_blocks_append(self, gateguard, tmp_path):
        for name in ["a.py", "b.py", "c.py"]:
            input_data = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(tmp_path / "src" / name)},
                "cwd": str(tmp_path),
            }
            gateguard.check(input_data)

        state_file = tmp_path / ".claude" / "ecw" / "state" / "investigated-files.txt"
        content = state_file.read_text()
        assert "src/a.py" in content
        assert "src/b.py" in content
        assert "src/c.py" in content


class TestScriptExists:
    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "gateguard-fact-force.py").exists()
