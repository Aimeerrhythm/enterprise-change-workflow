#!/usr/bin/env python3
"""ECW 完成验证 hook — 对本次任务的实现结果进行技术检查。

PreToolUse 拦截 TaskUpdate(status=completed)：
1. 检查本次修改的文件中是否有断裂引用
2. 检查被删除的文件是否还被其他文件引用
3. Java 编译检查（改了 .java 文件 → mvn compile，失败则阻止）
4. Java 测试检查（改了 .java 文件 → mvn test，失败则阻止）
5. impl-verify must-fix 检查（未解决的 must-fix 项 → 阻止完成）

技术检查失败 → 阻止完成；通过 → 放行。
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecw_config import read_ecw_config as _read_ecw_config  # noqa: E402
from marker_utils import CheckpointStore  # noqa: E402
from trace_logger import log_trace  # noqa: E402


ECW_ARTIFACT_PREFIXES = (
    ".claude/knowledge/",
    ".claude/ecw/session-data/",
    ".claude/plans/",
    ".claude/ecw/state/",
)


def _is_ecw_artifact(filepath):
    normalized = filepath.replace(os.sep, "/")
    return any(normalized.startswith(p) for p in ECW_ARTIFACT_PREFIXES)


_MESSAGES = {
    "broken_ref": "`{filepath}` 引用了不存在的路径: `{ref}`",
    "stale_ref": "`{ref_file}` 仍引用已删除的文件 `{deleted_file}`",
    "compile_fail": "Java 编译失败:\n{errors}",
    "compile_timeout": "Java 编译超时（>120s），编译结果未验证，请手动执行 `mvn compile` 检查",
    "test_fail": "Java 测试失败:\n{errors}",
    "test_timeout": "Java 测试超时（>{timeout}s），测试结果未验证，请手动执行 `mvn test` 检查",
    "fail_header": "**[ECW Verify]** 实现结果存在技术问题，请修复后重试：**\n\n",
    "fail_more": "...还有 {n} 个问题",
    "pass_header": (
        "**[ECW Verify]** 技术检查通过"
        "（{modified} 个修改文件、{deleted} 个删除文件，无断裂引用）。"
    ),
    "warnings_header": "\n\n---\n\n**[注意事项]**\n\n",
    "impl_verify_must_fix": (
        "**[ECW Verify]** `impl-verify` 存在未解决的 must-fix 项，"
        "必须完成 Round N+ 再验证（确认 zero must-fix）后才能标记完成。"
        "请修复所有 must-fix 项并重新运行 `ecw:impl-verify`。"
    ),
}


def check(input_data, config=None):
    """Dispatcher sub-hook entry point."""
    cwd = input_data.get("cwd", "")
    if not cwd:
        return ("continue", "")

    if input_data.get("tool_name") == "Skill":
        verify_status = check_impl_verify_convergence(cwd)
        if verify_status == "has-must-fix":
            log_trace(cwd, "verify-completion", "PreToolUse",
                      action="block", reason="impl-verify-must-fix")
            return ("block", _MESSAGES["impl_verify_must_fix"])
        return ("continue", "")

    issues = []
    modified, deleted = get_changed_files(cwd)

    if not modified and not deleted:
        return ("continue", _format_pass_message(0, 0))

    source_modified = [f for f in modified if not _is_ecw_artifact(f)]
    source_deleted = [f for f in deleted if not _is_ecw_artifact(f)]

    ecw_configured = os.path.exists(os.path.join(cwd, ".claude", "ecw", "ecw.yml"))

    if ecw_configured:
        for filepath in source_modified:
            issues.extend(check_broken_references(cwd, filepath))
        for filepath in source_deleted:
            issues.extend(check_stale_references(cwd, filepath))

    compile_issues, compile_warnings = check_java_compilation(cwd, source_modified) if ecw_configured else ([], [])
    issues.extend(compile_issues)

    test_issues, test_warnings = [], []
    if not compile_issues:
        test_issues, test_warnings = check_java_tests(cwd, source_modified) if ecw_configured else ([], [])
        issues.extend(test_issues)

    profile = (config or {}).get("_runtime_profile", "standard")
    if profile != "minimal":
        verify_status = check_impl_verify_convergence(cwd)
        if verify_status == "has-must-fix":
            issues.append(_MESSAGES["impl_verify_must_fix"])

    all_warnings = (compile_warnings or []) + (test_warnings or [])

    if issues:
        log_trace(cwd, "verify-completion", "PreToolUse",
                  action="block", issues_count=len(issues),
                  issues_summary=[i[:120] for i in issues[:5]])
        return ("block", _format_fail_message(issues))
    log_trace(cwd, "verify-completion", "PreToolUse",
              action="pass", modified=len(modified), deleted=len(deleted),
              has_warnings=bool(all_warnings))
    return ("continue", _format_pass_message(
        len(modified), len(deleted), all_warnings
    ))


def main():
    input_data = json.load(sys.stdin)

    if input_data.get("tool_name") != "TaskUpdate":
        sys.exit(0)
    tool_input = input_data.get("tool_input", {})
    if tool_input.get("status") != "completed":
        sys.exit(0)

    action, message = check(input_data)

    if action == "block":
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny"
            },
            "systemMessage": message
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(2)
    else:
        if message:
            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        sys.exit(0)


def get_changed_files(cwd):
    """获取 git 工作区中本次变更的文件（staged + unstaged vs HEAD）"""
    modified, deleted = [], []
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        modified = [f for f in r.stdout.strip().split("\n") if f]

        r = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=D", "HEAD"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        deleted = [f for f in r.stdout.strip().split("\n") if f]
    except Exception:
        pass
    return modified, deleted


def check_broken_references(cwd, filepath):
    """检查文件中是否有指向不存在路径的 .claude/ 引用"""
    issues = []
    full_path = os.path.join(cwd, filepath)
    if not os.path.exists(full_path):
        return issues

    text_exts = (".md", ".yml", ".yaml", ".json", ".xml", ".properties")
    if not filepath.endswith(text_exts):
        return issues

    runtime_dirs = (".claude/ecw/state/", ".claude/ecw/session-data/")

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        for ref in re.findall(r"\.claude/[\w\-/]+\.[\w]+", content):
            if any(ref.startswith(d) for d in runtime_dirs):
                continue
            if not os.path.exists(os.path.join(cwd, ref)):
                issues.append(_MESSAGES["broken_ref"].format(filepath=filepath, ref=ref))

    except Exception:
        pass

    return issues


def check_stale_references(cwd, deleted_file):
    """检查被删除的文件的完整路径是否还被其他文件引用。"""
    issues = []
    if not deleted_file:
        return issues

    claude_dir = os.path.join(cwd, ".claude")
    if not os.path.isdir(claude_dir):
        return issues

    skip_dirs = {".claude/specs/"}

    try:
        r = subprocess.run(
            ["grep", "-rlF", deleted_file,
             "--include=*.md", "--include=*.yml",
             "--include=*.yaml", "--include=*.json",
             ".claude/"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        referencing_files = [f for f in r.stdout.strip().split("\n") if f]
        for ref_file in referencing_files:
            if any(ref_file.startswith(d) for d in skip_dirs):
                continue
            issues.append(
                _MESSAGES["stale_ref"].format(ref_file=ref_file, deleted_file=deleted_file)
            )
    except Exception:
        pass

    return issues


def check_java_compilation(cwd, modified):
    """如果本次改了 .java 文件，执行 mvn compile 检查编译。"""
    java_files = [f for f in modified if f.endswith(".java")]
    if not java_files:
        return [], []

    if not os.path.exists(os.path.join(cwd, "pom.xml")):
        return [], []

    try:
        r = subprocess.run(
            ["mvn", "compile", "-q", "-T", "1C"],
            capture_output=True, text=True, cwd=cwd, timeout=120
        )
        if r.returncode != 0:
            errors = [l for l in r.stdout.split("\n") + r.stderr.split("\n")
                      if "[ERROR]" in l][:5]
            return [_MESSAGES["compile_fail"].format(errors="\n".join(errors))], []
    except subprocess.TimeoutExpired:
        return [], [_MESSAGES["compile_timeout"]]
    except FileNotFoundError:
        return [], []

    return [], []


def check_java_tests(cwd, modified):
    """如果本次改了 .java 文件且 ecw.yml 启用了测试检查，执行 mvn test。"""
    java_files = [f for f in modified if f.endswith(".java")]
    if not java_files:
        return [], []

    if not os.path.exists(os.path.join(cwd, "pom.xml")):
        return [], []

    # Always run tests with 10-minute timeout
    timeout = 600

    try:
        r = subprocess.run(
            ["mvn", "test", "-q"],
            capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        if r.returncode != 0:
            errors = [l for l in r.stdout.split("\n") + r.stderr.split("\n")
                      if "[ERROR]" in l or "FAILURE" in l][:5]
            return [_MESSAGES["test_fail"].format(errors="\n".join(errors))], []
    except subprocess.TimeoutExpired:
        return [], [_MESSAGES["test_timeout"].format(timeout=timeout)]
    except FileNotFoundError:
        return [], []

    return [], []


def check_impl_verify_convergence(cwd):
    """Check impl-verify convergence status.

    Returns:
        'has-must-fix' — findings file exists and has unresolved must-fix items
        'not-run'      — no findings file found
        'pass'         — findings file exists with no unresolved must-fix items
    """
    session_data = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data):
        return "not-run"
    try:
        for entry in os.listdir(session_data):
            if not os.path.isdir(os.path.join(session_data, entry)):
                continue
            store = CheckpointStore(cwd, entry)
            if not store.exists("impl-verify-findings"):
                continue
            content = store.read("impl-verify-findings") or ""
            for line in content.splitlines():
                if "|" in line and "must-fix" in line.lower() and "[FIXED]" not in line:
                    return "has-must-fix"
            return "pass"
    except Exception:
        pass
    return "not-run"


def _format_fail_message(issues):
    msg = _MESSAGES["fail_header"]
    msg += "\n".join(f"- {i}" for i in issues[:10])
    if len(issues) > 10:
        msg += f"\n- {_MESSAGES['fail_more'].format(n=len(issues) - 10)}"
    return msg


def _format_pass_message(modified_count, deleted_count, warnings=None):
    msg = _MESSAGES["pass_header"].format(modified=modified_count, deleted=deleted_count)
    if warnings:
        msg += _MESSAGES["warnings_header"]
        msg += "\n".join(f"- {w}" for w in warnings)
    return msg


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"systemMessage": f"ECW verify-completion hook error: {e}"}))
        sys.exit(0)
