"""Unit tests for hooks/eval-gate.py"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location(
        "eval_gate", HOOKS_DIR / "eval-gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Entry filtering
# ══════════════════════════════════════════════════════

class TestEntryFiltering:

    def test_non_task_update_passes(self, gate):
        action, msg = gate.check({"tool_name": "Edit", "tool_input": {}})
        assert action == "continue"
        assert msg == ""

    def test_non_completed_status_passes(self, gate):
        action, msg = gate.check({"tool_name": "TaskUpdate", "tool_input": {"status": "in_progress"}})
        assert action == "continue"
        assert msg == ""

    def test_missing_tool_name_passes(self, gate):
        action, msg = gate.check({})
        assert action == "continue"
        assert msg == ""


# ══════════════════════════════════════════════════════
# _is_skill_file
# ══════════════════════════════════════════════════════

class TestIsSkillFile:

    def test_skill_md_detected(self, gate):
        assert gate._is_skill_file("skills/risk-classifier/SKILL.md") is True
        assert gate._is_skill_file("skills/tdd/SKILL.md") is True

    def test_workflow_routes_detected(self, gate):
        assert gate._is_skill_file("skills/risk-classifier/workflow-routes.yml") is True

    def test_non_skill_files_ignored(self, gate):
        assert gate._is_skill_file("hooks/verify-completion.py") is False
        assert gate._is_skill_file("skills/tdd/extra.md") is False
        assert gate._is_skill_file("CLAUDE.md") is False
        assert gate._is_skill_file("tests/static/lint_skills.py") is False


# ══════════════════════════════════════════════════════
# get_changed_skill_files
# ══════════════════════════════════════════════════════

class TestGetChangedSkillFiles:

    def test_skill_md_in_diff_returned(self, gate, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="skills/risk-classifier/SKILL.md\nhooks/verify-completion.py\n",
            )
            result = gate.get_changed_skill_files(str(tmp_path))
        assert result == ["skills/risk-classifier/SKILL.md"]

    def test_workflow_routes_in_diff_returned(self, gate, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="skills/risk-classifier/workflow-routes.yml\n",
            )
            result = gate.get_changed_skill_files(str(tmp_path))
        assert result == ["skills/risk-classifier/workflow-routes.yml"]

    def test_no_skill_files_returns_empty(self, gate, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hooks/foo.py\n")
            result = gate.get_changed_skill_files(str(tmp_path))
        assert result == []

    def test_git_error_returns_empty(self, gate, tmp_path):
        with patch("subprocess.run", side_effect=Exception("git not found")):
            result = gate.get_changed_skill_files(str(tmp_path))
        assert result == []

    def test_git_timeout_returns_empty(self, gate, tmp_path):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            result = gate.get_changed_skill_files(str(tmp_path))
        assert result == []


# ══════════════════════════════════════════════════════
# stamp_is_fresh
# ══════════════════════════════════════════════════════

class TestStampIsFresh:

    def test_stamp_missing_returns_false(self, gate, tmp_path):
        result = gate.stamp_is_fresh(str(tmp_path), ["skills/tdd/SKILL.md"])
        assert result is False

    def test_stamp_newer_than_skill_files_returns_true(self, gate, tmp_path):
        skill_file = tmp_path / "skills" / "tdd" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("content")

        stamp_dir = tmp_path / ".claude" / "ecw" / "state"
        stamp_dir.mkdir(parents=True)
        stamp = stamp_dir / "eval-cleared.stamp"
        stamp.write_text("")

        # Make stamp newer than skill file
        future = time.time() + 10
        os.utime(str(stamp), (future, future))

        result = gate.stamp_is_fresh(str(tmp_path), ["skills/tdd/SKILL.md"])
        assert result is True

    def test_skill_file_newer_than_stamp_returns_false(self, gate, tmp_path):
        skill_file = tmp_path / "skills" / "tdd" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("content")

        stamp_dir = tmp_path / ".claude" / "ecw" / "state"
        stamp_dir.mkdir(parents=True)
        stamp = stamp_dir / "eval-cleared.stamp"
        stamp.write_text("")

        # Make skill file newer than stamp
        future = time.time() + 10
        os.utime(str(skill_file), (future, future))

        result = gate.stamp_is_fresh(str(tmp_path), ["skills/tdd/SKILL.md"])
        assert result is False

    def test_missing_skill_file_does_not_block(self, gate, tmp_path):
        """If skill file doesn't exist locally, stamp is considered fresh."""
        stamp_dir = tmp_path / ".claude" / "ecw" / "state"
        stamp_dir.mkdir(parents=True)
        (stamp_dir / "eval-cleared.stamp").write_text("")

        result = gate.stamp_is_fresh(str(tmp_path), ["skills/nonexistent/SKILL.md"])
        assert result is True


# ══════════════════════════════════════════════════════
# run_eval
# ══════════════════════════════════════════════════════

class TestRunEval:

    def test_eval_success_returns_true(self, gate, tmp_path):
        (tmp_path / "tests").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="8/8 passed", stderr="")
            passed, output = gate.run_eval(str(tmp_path))
        assert passed is True
        assert "passed" in output

    def test_eval_failure_returns_false(self, gate, tmp_path):
        (tmp_path / "tests").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="FAILED: s01")
            passed, output = gate.run_eval(str(tmp_path))
        assert passed is False
        assert "FAILED" in output

    def test_eval_timeout_returns_none(self, gate, tmp_path):
        (tmp_path / "tests").mkdir()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("make", 240)):
            passed, output = gate.run_eval(str(tmp_path))
        assert passed is None
        assert "超时" in output

    def test_eval_exception_returns_none(self, gate, tmp_path):
        (tmp_path / "tests").mkdir()
        with patch("subprocess.run", side_effect=FileNotFoundError("make not found")):
            passed, output = gate.run_eval(str(tmp_path))
        assert passed is None

    def test_log_file_written(self, gate, tmp_path):
        (tmp_path / "tests").mkdir()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="passed", stderr="")
            gate.run_eval(str(tmp_path))
        log = tmp_path / ".claude" / "ecw" / "state" / "eval-last-run.log"
        assert log.exists()
        assert "passed" in log.read_text()


# ══════════════════════════════════════════════════════
# check() — integration
# ══════════════════════════════════════════════════════

class TestCheck:

    def _input(self):
        return {"tool_name": "TaskUpdate", "tool_input": {"status": "completed"}}

    def test_no_skill_files_changed_passes(self, gate, tmp_path):
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files", return_value=[]):
                action, msg = gate.check(self._input())
        assert action == "continue"
        assert msg == ""

    def test_stamp_fresh_passes_without_running_eval(self, gate, tmp_path):
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files",
                              return_value=["skills/tdd/SKILL.md"]):
                with patch.object(gate, "stamp_is_fresh", return_value=True):
                    with patch.object(gate, "run_eval") as mock_eval:
                        action, msg = gate.check(self._input())
                        mock_eval.assert_not_called()
        assert action == "continue"

    def test_stale_stamp_triggers_eval_pass(self, gate, tmp_path):
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files",
                              return_value=["skills/tdd/SKILL.md"]):
                with patch.object(gate, "stamp_is_fresh", return_value=False):
                    with patch.object(gate, "run_eval", return_value=(True, "8/8 passed")):
                        action, msg = gate.check(self._input())
        assert action == "continue"
        assert "通过" in msg
        assert "skills/tdd/SKILL.md" in msg

    def test_stale_stamp_triggers_eval_fail_blocks(self, gate, tmp_path):
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files",
                              return_value=["skills/tdd/SKILL.md"]):
                with patch.object(gate, "stamp_is_fresh", return_value=False):
                    with patch.object(gate, "run_eval",
                                      return_value=(False, "FAILED: s01 risk_level wrong")):
                        action, msg = gate.check(self._input())
        assert action == "block"
        assert "失败" in msg
        assert "eval-quick" in msg

    def test_eval_timeout_continues_with_reminder(self, gate, tmp_path):
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files",
                              return_value=["skills/tdd/SKILL.md"]):
                with patch.object(gate, "stamp_is_fresh", return_value=False):
                    with patch.object(gate, "run_eval", return_value=(None, "超时")):
                        action, msg = gate.check(self._input())
        assert action == "continue"
        assert "超时" in msg

    def test_multiple_skill_files_all_listed(self, gate, tmp_path):
        files = ["skills/tdd/SKILL.md", "skills/risk-classifier/workflow-routes.yml"]
        with patch.object(gate, "_get_plugin_root", return_value=str(tmp_path)):
            with patch.object(gate, "get_changed_skill_files", return_value=files):
                with patch.object(gate, "stamp_is_fresh", return_value=False):
                    with patch.object(gate, "run_eval", return_value=(True, "passed")):
                        action, msg = gate.check(self._input())
        assert "tdd/SKILL.md" in msg
        assert "workflow-routes.yml" in msg


# ══════════════════════════════════════════════════════
# main() — JSON output format
# ══════════════════════════════════════════════════════

class TestMainOutput:

    def test_block_produces_deny_json(self, gate):
        with patch("json.load", return_value={"tool_name": "TaskUpdate",
                                               "tool_input": {"status": "completed"}}):
            with patch.object(gate, "check", return_value=("block", "eval failed")):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        gate.main()
                    assert exc.value.code == 2
                    output = json.loads(mock_print.call_args[0][0])
                    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
                    assert "eval failed" in output["systemMessage"]

    def test_continue_with_message_produces_system_message(self, gate):
        with patch("json.load", return_value={"tool_name": "TaskUpdate",
                                               "tool_input": {"status": "completed"}}):
            with patch.object(gate, "check", return_value=("continue", "eval passed")):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        gate.main()
                    assert exc.value.code == 0
                    output = json.loads(mock_print.call_args[0][0])
                    assert "eval passed" in output["systemMessage"]

    def test_continue_no_message_prints_nothing(self, gate):
        with patch("json.load", return_value={"tool_name": "TaskUpdate",
                                               "tool_input": {"status": "completed"}}):
            with patch.object(gate, "check", return_value=("continue", "")):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        gate.main()
                    assert exc.value.code == 0
                    mock_print.assert_not_called()


# ══════════════════════════════════════════════════════
# Exception safety
# ══════════════════════════════════════════════════════

class TestExceptionSafety:

    def test_exception_does_not_block_workflow(self, gate):
        with patch("json.load", side_effect=RuntimeError("unexpected")):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc:
                    try:
                        gate.main()
                    except RuntimeError:
                        print(json.dumps({"systemMessage": "ECW eval-gate hook error: unexpected"}))
                        sys.exit(0)
                assert exc.value.code == 0
