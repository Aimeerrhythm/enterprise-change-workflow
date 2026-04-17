"""Unit tests for hooks/dispatcher.py

Covers dispatcher routing, profile resolution, sub-hook loading,
and output format for both block and continue paths.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def dispatcher():
    """Import dispatcher.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "dispatcher",
        HOOKS_DIR / "dispatcher.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Profile Resolution
# ══════════════════════════════════════════════════════

class TestGetProfile:
    """Tests for risk level → profile mapping."""

    def test_env_p0_returns_strict(self, dispatcher):
        """ECW_RISK_LEVEL=P0 → strict profile."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "P0"}):
            assert dispatcher.get_profile("/fake") == "strict"

    def test_env_p1_returns_standard(self, dispatcher):
        """ECW_RISK_LEVEL=P1 → standard profile."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "P1"}):
            assert dispatcher.get_profile("/fake") == "standard"

    def test_env_p2_returns_standard(self, dispatcher):
        """ECW_RISK_LEVEL=P2 → standard profile."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "P2"}):
            assert dispatcher.get_profile("/fake") == "standard"

    def test_env_p3_returns_minimal(self, dispatcher):
        """ECW_RISK_LEVEL=P3 → minimal profile."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "P3"}):
            assert dispatcher.get_profile("/fake") == "minimal"

    def test_env_lowercase_works(self, dispatcher):
        """ECW_RISK_LEVEL=p0 (lowercase) → strict profile."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "p0"}):
            assert dispatcher.get_profile("/fake") == "strict"

    def test_session_state_risk_level(self, dispatcher, tmp_path):
        """Risk level read from session-state.md when env not set."""
        state_dir = tmp_path / ".claude" / "ecw" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "session-state.md").write_text("risk_level: P0\nstatus: active\n")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_RISK_LEVEL", None)
            assert dispatcher.get_profile(str(tmp_path)) == "strict"

    def test_default_profile_when_nothing_set(self, dispatcher, tmp_path):
        """Default profile is 'standard' when no env or session-state."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_RISK_LEVEL", None)
            assert dispatcher.get_profile(str(tmp_path)) == "standard"

    def test_empty_cwd_returns_default(self, dispatcher):
        """Empty cwd → default profile."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ECW_RISK_LEVEL", None)
            assert dispatcher.get_profile("") == "standard"

    def test_invalid_env_value_falls_through(self, dispatcher, tmp_path):
        """Invalid ECW_RISK_LEVEL value → check session-state → default."""
        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "INVALID"}):
            assert dispatcher.get_profile(str(tmp_path)) == "standard"


# ══════════════════════════════════════════════════════
# Matcher Functions
# ══════════════════════════════════════════════════════

class TestMatchers:
    """Tests for sub-hook matcher functions."""

    def test_is_task_complete_matches(self, dispatcher):
        inp = {"tool_name": "TaskUpdate", "tool_input": {"status": "completed"}}
        assert dispatcher._is_task_complete(inp) is True

    def test_is_task_complete_rejects_non_completed(self, dispatcher):
        inp = {"tool_name": "TaskUpdate", "tool_input": {"status": "in_progress"}}
        assert dispatcher._is_task_complete(inp) is False

    def test_is_task_complete_rejects_other_tool(self, dispatcher):
        inp = {"tool_name": "Read", "tool_input": {}}
        assert dispatcher._is_task_complete(inp) is False

    def test_is_edit_or_write_matches_edit(self, dispatcher):
        assert dispatcher._is_edit_or_write({"tool_name": "Edit"}) is True

    def test_is_edit_or_write_matches_write(self, dispatcher):
        assert dispatcher._is_edit_or_write({"tool_name": "Write"}) is True

    def test_is_edit_or_write_rejects_read(self, dispatcher):
        assert dispatcher._is_edit_or_write({"tool_name": "Read"}) is False

    def test_is_bash_matches(self, dispatcher):
        assert dispatcher._is_bash({"tool_name": "Bash"}) is True

    def test_is_bash_rejects_other(self, dispatcher):
        assert dispatcher._is_bash({"tool_name": "Edit"}) is False


# ══════════════════════════════════════════════════════
# Module Loading
# ══════════════════════════════════════════════════════

class TestLoadSubhook:
    """Tests for _load_subhook module loading."""

    def test_load_verify_completion(self, dispatcher):
        """verify-completion.py should load and have a check() function."""
        mod = dispatcher._load_subhook("verify-completion")
        assert mod is not None
        assert hasattr(mod, "check"), "verify-completion must expose check()"

    def test_load_nonexistent_returns_none(self, dispatcher):
        """Non-existent module file returns None."""
        mod = dispatcher._load_subhook("nonexistent-hook")
        assert mod is None


# ══════════════════════════════════════════════════════
# Dispatcher Routing
# ══════════════════════════════════════════════════════

class TestDispatcherRouting:
    """Tests for the main dispatcher routing logic."""

    def test_non_matching_tool_passes_through(self, dispatcher):
        """Read tool → no sub-hook matches → continue."""
        input_data = {"tool_name": "Read", "tool_input": {}, "cwd": "/fake"}
        with patch("json.load", return_value=input_data):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc:
                    dispatcher.main()
                assert exc.value.code == 0
                output = json.loads(mock_print.call_args[0][0])
                assert output.get("result") == "continue"

    def test_task_complete_routes_to_verify(self, dispatcher, tmp_path):
        """TaskUpdate(completed) → routes to verify-completion sub-hook."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        # Mock verify-completion.check to return continue
        mock_mod = MagicMock()
        mock_mod.check.return_value = ("continue", "test message")

        with patch("json.load", return_value=input_data):
            with patch.object(dispatcher, "_load_subhook", return_value=mock_mod):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        dispatcher.main()
                    assert exc.value.code == 0
                    output = json.loads(mock_print.call_args[0][0])
                    assert "test message" in output["systemMessage"]

    def test_block_result_produces_deny(self, dispatcher, tmp_path):
        """Sub-hook returning block → deny output with exit 2."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        mock_mod = MagicMock()
        mock_mod.check.return_value = ("block", "compilation failed")

        with patch("json.load", return_value=input_data):
            with patch.object(dispatcher, "_load_subhook", return_value=mock_mod):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        dispatcher.main()
                    assert exc.value.code == 2
                    output = json.loads(mock_print.call_args[0][0])
                    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
                    assert "compilation failed" in output["systemMessage"]

    def test_subhook_exception_does_not_block(self, dispatcher, tmp_path):
        """Sub-hook raising exception → logged to stderr, not blocking."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        mock_mod = MagicMock()
        mock_mod.check.side_effect = RuntimeError("boom")

        with patch("json.load", return_value=input_data):
            with patch.object(dispatcher, "_load_subhook", return_value=mock_mod):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        dispatcher.main()
                    assert exc.value.code == 0

    def test_profile_filters_subhooks(self, dispatcher, tmp_path):
        """P3 profile (minimal) should still run verify-completion (it's in minimal)."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        mock_mod = MagicMock()
        mock_mod.check.return_value = ("continue", "passed")

        with patch.dict(os.environ, {"ECW_RISK_LEVEL": "P3"}):
            with patch("json.load", return_value=input_data):
                with patch.object(dispatcher, "_load_subhook", return_value=mock_mod):
                    with patch("builtins.print") as mock_print:
                        with pytest.raises(SystemExit) as exc:
                            dispatcher.main()
                        assert exc.value.code == 0
                        # verify-completion should have been called even at minimal
                        mock_mod.check.assert_called_once()

    def test_empty_message_gives_continue_result(self, dispatcher, tmp_path):
        """Sub-hook returning empty message → result: continue."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        mock_mod = MagicMock()
        mock_mod.check.return_value = ("continue", "")

        with patch("json.load", return_value=input_data):
            with patch.object(dispatcher, "_load_subhook", return_value=mock_mod):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        dispatcher.main()
                    assert exc.value.code == 0
                    output = json.loads(mock_print.call_args[0][0])
                    assert output.get("result") == "continue"


# ══════════════════════════════════════════════════════
# Exception Safety
# ══════════════════════════════════════════════════════

class TestDispatcherExceptionSafety:
    """Tests for the top-level exception handler."""

    def test_stdin_parse_error_does_not_block(self, dispatcher):
        """Invalid JSON stdin → error message, exit 0."""
        with patch("json.load", side_effect=Exception("bad json")):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc:
                    # Simulate the if __name__ == "__main__" block
                    try:
                        dispatcher.main()
                    except Exception as e:
                        print(json.dumps({"systemMessage": f"ECW dispatcher error: {e}"}))
                        sys.exit(0)
                assert exc.value.code == 0


# ══════════════════════════════════════════════════════
# SUB_HOOKS Registry Integrity
# ══════════════════════════════════════════════════════

class TestSubHooksRegistry:
    """Verify the SUB_HOOKS registry is well-formed."""

    def test_all_entries_have_three_elements(self, dispatcher):
        """Each SUB_HOOKS entry must be (filename, profiles, matcher)."""
        for entry in dispatcher.SUB_HOOKS:
            assert len(entry) == 3, f"SUB_HOOKS entry must have 3 elements: {entry}"

    def test_all_profiles_are_valid(self, dispatcher):
        """All declared profiles must be in {minimal, standard, strict}."""
        valid = {"minimal", "standard", "strict"}
        for filename, profiles, _ in dispatcher.SUB_HOOKS:
            for p in profiles:
                assert p in valid, f"Invalid profile '{p}' in sub-hook '{filename}'"

    def test_all_matchers_are_callable(self, dispatcher):
        """All matcher functions must be callable."""
        for filename, _, matcher in dispatcher.SUB_HOOKS:
            assert callable(matcher), f"Matcher for '{filename}' is not callable"

    def test_verify_completion_is_registered(self, dispatcher):
        """verify-completion must be in the SUB_HOOKS registry."""
        filenames = [entry[0] for entry in dispatcher.SUB_HOOKS]
        assert "verify-completion" in filenames
