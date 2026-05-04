"""Unit tests for hooks/gateguard-fact-force.py

Validates:
1. Whitelist mode: only guarded extensions are blocked
2. No config or empty gateguard_extensions = no blocking
3. Second edit passes (file already recorded)
4. Exempt paths and .claude/ directory
5. State file management
"""
import importlib.util
import os
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"

JAVA_CONFIG = {"hooks": {"gateguard_extensions": [".java"]}}
MULTI_CONFIG = {"hooks": {"gateguard_extensions": [".java", ".xml", "yml"]}}


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


def _make_input(tmp_path, filename):
    filepath = tmp_path / "src" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.touch()
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(filepath)},
        "cwd": str(tmp_path),
    }


class TestWhitelistMode:
    def test_guarded_java_blocks(self, gateguard, tmp_path):
        action, msg = gateguard.check(_make_input(tmp_path, "Service.java"), JAVA_CONFIG)
        assert action == "block"
        assert "Gateguard" in msg

    def test_unguarded_py_passes(self, gateguard, tmp_path):
        action, _ = gateguard.check(_make_input(tmp_path, "main.py"), JAVA_CONFIG)
        assert action == "continue"

    def test_unguarded_ts_passes(self, gateguard, tmp_path):
        action, _ = gateguard.check(_make_input(tmp_path, "app.ts"), JAVA_CONFIG)
        assert action == "continue"

    def test_multi_extensions(self, gateguard, tmp_path):
        action1, _ = gateguard.check(_make_input(tmp_path, "Service.java"), MULTI_CONFIG)
        assert action1 == "block"
        action2, _ = gateguard.check(_make_input(tmp_path, "beans.xml"), MULTI_CONFIG)
        assert action2 == "block"
        action3, _ = gateguard.check(_make_input(tmp_path, "config.yml"), MULTI_CONFIG)
        assert action3 == "block"

    def test_extension_without_dot(self, gateguard, tmp_path):
        config = {"hooks": {"gateguard_extensions": ["java"]}}
        action, _ = gateguard.check(_make_input(tmp_path, "Dao.java"), config)
        assert action == "block"

    def test_case_insensitive(self, gateguard, tmp_path):
        config = {"hooks": {"gateguard_extensions": [".JAVA"]}}
        action, _ = gateguard.check(_make_input(tmp_path, "Dao.java"), config)
        assert action == "block"


class TestNoConfigNoBlocking:
    def test_no_config_passes(self, gateguard, tmp_path):
        action, _ = gateguard.check(_make_input(tmp_path, "Service.java"))
        assert action == "continue"

    def test_empty_extensions_passes(self, gateguard, tmp_path):
        config = {"hooks": {"gateguard_extensions": []}}
        action, _ = gateguard.check(_make_input(tmp_path, "Service.java"), config)
        assert action == "continue"

    def test_none_config_passes(self, gateguard, tmp_path):
        action, _ = gateguard.check(_make_input(tmp_path, "Service.java"), None)
        assert action == "continue"


class TestSecondEditPasses:
    def test_recorded_file_passes(self, gateguard, tmp_path):
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "investigated-files.txt").write_text("src/Service.java\n")

        action, _ = gateguard.check(_make_input(tmp_path, "Service.java"), JAVA_CONFIG)
        assert action == "continue"

    def test_block_then_pass(self, gateguard, tmp_path):
        inp = _make_input(tmp_path, "Service.java")
        action1, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action1 == "block"

        action2, msg2 = gateguard.check(inp, JAVA_CONFIG)
        assert action2 == "continue"
        assert msg2 == ""


class TestExemptions:
    def test_claude_dir_exempt(self, gateguard, tmp_path):
        filepath = tmp_path / ".claude" / "ecw" / "Hook.java"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.touch()
        inp = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(filepath)},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_exempt_paths(self, gateguard, tmp_path):
        config = {
            "hooks": {
                "gateguard_extensions": [".java"],
                "exempt_paths": ["src/generated/"],
            },
        }
        filepath = tmp_path / "src" / "generated" / "Model.java"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.touch()
        inp = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(filepath)},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(inp, config)
        assert action == "continue"


class TestEdgeCases:
    def test_empty_path_continues(self, gateguard, tmp_path):
        inp = {"tool_name": "Edit", "tool_input": {"file_path": ""}, "cwd": str(tmp_path)}
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_empty_cwd_continues(self, gateguard, tmp_path):
        inp = {"tool_name": "Edit", "tool_input": {"file_path": "/some/file.java"}, "cwd": ""}
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_nonexistent_file_continues(self, gateguard, tmp_path):
        inp = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(tmp_path / "nonexistent" / "File.java")},
            "cwd": str(tmp_path),
        }
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"


class TestStateFileManagement:
    def test_block_creates_state_file(self, gateguard, tmp_path):
        gateguard.check(_make_input(tmp_path, "Module.java"), JAVA_CONFIG)
        state_file = tmp_path / ".claude" / "ecw" / "state" / "investigated-files.txt"
        assert state_file.exists()
        assert "Module.java" in state_file.read_text()

    def test_multiple_blocks_append(self, gateguard, tmp_path):
        for name in ["A.java", "B.java", "C.java"]:
            gateguard.check(_make_input(tmp_path, name), JAVA_CONFIG)

        state_file = tmp_path / ".claude" / "ecw" / "state" / "investigated-files.txt"
        content = state_file.read_text()
        assert "src/A.java" in content
        assert "src/B.java" in content
        assert "src/C.java" in content


class TestScriptExists:
    def test_hook_script_exists(self):
        assert (HOOKS_DIR / "gateguard-fact-force.py").exists()


# ---------------------------------------------------------------------------
# Bash write interception (Issue #35)
# ---------------------------------------------------------------------------

def _make_bash_input(tmp_path, command):
    """Build a Bash tool_input dict with the given command."""
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(tmp_path),
    }


def _touch(tmp_path, rel):
    """Create a file at tmp_path/rel and return its path string."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return str(p)


class TestBashWriteInterception:
    def test_redirect_gt_blocks_guarded_file(self, gateguard, tmp_path):
        """echo content > Foo.java should be blocked (file not yet investigated)."""
        _touch(tmp_path, "src/Foo.java")
        inp = _make_bash_input(tmp_path, f"echo 'public class Foo {{}}' > {tmp_path}/src/Foo.java")
        action, msg = gateguard.check(inp, JAVA_CONFIG)
        assert action == "block"
        assert "Gateguard" in msg

    def test_redirect_append_blocks_guarded_file(self, gateguard, tmp_path):
        """cat >> Bar.java should be blocked."""
        _touch(tmp_path, "src/Bar.java")
        inp = _make_bash_input(tmp_path, f"cat >> {tmp_path}/src/Bar.java << 'EOF'\npublic class Bar {{}}\nEOF")
        action, msg = gateguard.check(inp, JAVA_CONFIG)
        assert action == "block"
        assert "Gateguard" in msg

    def test_tee_blocks_guarded_file(self, gateguard, tmp_path):
        """echo content | tee Baz.java should be blocked."""
        _touch(tmp_path, "src/Baz.java")
        inp = _make_bash_input(tmp_path, f"echo 'class Baz {{}}' | tee {tmp_path}/src/Baz.java")
        action, msg = gateguard.check(inp, JAVA_CONFIG)
        assert action == "block"
        assert "Gateguard" in msg

    def test_bash_write_already_investigated_passes(self, gateguard, tmp_path):
        """Bash write to an already-investigated file should pass through."""
        _touch(tmp_path, "src/Known.java")
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "investigated-files.txt").write_text("src/Known.java\n")

        inp = _make_bash_input(tmp_path, f"echo 'x' > {tmp_path}/src/Known.java")
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_bash_write_unguarded_extension_passes(self, gateguard, tmp_path):
        """Bash write to a .py file (not in guarded_exts) should pass through."""
        _touch(tmp_path, "src/main.py")
        inp = _make_bash_input(tmp_path, f"echo 'pass' > {tmp_path}/src/main.py")
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_block_message_contains_bypass_warning(self, gateguard, tmp_path):
        """Block message must warn against Bash bypass (layer-1 text)."""
        _, msg = gateguard.check(_make_input(tmp_path, "Service.java"), JAVA_CONFIG)
        assert "Do not bypass this check by using Bash" in msg

    def test_bash_no_write_pattern_passes(self, gateguard, tmp_path):
        """A Bash command without write patterns should always pass."""
        inp = _make_bash_input(tmp_path, "grep -r 'Service' src/")
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"

    def test_bash_write_nonexistent_file_passes(self, gateguard, tmp_path):
        """Bash writing to a guarded-extension path that doesn't exist yet passes."""
        inp = _make_bash_input(tmp_path, f"echo 'x' > {tmp_path}/src/NewFile.java")
        action, _ = gateguard.check(inp, JAVA_CONFIG)
        assert action == "continue"
