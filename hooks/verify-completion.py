#!/usr/bin/env python3
"""ECW 完成验证 hook — 对本次任务的实现结果进行技术检查。

PreToolUse 拦截 TaskUpdate(status=completed)：
1. 检查本次修改的文件中是否有断裂引用
2. 检查被删除的文件是否还被其他文件引用
3. Java 编译检查（改了 .java 文件 → mvn compile，失败则阻止）
4. Java 测试检查（改了 .java 文件 → mvn test，失败则阻止；ecw.yml verification.run_tests 控制开关）
5. 知识文档同步提醒（业务代码改了但对应域知识文档没动 → 定向提醒）
6. TDD 测试覆盖提醒（BizService/Manager 改了但无对应测试文件 → 定向提醒；ecw.yml tdd.check_test_files 控制开关）
7. impl-verify 执行状态检查（session-data 下无 impl-verify-findings.md → 提醒先执行 impl-verify）
8. 知识库过时引用提醒（stale-refs.md 存在 → 提醒文档中有过时类引用）
9. doc-tracker misleading 提醒（doc-tracker.md 近期有 doc-misleading → 提醒更新对应文档）
10. Repo Map 刷新提醒（component_types 相关文件有结构变更 → 提醒刷新 repo-map）
技术检查 1-4 失败 → 阻止完成；通过 → 放行 + 注入语义验证提醒 + 知识文档定向提醒 + TDD 测试覆盖提醒。
"""

import glob as globmod
import json
import os
import re
import subprocess
import sys

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ecw_config import read_ecw_config as _read_ecw_config  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


ECW_ARTIFACT_PREFIXES = (
    ".claude/knowledge/",
    ".claude/ecw/session-data/",
    ".claude/plans/",
    ".claude/ecw/state/",
)


def _is_ecw_artifact(filepath):
    normalized = filepath.replace(os.sep, "/")
    return any(normalized.startswith(p) for p in ECW_ARTIFACT_PREFIXES)


# ── User-visible messages (locale: zh-CN) ──
# All user-facing strings are collected here for future i18n.

_MESSAGES = {
    "broken_ref": "`{filepath}` 引用了不存在的路径: `{ref}`",
    "stale_ref": "`{ref_file}` 仍引用已删除的文件 `{deleted_file}`",
    "compile_fail": "Java 编译失败:\n{errors}",
    "compile_timeout": "Java 编译超时（>120s），编译结果未验证，请手动执行 `mvn compile` 检查",
    "test_fail": "Java 测试失败:\n{errors}",
    "test_timeout": "Java 测试超时（>{timeout}s），测试结果未验证，请手动执行 `mvn test` 检查",
    "knowledge_sync": (
        "域 `{domain}` 的业务代码有变更，但知识文档未更新。"
        "请检查以下文档是否需要同步：\n{file_list}"
    ),
    "test_coverage": (
        "`{class_name}` 有代码变更但未找到对应测试文件 `{test_file}`。"
        "TDD 流程要求新增/修改的 BizService 和 Manager 需有对应测试。"
    ),
    "fail_header": "**[ECW Verify]** 实现结果存在技术问题，请修复后重试：**\n\n",
    "fail_more": "...还有 {n} 个问题",
    "pass_header": (
        "**[ECW Verify]** 技术检查通过"
        "（{modified} 个修改文件、{deleted} 个删除文件，无断裂引用）。"
    ),
    "warnings_header": "\n\n---\n\n**[注意事项]**\n\n",
    "knowledge_header": "\n\n---\n\n**[知识文档同步提醒]** 以下域的业务代码有变更，请确认知识文档是否需要同步更新：\n\n",
    "tdd_header": "\n\n---\n\n**[TDD 测试覆盖提醒]** 以下业务组件有代码变更但缺少对应测试：\n\n",
    "impl_verify_reminder": (
        "**语义验证**：未检测到 `impl-verify-findings.md`，"
        "`ecw:impl-verify` 可能尚未执行。"
        "建议先执行实现正确性验证再标记完成（P3 或纯格式/注释变更可跳过）。"
    ),
    "stale_refs_reminder": (
        "知识库审计发现 {count} 条过时引用（详见 `{path}`）。"
        "建议更新相关文档或运行 `/ecw:knowledge-audit` 重新审计。"
    ),
    "doc_misleading_reminder": (
        "近期 doc-tracker 记录了 doc-misleading 事件，以下文档可能与代码不一致：\n{file_list}"
    ),
    "repomap_refresh_reminder": (
        "本次变更涉及组件结构文件（新增/删除/重命名），"
        "建议运行 `/ecw:knowledge-repomap` 刷新代码结构索引。"
    ),
    "km_header": "\n\n---\n\n**[知识库维护提醒]**\n\n",
}


def check(input_data, config=None):
    """Dispatcher sub-hook entry point.

    Called by dispatcher.py when tool_name=TaskUpdate, status=completed.
    Also usable directly for testing.

    Args:
        input_data: Hook input dict (must contain "cwd")
        config: Optional dict with ecw.yml config + _runtime_profile from dispatcher

    Returns:
        (action, message) tuple:
        - ("block", reason): technical check failed, deny completion
        - ("continue", text): checks passed, text contains reminders (may be empty)
    """
    cwd = input_data.get("cwd", "")
    if not cwd:
        return ("continue", "")

    profile = (config or {}).get("_runtime_profile", "standard")

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

    compile_issues, compile_warnings = check_java_compilation(cwd, source_modified)
    issues.extend(compile_issues)

    test_issues, test_warnings = [], []
    if not compile_issues:
        test_issues, test_warnings = check_java_tests(cwd, source_modified)
        issues.extend(test_issues)

    # Non-essential reminders: skip at "minimal" profile (P3)
    knowledge_reminders = []
    test_reminders = []
    km_reminders = []
    impl_verify_ran = True
    if profile != "minimal":
        knowledge_reminders = check_knowledge_doc_freshness(cwd, source_modified)
        test_reminders = check_test_coverage(cwd, source_modified)
        impl_verify_ran = check_impl_verify_executed(cwd)
        km_reminders = check_knowledge_maintenance(cwd, source_modified)

    all_warnings = (compile_warnings or []) + (test_warnings or [])

    if issues:
        return ("block", _format_fail_message(issues))
    return ("continue", _format_pass_message(
        len(modified), len(deleted), all_warnings, knowledge_reminders, test_reminders,
        impl_verify_ran, km_reminders
    ))


def main():
    input_data = json.load(sys.stdin)

    # 只拦截 TaskUpdate(status=completed)
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

    # 只检查文本配置文件
    text_exts = (".md", ".yml", ".yaml", ".json", ".xml", ".properties")
    if not filepath.endswith(text_exts):
        return issues

    # 运行时自动生成的目录 — 文件可能尚未创建，跳过存在性检查
    runtime_dirs = (".claude/ecw/state/", ".claude/ecw/session-data/")

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 匹配 .claude/ 开头的文件路径引用（带扩展名）
        for ref in re.findall(r"\.claude/[\w\-/]+\.[\w]+", content):
            if any(ref.startswith(d) for d in runtime_dirs):
                continue
            if not os.path.exists(os.path.join(cwd, ref)):
                issues.append(_MESSAGES["broken_ref"].format(filepath=filepath, ref=ref))

    except Exception:
        pass

    return issues


def check_stale_references(cwd, deleted_file):
    """检查被删除的文件的完整路径是否还被其他文件引用。

    用完整路径 grep，避免 basename 误报（文件从 A 移到 B 时，
    引用 B 的文件不应被标记为"引用了已删除的 A"）。
    """
    issues = []
    if not deleted_file:
        return issues

    claude_dir = os.path.join(cwd, ".claude")
    if not os.path.isdir(claude_dir):
        return issues

    # 跳过历史/快照性质的目录（specs/ 记录设计时状态，不应跟踪引用变更）
    skip_dirs = {".claude/specs/"}

    try:
        # 用完整相对路径 grep，而不是 basename
        r = subprocess.run(
            ["grep", "-rl", deleted_file,
             "--include=*.md", "--include=*.yml",
             "--include=*.yaml", "--include=*.json",
             ".claude/"],
            capture_output=True, text=True, cwd=cwd, timeout=5
        )
        referencing_files = [f for f in r.stdout.strip().split("\n") if f]
        for ref_file in referencing_files:
            # 跳过快照目录中的文件
            if any(ref_file.startswith(d) for d in skip_dirs):
                continue
            issues.append(
                _MESSAGES["stale_ref"].format(ref_file=ref_file, deleted_file=deleted_file)
            )
    except Exception:
        pass

    return issues


def check_java_compilation(cwd, modified):
    """如果本次改了 .java 文件，执行 mvn compile 检查编译。

    返回 (issues, warnings)：
    - issues: 编译失败 → deny
    - warnings: 超时等非致命情况 → 提醒但不阻止
    """
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
        return [], []  # mvn 不在 PATH 中，跳过

    return [], []


def check_java_tests(cwd, modified):
    """如果本次改了 .java 文件且 ecw.yml 启用了测试检查，执行 mvn test。

    受 ecw.yml verification.run_tests 控制（默认 true）。
    返回 (issues, warnings)：
    - issues: 测试失败 → deny
    - warnings: 超时等非致命情况 → 提醒但不阻止
    """
    java_files = [f for f in modified if f.endswith(".java")]
    if not java_files:
        return [], []

    if not os.path.exists(os.path.join(cwd, "pom.xml")):
        return [], []

    # 读取 ecw.yml 配置，默认启用测试
    cfg = _read_ecw_config(cwd)
    verification = cfg.get("verification", {})
    if not verification.get("run_tests", True):
        return [], []

    timeout = verification.get("test_timeout", 300)

    try:
        r = subprocess.run(
            ["mvn", "test", "-q", "-T", "1C"],
            capture_output=True, text=True, cwd=cwd, timeout=timeout
        )
        if r.returncode != 0:
            errors = [l for l in r.stdout.split("\n") + r.stderr.split("\n")
                      if "[ERROR]" in l or "FAILURE" in l.upper()][:8]
            return [_MESSAGES["test_fail"].format(errors="\n".join(errors))], []
    except subprocess.TimeoutExpired:
        return [], [_MESSAGES["test_timeout"].format(timeout=timeout)]
    except FileNotFoundError:
        return [], []  # mvn 不在 PATH 中，跳过

    return [], []


def _load_path_mappings(cwd, cfg):
    """从 ecw-path-mappings.md 加载 代码路径→域 映射表。

    解析 markdown 表格行，格式：| 路径前缀/glob | 域名 |
    返回 [(path_prefix, domain), ...] 列表。
    """
    mappings = []
    mappings_path = cfg.get("paths", {}).get("path_mappings", ".claude/ecw/ecw-path-mappings.md")
    full_path = os.path.join(cwd, mappings_path)
    if not os.path.exists(full_path):
        return mappings

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                # 跳过表头和分隔行
                if not line.startswith("|") or "---" in line:
                    continue
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    path_prefix = parts[0].rstrip("*").rstrip("/")
                    domain = parts[1]
                    if path_prefix and domain and domain != "域":
                        mappings.append((path_prefix, domain))
    except Exception:
        pass

    return mappings


def _match_domain_by_mappings(filepath, mappings):
    """用 path_mappings 匹配文件路径到域。返回域名或 None。"""
    for path_prefix, domain in mappings:
        if filepath.startswith(path_prefix) or ("/" + path_prefix) in filepath:
            return domain
    return None


def check_knowledge_doc_freshness(cwd, modified):
    """检查业务代码变更是否需要同步更新知识文档。返回定向提醒列表（不阻止完成）。"""
    reminders = []

    cfg = _read_ecw_config(cwd)
    knowledge_root = cfg.get("paths", {}).get("knowledge_root", ".claude/knowledge/")

    # 确保 knowledge_root 末尾有 /
    if not knowledge_root.endswith("/"):
        knowledge_root += "/"

    knowledge_abs = os.path.join(cwd, knowledge_root)
    if not os.path.isdir(knowledge_abs):
        return reminders

    # 扫描受影响的域：从 modified 文件中提取
    biz_domains_changed = set()
    knowledge_domains_changed = set()

    # 尝试读取 ecw-path-mappings 做精确域匹配
    path_mappings = _load_path_mappings(cwd, cfg)

    for f in modified:
        # 优先用 path-mappings 精确匹配
        mapped_domain = _match_domain_by_mappings(f, path_mappings)
        if mapped_domain:
            biz_domains_changed.add(mapped_domain)
        else:
            # 回退启发式匹配业务代码路径（支持连字符域名）
            m = re.search(r'/biz/([\w-]+)/', f)
            if m:
                biz_domains_changed.add(m.group(1))
            m = re.search(r'/service/([\w-]+)/', f)
            if m:
                biz_domains_changed.add(m.group(1))

        # 匹配知识文档路径（使用实际的 knowledge_root）
        kr_pattern = re.escape(knowledge_root) + r'(\w[\w-]*)/'
        m = re.search(kr_pattern, f)
        if m:
            knowledge_domains_changed.add(m.group(1))

    # 差集：代码改了但文档没动的域
    for domain in sorted(biz_domains_changed - knowledge_domains_changed):
        domain_dir = os.path.join(knowledge_abs, domain)
        if not os.path.isdir(domain_dir):
            continue

        # 列出该域下所有 .md 文件
        md_files = sorted(globmod.glob(os.path.join(domain_dir, "*.md")))
        if not md_files:
            continue

        file_list = "\n".join(
            f"  - {os.path.relpath(p, cwd)}" for p in md_files
        )
        reminders.append(
            _MESSAGES["knowledge_sync"].format(domain=domain, file_list=file_list)
        )

    return reminders


def check_impl_verify_executed(cwd):
    """检查 session-data 下是否存在 impl-verify-findings.md，判断 impl-verify 是否已执行。"""
    session_data = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data):
        return False
    for workflow_dir in os.listdir(session_data):
        findings = os.path.join(session_data, workflow_dir, "impl-verify-findings.md")
        if os.path.isfile(findings):
            return True
    return False


def check_test_coverage(cwd, modified):
    """检查新增/修改的 BizService/Manager 是否有对应测试文件。返回提醒列表（不阻止完成）。"""
    reminders = []

    cfg = _read_ecw_config(cwd)
    tdd = cfg.get("tdd", {})
    if not tdd.get("check_test_files", False):
        return reminders

    biz_files = [f for f in modified
                 if f.endswith(".java")
                 and ("BizServiceImpl" in f or "ManagerImpl" in f)]

    if not biz_files:
        return reminders

    for biz_file in biz_files:
        # src/main/java → src/test/java, Impl.java → Test.java
        test_file = biz_file.replace("src/main/java", "src/test/java")
        test_file = re.sub(r'Impl\.java$', 'Test.java', test_file)

        if not os.path.exists(os.path.join(cwd, test_file)):
            class_name = os.path.basename(biz_file).replace("Impl.java", "")
            reminders.append(
                _MESSAGES["test_coverage"].format(class_name=class_name, test_file=test_file)
            )

    return reminders


def check_knowledge_maintenance(cwd, modified):
    """知识库维护提醒：消费 audit/track/repomap 产出数据。返回提醒列表（不阻止完成）。"""
    reminders = []

    cfg = _read_ecw_config(cwd)
    km = cfg.get("knowledge_maintenance", {})

    # 1. stale-refs: audit 产出的过时引用
    stale_refs_path = ".claude/ecw/state/stale-refs.md"
    stale_refs_full = os.path.join(cwd, stale_refs_path)
    if os.path.isfile(stale_refs_full):
        try:
            with open(stale_refs_full, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            stale_count = content.count("| ")
            # 减去表头行（每个表有 2 行表头: header + separator）
            table_count = content.count("| Doc ")
            stale_count = max(0, stale_count - table_count * 2)
            if stale_count > 0:
                reminders.append(
                    _MESSAGES["stale_refs_reminder"].format(
                        count=stale_count, path=stale_refs_path
                    )
                )
        except Exception:
            pass

    # 2. doc-tracker: 近期 misleading 事件
    tracker_path = ".claude/ecw/knowledge-ops/doc-tracker.md"
    tracker_full = os.path.join(cwd, tracker_path)
    if os.path.isfile(tracker_full):
        try:
            with open(tracker_full, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            misleading_files = []
            for line in content.split("\n"):
                if "doc-misleading" in line.lower():
                    # 提取文档路径: "**doc-misleading**: path/to/doc §section → ..."
                    m = re.search(r'\*\*doc-misleading\*\*:\s*(\S+)', line)
                    if m:
                        misleading_files.append(m.group(1))
            if misleading_files:
                file_list = "\n".join(f"  - `{f}`" for f in misleading_files[-5:])
                reminders.append(
                    _MESSAGES["doc_misleading_reminder"].format(file_list=file_list)
                )
        except Exception:
            pass

    # 3. repo-map 刷新: 检测 component_types 相关文件有结构变更（新增/删除/重命名）
    component_types = cfg.get("component_types", [])
    if component_types and modified:
        component_suffixes = []
        for ct in component_types:
            name = ct.get("name", "")
            if name:
                component_suffixes.append(name + ".java")

        if component_suffixes:
            structural_change = False
            for f in modified:
                basename = os.path.basename(f)
                if any(basename.endswith(s) for s in component_suffixes):
                    structural_change = True
                    break

            if structural_change:
                repomap_path = ".claude/ecw/knowledge-ops/repo-map.md"
                repomap_full = os.path.join(cwd, repomap_path)
                if os.path.isfile(repomap_full):
                    reminders.append(_MESSAGES["repomap_refresh_reminder"])

    return reminders


def _format_fail_message(issues):
    """Format technical check failure message."""
    msg = _MESSAGES["fail_header"]
    msg += "\n".join(f"- {i}" for i in issues[:10])
    if len(issues) > 10:
        msg += f"\n- {_MESSAGES['fail_more'].format(n=len(issues) - 10)}"
    return msg


def _format_pass_message(modified_count, deleted_count, warnings=None,
                         knowledge_reminders=None, test_reminders=None,
                         impl_verify_ran=True, km_reminders=None):
    """Format technical check pass message with optional reminders."""
    msg = _MESSAGES["pass_header"].format(modified=modified_count, deleted=deleted_count)
    if not impl_verify_ran:
        msg += "\n\n" + _MESSAGES["impl_verify_reminder"]
    if warnings:
        msg += _MESSAGES["warnings_header"]
        msg += "\n".join(f"- {w}" for w in warnings)
    if knowledge_reminders:
        msg += _MESSAGES["knowledge_header"]
        msg += "\n\n".join(f"- {r}" for r in knowledge_reminders)
    if test_reminders:
        msg += _MESSAGES["tdd_header"]
        msg += "\n".join(f"- {r}" for r in test_reminders)
    if km_reminders:
        msg += _MESSAGES["km_header"]
        msg += "\n".join(f"- {r}" for r in km_reminders)
    return msg


def output_fail(issues):
    """技术检查失败 → 阻止完成"""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny"
        },
        "systemMessage": _format_fail_message(issues)
    }
    print(json.dumps(result, ensure_ascii=False))


def output_pass(modified_count, deleted_count, warnings=None, knowledge_reminders=None,
                test_reminders=None, impl_verify_ran=True, km_reminders=None):
    """技术检查通过 → 放行 + 语义验证提醒 + 编译警告 + 知识文档定向提醒 + TDD 测试覆盖提醒"""
    result = {"systemMessage": _format_pass_message(
        modified_count, deleted_count, warnings, knowledge_reminders, test_reminders,
        impl_verify_ran, km_reminders
    )}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # hook 出错不应阻塞正常工作流
        print(json.dumps({"systemMessage": f"ECW verify-completion hook error: {e}"}))
        sys.exit(0)
