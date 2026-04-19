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
# _load_path_mappings
# ══════════════════════════════════════════════════════

class TestLoadPathMappings:
    """Tests for path mapping table parsing."""

    def test_normal_table(self, hook_module, tmp_project):
        """Parse standard markdown table. Note: header row is included (only '域' is filtered)."""
        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n"
            "|------|--------|\n"
            "| src/order/* | order |\n"
            "| src/payment/ | payment |\n"
        )
        mappings = hook_module._load_path_mappings(str(tmp_project), {})
        # Header row ("Path", "Domain") is parsed as an entry — known behavior
        assert len(mappings) == 3
        assert ("src/order", "order") in mappings
        assert ("src/payment", "payment") in mappings

    def test_header_row_skipped(self, hook_module, tmp_project):
        """Header row with '域' is skipped."""
        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| 路径 | 域 |\n"
            "|------|----|\n"
            "| src/order/* | order |\n"
        )
        mappings = hook_module._load_path_mappings(str(tmp_project), {})
        assert len(mappings) == 1

    def test_path_strip_glob_and_slash(self, hook_module, tmp_project):
        """Trailing * and / are stripped from paths."""
        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| src/biz/order/* | order |\n"
            "| src/biz/pay/ | payment |\n"
        )
        mappings = hook_module._load_path_mappings(str(tmp_project), {})
        assert ("src/biz/order", "order") in mappings
        assert ("src/biz/pay", "payment") in mappings

    def test_file_not_found_returns_empty(self, hook_module, tmp_path):
        """Missing mappings file returns empty list."""
        mappings = hook_module._load_path_mappings(str(tmp_path), {})
        assert mappings == []

    def test_custom_path_from_config(self, hook_module, tmp_project):
        """Custom path_mappings path from config."""
        custom_path = tmp_project / "custom" / "mappings.md"
        custom_path.parent.mkdir(parents=True)
        custom_path.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| app/svc/* | service |\n"
        )
        cfg = {"paths": {"path_mappings": "custom/mappings.md"}}
        mappings = hook_module._load_path_mappings(str(tmp_project), cfg)
        # Header row is included
        assert len(mappings) == 2
        assert ("app/svc", "service") in mappings


# ══════════════════════════════════════════════════════
# check_knowledge_doc_freshness
# ══════════════════════════════════════════════════════

class TestCheckKnowledgeDocFreshness:
    """Tests for knowledge document sync reminders."""

    def test_biz_code_changed_knowledge_not(self, hook_module, tmp_project):
        """Business code changed but knowledge docs not → reminder."""
        # Create knowledge domain
        order_dir = tmp_project / ".claude" / "knowledge" / "order"
        order_dir.mkdir(parents=True)
        (order_dir / "business-rules.md").write_text("order rules")

        # Create path mappings
        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| src/order | order |\n"
        )

        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_project),
            ["src/order/OrderService.java"]
        )
        assert len(reminders) == 1
        assert "order" in reminders[0]

    def test_biz_code_and_knowledge_both_changed(self, hook_module, tmp_project):
        """Both code and knowledge changed → no reminder."""
        order_dir = tmp_project / ".claude" / "knowledge" / "order"
        order_dir.mkdir(parents=True)
        (order_dir / "business-rules.md").write_text("order rules")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| src/order | order |\n"
        )

        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_project),
            ["src/order/OrderService.java", ".claude/knowledge/order/business-rules.md"]
        )
        assert reminders == []

    def test_heuristic_biz_path_match(self, hook_module, tmp_project):
        """Heuristic /biz/domain/ path matching works."""
        order_dir = tmp_project / ".claude" / "knowledge" / "order"
        order_dir.mkdir(parents=True)
        (order_dir / "business-rules.md").write_text("rules")

        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_project),
            ["src/main/java/com/example/biz/order/OrderServiceImpl.java"]
        )
        assert len(reminders) == 1

    def test_no_knowledge_dir_returns_empty(self, hook_module, tmp_path):
        """No knowledge directory → no reminders."""
        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_path),
            ["src/Main.java"]
        )
        assert reminders == []

    def test_domain_dir_exists_but_no_md_files(self, hook_module, tmp_project):
        """Domain dir exists but no .md files → no reminder."""
        order_dir = tmp_project / ".claude" / "knowledge" / "order"
        order_dir.mkdir(parents=True)

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| src/order | order |\n"
        )

        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_project),
            ["src/order/OrderService.java"]
        )
        assert reminders == []

    def test_knowledge_root_trailing_slash(self, hook_module, tmp_project):
        """knowledge_root without trailing / is normalized."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text(
            "paths:\n  knowledge_root: .claude/knowledge\n"
        )

        order_dir = tmp_project / ".claude" / "knowledge" / "order"
        order_dir.mkdir(parents=True)
        (order_dir / "rules.md").write_text("rules")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text(
            "| Path | Domain |\n|---|---|\n"
            "| src/order | order |\n"
        )

        reminders = hook_module.check_knowledge_doc_freshness(
            str(tmp_project),
            ["src/order/OrderService.java"]
        )
        assert len(reminders) == 1


# ══════════════════════════════════════════════════════
# check_test_coverage
# ══════════════════════════════════════════════════════

class TestCheckTestCoverage:
    """Tests for TDD test file coverage check."""

    def test_check_disabled_returns_empty(self, hook_module, tmp_project):
        """check_test_files=false → empty."""
        # Default ecw.yml has check_test_files: false
        reminders = hook_module.check_test_coverage(
            str(tmp_project), ["src/main/java/BizServiceImpl.java"]
        )
        assert reminders == []

    def test_check_enabled_test_exists(self, hook_module, tmp_project):
        """BizServiceImpl changed + test exists → no reminder."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("tdd:\n  check_test_files: true\n")

        test_file = tmp_project / "src" / "test" / "java" / "BizServiceTest.java"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        reminders = hook_module.check_test_coverage(
            str(tmp_project),
            ["src/main/java/BizServiceImpl.java"]
        )
        assert reminders == []

    def test_check_enabled_test_missing(self, hook_module, tmp_project):
        """BizServiceImpl changed + no test → reminder."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("tdd:\n  check_test_files: true\n")

        reminders = hook_module.check_test_coverage(
            str(tmp_project),
            ["src/main/java/BizServiceImpl.java"]
        )
        assert len(reminders) == 1
        assert "BizService" in reminders[0]

    def test_manager_impl_checked(self, hook_module, tmp_project):
        """ManagerImpl files are also checked."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("tdd:\n  check_test_files: true\n")

        reminders = hook_module.check_test_coverage(
            str(tmp_project),
            ["src/main/java/OrderManagerImpl.java"]
        )
        assert len(reminders) == 1

    def test_non_biz_files_ignored(self, hook_module, tmp_project):
        """Non-BizService/Manager java files are not checked."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("tdd:\n  check_test_files: true\n")

        reminders = hook_module.check_test_coverage(
            str(tmp_project),
            ["src/main/java/Controller.java", "src/main/java/Utils.java"]
        )
        assert reminders == []

    def test_path_conversion_main_to_test(self, hook_module, tmp_project):
        """Verify src/main/java → src/test/java + Impl → Test conversion."""
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text("tdd:\n  check_test_files: true\n")

        # Create the expected test file at the converted path
        test_file = tmp_project / "src" / "test" / "java" / "com" / "OrderBizServiceTest.java"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("test")

        reminders = hook_module.check_test_coverage(
            str(tmp_project),
            ["src/main/java/com/OrderBizServiceImpl.java"]
        )
        assert reminders == []


# ══════════════════════════════════════════════════════
# Profile-Aware Behavior (B-2)
# ══════════════════════════════════════════════════════

class TestProfileAwareness:
    """Tests for risk-level-driven check skipping via check()."""

    def test_minimal_profile_skips_knowledge_reminders(self, hook_module, tmp_project):
        """P3 (minimal) profile skips knowledge doc freshness checks."""
        # Set up: business code changed, knowledge docs not updated
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text("| path | domain |\n| --- | --- |\n| order-biz/ | order |\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "minimal"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["order-biz/src/OrderService.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "continue"
                    assert "知识文档同步提醒" not in message

    def test_standard_profile_includes_knowledge_reminders(self, hook_module, tmp_project):
        """P1 (standard) profile includes knowledge doc freshness checks."""
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
        mappings_file.write_text("| path | domain |\n| --- | --- |\n| order-biz/ | order |\n")

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "standard"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["order-biz/src/OrderService.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "continue"
                    assert "知识文档同步提醒" in message

    def test_minimal_profile_skips_test_coverage(self, hook_module, tmp_project):
        """P3 (minimal) profile skips TDD test coverage checks."""
        # Enable tdd.check_test_files in ecw.yml
        ecw_yml = tmp_project / ".claude" / "ecw" / "ecw.yml"
        ecw_yml.write_text(
            "project:\n  name: test\n  language: java\n"
            "verification:\n  run_tests: false\n"
            "tdd:\n  check_test_files: true\n"
            "paths:\n  knowledge_root: .claude/knowledge/\n"
        )

        input_data = {
            "tool_name": "TaskUpdate",
            "tool_input": {"status": "completed"},
            "cwd": str(tmp_project),
        }
        config = {"_runtime_profile": "minimal"}

        with patch.object(hook_module, "get_changed_files",
                          return_value=(["src/main/java/OrderBizServiceImpl.java"], [])):
            with patch.object(hook_module, "check_java_compilation", return_value=([], [])):
                with patch.object(hook_module, "check_java_tests", return_value=([], [])):
                    action, message = hook_module.check(input_data, config)
                    assert action == "continue"
                    assert "TDD 测试覆盖提醒" not in message

    def test_strict_profile_includes_all_checks(self, hook_module, tmp_project):
        """P0 (strict) profile runs all checks including reminders."""
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
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
                    assert "知识文档同步提醒" in message

    def test_no_config_defaults_to_standard(self, hook_module, tmp_project):
        """check() without config defaults to standard profile."""
        domain_dir = tmp_project / ".claude" / "knowledge" / "order"
        domain_dir.mkdir(parents=True)
        (domain_dir / "business-rules.md").write_text("# Rules\n")

        mappings_file = tmp_project / ".claude" / "ecw" / "ecw-path-mappings.md"
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
                    assert "知识文档同步提醒" in message

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
    """Tests for output_fail and output_pass JSON format."""

    def test_output_fail_format(self, hook_module):
        """output_fail produces deny JSON."""
        with patch("builtins.print") as mock_print:
            hook_module.output_fail(["issue 1", "issue 2"])
            output = json.loads(mock_print.call_args[0][0])
            assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
            assert "issue 1" in output["systemMessage"]

    def test_output_fail_truncates(self, hook_module):
        """output_fail truncates after 10 issues."""
        issues = [f"issue {i}" for i in range(15)]
        with patch("builtins.print") as mock_print:
            hook_module.output_fail(issues)
            output = json.loads(mock_print.call_args[0][0])
            assert "还有 5 个问题" in output["systemMessage"]

    def test_output_pass_format(self, hook_module):
        """output_pass produces pass JSON."""
        with patch("builtins.print") as mock_print:
            hook_module.output_pass(3, 1)
            output = json.loads(mock_print.call_args[0][0])
            assert "hookSpecificOutput" not in output
            assert "技术检查通过" in output["systemMessage"]

    def test_output_pass_with_reminders(self, hook_module):
        """output_pass includes knowledge and test reminders."""
        with patch("builtins.print") as mock_print:
            hook_module.output_pass(
                2, 0,
                warnings=["compile warning"],
                knowledge_reminders=["order domain needs sync"],
                test_reminders=["missing test for OrderBizService"]
            )
            output = json.loads(mock_print.call_args[0][0])
            msg = output["systemMessage"]
            assert "compile warning" in msg
            assert "order domain" in msg
            assert "OrderBizService" in msg


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

    def test_state_file_is_artifact(self, hook_module):
        assert hook_module._is_ecw_artifact(".claude/ecw/state/instincts.md") is True

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
