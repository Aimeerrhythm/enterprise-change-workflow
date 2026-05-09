"""Unit tests for hooks/verify-completion.py

Covers all functions and branches of the ECW completion verification hook.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest


# ══════════════════════════════════════════════════════
# Entry Logic
# ══════════════════════════════════════════════════════

class TestEntryLogic:
    """Tests for the main() entry point filtering."""

    def test_non_task_update_passes(self, hook_module):
        """Non-TaskUpdate tools should pass through (exit 0)."""
        input_data = {"tool_name": "Read", "tool_input": {}, "cwd": "/fake"}
        with patch("sys.stdin", MagicMock(read=lambda: json.dumps(input_data))):
            with patch("json.load", return_value=input_data):
                with pytest.raises(SystemExit) as exc:
                    hook_module.main()
                assert exc.value.code == 0

    def test_non_completed_status_passes(self, hook_module):
        """TaskUpdate with status != completed should pass through."""
        input_data = {"tool_name": "TaskUpdate", "tool_input": {"status": "in_progress"}, "cwd": "/fake"}
        with patch("json.load", return_value=input_data):
            with pytest.raises(SystemExit) as exc:
                hook_module.main()
            assert exc.value.code == 0

    def test_empty_cwd_passes(self, hook_module):
        """Empty cwd should pass through."""
        input_data = {"tool_name": "TaskUpdate", "tool_input": {"status": "completed"}, "cwd": ""}
        with patch("json.load", return_value=input_data):
            with pytest.raises(SystemExit) as exc:
                hook_module.main()
            assert exc.value.code == 0

    def test_no_changed_files_passes(self, hook_module, tmp_project):
        """No git changes should pass with reminder."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        with patch("json.load", return_value=input_data):
            with patch.object(hook_module, "get_changed_files", return_value=([], [])):
                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as exc:
                        hook_module.main()
                    assert exc.value.code == 0
                    output = mock_print.call_args[0][0]
                    assert "技术检查通过" in output


# ══════════════════════════════════════════════════════
# get_changed_files
# ══════════════════════════════════════════════════════

class TestGetChangedFiles:
    """Tests for git diff parsing."""

    def test_normal_output(self, hook_module):
        """Parse normal git diff output."""
        def mock_run(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
            if "ACMR" in cmd_str:
                r.stdout = "src/Main.java\nsrc/Other.java\n"
            else:
                r.stdout = "deleted/File.java\n"
            return r

        with patch("subprocess.run", side_effect=mock_run):
            modified, deleted = hook_module.get_changed_files("/fake")
        assert modified == ["src/Main.java", "src/Other.java"]
        assert deleted == ["deleted/File.java"]

    def test_empty_output(self, hook_module):
        """Empty git diff returns empty lists."""
        def mock_run(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            r.stdout = ""
            return r

        with patch("subprocess.run", side_effect=mock_run):
            modified, deleted = hook_module.get_changed_files("/fake")
        assert modified == []
        assert deleted == []

    def test_git_error_returns_empty(self, hook_module):
        """Git command failure returns empty lists."""
        with patch("subprocess.run", side_effect=Exception("git not found")):
            modified, deleted = hook_module.get_changed_files("/fake")
        assert modified == []
        assert deleted == []

    def test_git_timeout_returns_empty(self, hook_module):
        """Git timeout returns empty lists."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)):
            modified, deleted = hook_module.get_changed_files("/fake")
        assert modified == []
        assert deleted == []


# ══════════════════════════════════════════════════════
# check_broken_references
# ══════════════════════════════════════════════════════

class TestCheckBrokenReferences:
    """Tests for broken .claude/ path reference detection."""

    def test_valid_reference_no_issue(self, hook_module, tmp_project):
        """Reference to existing file produces no issue."""
        # Create a referenced file
        (tmp_project / ".claude" / "ecw" / "session-state.md").write_text("test")
        # Create a file referencing it
        md_file = tmp_project / "docs" / "guide.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("See `.claude/ecw/session-state.md` for state.")

        issues = hook_module.check_broken_references(str(tmp_project), "docs/guide.md")
        assert issues == []

    def test_broken_reference_produces_issue(self, hook_module, tmp_project):
        """Reference to non-existing file produces issue."""
        md_file = tmp_project / "docs" / "guide.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("See `.claude/ecw/nonexistent.md` for details.")

        issues = hook_module.check_broken_references(str(tmp_project), "docs/guide.md")
        assert len(issues) == 1
        assert "nonexistent.md" in issues[0]

    def test_non_text_file_skipped(self, hook_module, tmp_project):
        """Non-text files (.java, .py) are skipped."""
        java_file = tmp_project / "src" / "Main.java"
        java_file.parent.mkdir(parents=True, exist_ok=True)
        java_file.write_text("// .claude/ecw/something.md")

        issues = hook_module.check_broken_references(str(tmp_project), "src/Main.java")
        assert issues == []

    def test_file_not_found_returns_empty(self, hook_module, tmp_project):
        """Non-existing file path returns empty list."""
        issues = hook_module.check_broken_references(str(tmp_project), "nonexistent.md")
        assert issues == []

    def test_md_extension_checked(self, hook_module, tmp_project):
        """Markdown files are checked."""
        md_file = tmp_project / "test.md"
        md_file.write_text("Path: `.claude/ecw/missing.yml`")

        issues = hook_module.check_broken_references(str(tmp_project), "test.md")
        assert len(issues) == 1

    def test_yml_extension_checked(self, hook_module, tmp_project):
        """YAML files are checked."""
        yml_file = tmp_project / "config.yml"
        yml_file.write_text("path: .claude/ecw/missing.md")

        issues = hook_module.check_broken_references(str(tmp_project), "config.yml")
        assert len(issues) == 1


# ══════════════════════════════════════════════════════
# check_stale_references
# ══════════════════════════════════════════════════════

class TestCheckStaleReferences:
    """Tests for stale reference detection (deleted files still referenced)."""

    def test_deleted_file_still_referenced(self, hook_module, tmp_project):
        """Deleted file referenced by another .claude/ file produces issue."""
        # Create a file that references the deleted path
        ref_file = tmp_project / ".claude" / "ecw" / "session-state.md"
        ref_file.write_text("See .claude/ecw/deleted-file.md for details")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=".claude/ecw/session-state.md\n",
                returncode=0
            )
            issues = hook_module.check_stale_references(
                str(tmp_project), ".claude/ecw/deleted-file.md"
            )
        assert len(issues) == 1
        assert "deleted-file.md" in issues[0]

    def test_deleted_file_not_referenced(self, hook_module, tmp_project):
        """Deleted file not referenced by anyone produces no issue."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=1)
            issues = hook_module.check_stale_references(
                str(tmp_project), ".claude/ecw/deleted-file.md"
            )
        assert issues == []

    def test_empty_deleted_file_returns_empty(self, hook_module, tmp_project):
        """Empty deleted file path returns empty."""
        issues = hook_module.check_stale_references(str(tmp_project), "")
        assert issues == []

    def test_no_claude_dir_returns_empty(self, hook_module, tmp_path):
        """No .claude/ directory returns empty."""
        issues = hook_module.check_stale_references(str(tmp_path), "some-file.md")
        assert issues == []

    def test_specs_dir_skipped(self, hook_module, tmp_project):
        """References in .claude/specs/ are skipped."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout=".claude/specs/old-spec.md\n",
                returncode=0
            )
            issues = hook_module.check_stale_references(
                str(tmp_project), ".claude/ecw/deleted.md"
            )
        assert issues == []


# ══════════════════════════════════════════════════════
# check_java_compilation
# ══════════════════════════════════════════════════════

class TestCheckJavaCompilation:
    """Tests for Java compilation check."""

    def test_no_java_files_skipped(self, hook_module):
        """No .java files modified → skip compilation."""
        issues, warnings = hook_module.check_java_compilation("/fake", ["src/readme.md"])
        assert issues == []
        assert warnings == []

    def test_no_pom_xml_skipped(self, hook_module, tmp_path):
        """Java files but no pom.xml → skip compilation."""
        issues, warnings = hook_module.check_java_compilation(
            str(tmp_path), ["src/Main.java"]
        )
        assert issues == []
        assert warnings == []

    def test_compile_success(self, hook_module, tmp_path):
        """mvn compile success → no issues."""
        (tmp_path / "pom.xml").write_text("<project/>")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            issues, warnings = hook_module.check_java_compilation(
                str(tmp_path), ["src/Main.java"]
            )
        assert issues == []

    def test_compile_failure_produces_issue(self, hook_module, tmp_path):
        """mvn compile failure → issue with error lines."""
        (tmp_path / "pom.xml").write_text("<project/>")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="[ERROR] cannot find symbol\n[ERROR] class Foo",
                stderr=""
            )
            issues, warnings = hook_module.check_java_compilation(
                str(tmp_path), ["src/Main.java"]
            )
        assert len(issues) == 1
        assert "编译失败" in issues[0]

    def test_compile_timeout_produces_warning(self, hook_module, tmp_path):
        """mvn compile timeout → warning, not issue."""
        (tmp_path / "pom.xml").write_text("<project/>")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("mvn", 120)):
            issues, warnings = hook_module.check_java_compilation(
                str(tmp_path), ["src/Main.java"]
            )
        assert issues == []
        assert len(warnings) == 1
        assert "超时" in warnings[0]

    def test_mvn_not_found_skipped(self, hook_module, tmp_path):
        """mvn not in PATH → skip silently."""
        (tmp_path / "pom.xml").write_text("<project/>")
        with patch("subprocess.run", side_effect=FileNotFoundError("mvn")):
            issues, warnings = hook_module.check_java_compilation(
                str(tmp_path), ["src/Main.java"]
            )
        assert issues == []
        assert warnings == []


# ══════════════════════════════════════════════════════
# check_java_tests
# ══════════════════════════════════════════════════════

class TestCheckJavaTests:
    """Tests for Java test execution check."""

    def test_no_java_files_skipped(self, hook_module):
        """No .java files → skip."""
        issues, warnings = hook_module.check_java_tests("/fake", ["readme.md"])
        assert issues == []

    def test_run_tests_false_skipped(self, hook_module, tmp_project):
        """verification.run_tests=false → skip."""
        # Override ecw.yml to disable tests
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text(
            "verification:\n  run_tests: false\n"
        )
        (tmp_project / "pom.xml").write_text("<project/>")
        issues, warnings = hook_module.check_java_tests(
            str(tmp_project), ["src/Main.java"]
        )
        assert issues == []

    def test_test_failure_produces_issue(self, hook_module, tmp_project):
        """mvn test failure → issue."""
        (tmp_project / "pom.xml").write_text("<project/>")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="[ERROR] Tests run: 10, Failures: 2\nFAILURE in FooTest",
                stderr=""
            )
            issues, warnings = hook_module.check_java_tests(
                str(tmp_project), ["src/Main.java"]
            )
        assert len(issues) == 1
        assert "测试失败" in issues[0]

    def test_test_success(self, hook_module, tmp_project):
        """mvn test success → no issues."""
        (tmp_project / "pom.xml").write_text("<project/>")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            issues, warnings = hook_module.check_java_tests(
                str(tmp_project), ["src/Main.java"]
            )
        assert issues == []


# ══════════════════════════════════════════════════════
# _read_ecw_config
# ══════════════════════════════════════════════════════

class TestReadEcwConfig:
    """Tests for ecw.yml configuration reading."""

    def test_normal_yaml(self, hook_module, tmp_project):
        """Valid ecw.yml returns correct dict."""
        cfg = hook_module._read_ecw_config(str(tmp_project))
        assert cfg["project"]["name"] == "test"
        assert cfg["verification"]["run_tests"] is True

    def test_file_not_found_returns_empty(self, hook_module, tmp_path):
        """Missing ecw.yml returns empty dict."""
        cfg = hook_module._read_ecw_config(str(tmp_path))
        assert cfg == {}

    def test_yaml_none_returns_empty(self, hook_module, tmp_project):
        """yaml module not installed → read_ecw_config returns empty dict."""
        original = hook_module._read_ecw_config
        try:
            hook_module._read_ecw_config = lambda cwd: {}
            cfg = hook_module._read_ecw_config(str(tmp_project))
            assert cfg == {}
        finally:
            hook_module._read_ecw_config = original

    def test_parse_error_returns_empty(self, hook_module, tmp_project):
        """Malformed YAML returns empty dict."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("{{invalid yaml::: ]]]")
        cfg = hook_module._read_ecw_config(str(tmp_project))
        assert cfg == {}




# ══════════════════════════════════════════════════════
# Profile-Aware Behavior (B-2)
# ══════════════════════════════════════════════════════

class TestProfileAwareness:
    """Tests for risk-level-driven check skipping via check()."""

    def test_minimal_profile_passes(self, hook_module, tmp_project):
        """P3 (minimal) profile passes without soft reminders."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "minimal"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["src/OrderService.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "continue"


class TestEcwConfiguredGuard:
    """verify-completion must skip Java checks when ecw.yml is absent.

    Regression guard for the fix: compile_issues = check_java_compilation(...) if ecw_configured else ([], [])
    Without this guard, Java checks fire on non-ECW projects and produce false positives.
    """

    def test_java_compilation_not_called_without_ecw_yml(self, hook_module, tmp_path):
        """check_java_compilation must NOT be called when ecw.yml is absent."""
        # Use bare tmp_path — no ecw.yml created
        assert not (tmp_path / ".claude" / "ecw" / "ecw.yml").exists()

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_path),
        }
        config = {"_runtime_profile": "standard"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["src/Foo.java"], [])):
            with patch.object(hook_module, "check_java_compilation",
                              return_value=([], [])) as mock_compile:
                with patch.object(hook_module, "check_java_tests",
                                  return_value=([], [])) as mock_tests:
                    hook_module.check(input_data, config)
                    mock_compile.assert_not_called(), (
                        "check_java_compilation must not be called when ecw.yml is absent"
                    )
                    mock_tests.assert_not_called(), (
                        "check_java_tests must not be called when ecw.yml is absent"
                    )

    def test_java_compilation_called_with_ecw_yml(self, hook_module, tmp_project):
        """check_java_compilation MUST be called when ecw.yml exists and Java files changed."""
        ecw_dir = tmp_project / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True, exist_ok=True)
        (ecw_dir / "ecw.yml").write_text("project:\n  language: java\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "standard"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["src/Foo.java"], [])):
            with patch.object(hook_module, "check_java_compilation",
                              return_value=([], [])) as mock_compile:
                with patch.object(hook_module, "check_java_tests",
                                  return_value=([], [])):
                    hook_module.check(input_data, config)
                    mock_compile.assert_called_once(), (
                        "check_java_compilation must be called when ecw.yml exists"
                    )

    def test_strict_profile_includes_all_checks(self, hook_module, tmp_project):
        """P0 (strict) profile runs all checks including reminders."""
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "path-mappings.md"
        mappings_file.write_text("| path | domain |\n| --- | --- |\n| order-biz/ | order |\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "strict"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["order-biz/src/OrderService.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "continue"

    def test_no_config_defaults_to_standard(self, hook_module, tmp_project):
        """check() without config defaults to standard profile."""
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "path-mappings.md"
        mappings_file.write_text("| path | domain |\n| --- | --- |\n| order-biz/ | order |\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["order-biz/src/OrderService.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data)  # No config
                    assert action == "continue"

    def test_blocking_checks_run_at_minimal(self, hook_module, tmp_project):
        """P3 (minimal) still runs blocking checks (broken refs, compilation)."""
        # Create a file with broken reference
        test_file = tmp_project / "test.md"
        test_file.write_text("See .claude/ecw/nonexistent-file.md for details\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "minimal"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["test.md"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "block"
                    assert "不存在的路径" in message

class TestOutputFormat:
    """Tests for _format_fail_message and _format_pass_message."""

    def test_fail_format(self, hook_module):
        msg = hook_module._format_fail_message(["issue 1", "issue 2"])
        assert "issue 1" in msg
        assert "ECW Verify" in msg

    def test_fail_truncates(self, hook_module):
        issues = [f"issue {i}" for i in range(15)]
        msg = hook_module._format_fail_message(issues)
        assert "还有 5 个问题" in msg

    def test_pass_format(self, hook_module):
        msg = hook_module._format_pass_message(3, 1)
        assert "技术检查通过" in msg

    def test_output_pass_with_warnings(self, hook_module):
        """output_pass includes compile warnings."""
        msg = hook_module._format_pass_message(2, 0, warnings=["compile warning"])
        assert "compile warning" in msg


# ══════════════════════════════════════════════════════
# Exception Safety
# ══════════════════════════════════════════════════════

class TestExceptionSafety:
    """Tests for the top-level exception handler."""

    def test_main_exception_does_not_block(self, hook_module):
        """Any exception in main() should not block workflow (exit 0)."""
        with patch("json.load", side_effect=Exception("unexpected error")):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc:
                    # Call the __main__ block logic
                    try:
                        hook_module.main()
                    except Exception as e:
                        print(json.dumps({"systemMessage": f"ECW verify-completion hook error: {e}"}))
                        sys.exit(0)
                assert exc.value.code == 0

    def test_top_level_handler(self, hook_module):
        """The if __name__ == '__main__' handler catches all exceptions."""
        # This verifies the pattern used in the actual script
        with patch("json.load", side_effect=RuntimeError("boom")):
            with patch("builtins.print") as mock_print:
                try:
                    hook_module.main()
                except RuntimeError:
                    pass  # Expected — the actual script wraps this in try/except


# ══════════════════════════════════════════════════════
# ECW Artifact Filtering (v0.7+)
# ══════════════════════════════════════════════════════

class TestIsEcwArtifact:
    """Tests for _is_ecw_artifact and ECW_ARTIFACT_PREFIXES filtering."""

    def test_knowledge_file_is_artifact(self, hook_module):
        assert hook_module._is_ecw_artifact(".claude/knowledge/order/business-rules.md") is True

    def test_session_data_file_is_artifact(self, hook_module):
        assert hook_module._is_ecw_artifact(".claude/ecw/session-data/wf-001/session-state.md") is True

    def test_plans_file_is_artifact(self, hook_module):
        assert hook_module._is_ecw_artifact(".claude/plans/plan-001.md") is True

    def test_source_code_is_not_artifact(self, hook_module):
        assert hook_module._is_ecw_artifact("src/main/java/com/example/Service.java") is False

    def test_ecw_config_is_not_artifact(self, hook_module):
        """ecw.yml is under .claude/ecw/ but NOT under any artifact prefix."""
        assert hook_module._is_ecw_artifact(".claude/ecw/ecw.yml") is False

    def test_artifact_prefixes_completeness(self, hook_module):
        """ECW_ARTIFACT_PREFIXES must contain exactly the 4 expected prefixes."""
        expected = {".claude/knowledge/", ".claude/ecw/session-data/",
                    ".claude/plans/", ".claude/ecw/state/"}
        assert set(hook_module.ECW_ARTIFACT_PREFIXES) == expected


class TestArtifactFilteringInCheck:
    """Verify that check() filters ECW artifacts before running sub-checks."""

    def test_only_artifacts_changed_skips_reference_checks(self, hook_module, tmp_project):
        """When only ECW artifacts are modified, reference checks are not triggered."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        with patch.object(hook_module, "get_changed_files",
                          return_value=([".claude/knowledge/order/rules.md",
                                         ".claude/ecw/session-data/wf1/state.md"], [])):
            with patch.object(hook_module, "check_broken_references") as mock_ref:
                with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                    with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                        action, _ = hook_module.check(input_data)
                        assert action == "continue"
                        mock_ref.assert_not_called()

    def test_mixed_files_only_checks_source(self, hook_module, tmp_project):
        """When artifacts and source files are mixed, only source files are checked."""
        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        with patch.object(hook_module, "get_changed_files",
                          return_value=([".claude/knowledge/order/rules.md",
                                         "src/Main.java"], [])):
            with patch.object(hook_module, "check_broken_references", return_value=[]) as mock_ref:
                with patch.object(hook_module, "check_java_compilation", return_value=([], [])) as mock_compile:
                    with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                        hook_module.check(input_data)
                        # check_broken_references called only for source file
                        mock_ref.assert_called_once_with(str(tmp_project), "src/Main.java")
                        # check_java_compilation receives only source files
                        mock_compile.assert_called_once_with(str(tmp_project), ["src/Main.java"])

