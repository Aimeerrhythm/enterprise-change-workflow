"""DC-4: Hook exception safety — every Hook's __main__ block must have try/except.

Source: Claude Code Hooks Documentation — exit code semantics;
        Release It! (Nygard, 2018) — The Guardian pattern.

Assumption: All Hooks use the standard `if __name__ == "__main__":` entry pattern.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
EXCLUDED = {"marker_utils.py", "ecw_config.py", "__init__.py", "conftest.py"}

# Sub-hooks are loaded by dispatcher.py and protected by its try/except.
# They don't need their own __main__ block.
SUB_HOOKS = {"bash-preflight.py", "config-protect.py", "gateguard-fact-force.py", "secret-scan.py"}


def get_hook_files():
    return [f for f in sorted(HOOKS_DIR.glob("*.py"))
            if f.name not in EXCLUDED and not f.name.startswith("test_")]


def get_standalone_hook_files():
    return [f for f in get_hook_files() if f.name not in SUB_HOOKS]


class TestHookExceptionSafety:

    @pytest.mark.parametrize("hook_file", get_standalone_hook_files(), ids=lambda f: f.name)
    def test_main_has_try_except(self, hook_file):
        """Hook __main__ block must contain try/except."""
        content = hook_file.read_text(encoding="utf-8")
        tree = ast.parse(content)
        main_block = None
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                if isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
                    main_block = node
                    break
        assert main_block is not None, f"{hook_file.name}: missing __main__ block"
        has_try = any(isinstance(child, ast.Try) for child in ast.walk(main_block))
        assert has_try, f"{hook_file.name}: __main__ missing try/except"

    @pytest.mark.parametrize("hook_file", get_hook_files(), ids=lambda f: f.name)
    def test_no_sys_exit_one(self, hook_file):
        """Hooks must not use sys.exit(1) — use exit(0) for non-blocking or exit(2) for intentional block."""
        content = hook_file.read_text(encoding="utf-8")
        assert "sys.exit(1)" not in content, f"{hook_file.name}: contains sys.exit(1)"
