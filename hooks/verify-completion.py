#!/usr/bin/env python3
"""ECW 完成验证 hook — 对本次任务的实现结果进行技术检查。

PreToolUse 拦截 TaskUpdate(status=completed)：
1. 检查本次修改的文件中是否有断裂引用
2. 检查被删除的文件是否还被其他文件引用
3. Java 编译检查（改了 .java 文件 → mvn compile，失败则阻止）
4. 知识文档同步提醒（业务代码改了但对应域知识文档没动 → 定向提醒）
技术检查 1-3 失败 → 阻止完成；通过 → 放行 + 注入语义验证提醒 + 知识文档定向提醒。
"""

import glob as globmod
import json
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    yaml = None


def main():
    input_data = json.load(sys.stdin)

    # 只拦截 TaskUpdate(status=completed)
    if input_data.get("tool_name") != "TaskUpdate":
        sys.exit(0)
    tool_input = input_data.get("tool_input", {})
    if tool_input.get("status") != "completed":
        sys.exit(0)

    cwd = input_data.get("cwd", "")
    if not cwd:
        sys.exit(0)

    issues = []

    # ── 获取本次变更的文件列表 ──
    modified, deleted = get_changed_files(cwd)

    # 没有变更文件时跳过技术检查，只做语义提醒
    if not modified and not deleted:
        output_pass(0, 0)
        sys.exit(0)

    # ── 技术检查 1: 修改的文件中是否有断裂引用 ──
    for filepath in modified:
        broken = check_broken_references(cwd, filepath)
        issues.extend(broken)

    # ── 技术检查 2: 被删除的文件是否还被引用 ──
    for filepath in deleted:
        stale = check_stale_references(cwd, filepath)
        issues.extend(stale)

    # ── 技术检查 3: Java 编译 ──
    compile_issues = check_java_compilation(cwd, modified)
    issues.extend(compile_issues)

    # ── 知识文档同步提醒（非阻止性） ──
    reminders = check_knowledge_doc_freshness(cwd, modified)

    # ── 输出结果 ──
    if issues:
        output_fail(issues)
        sys.exit(2)
    else:
        output_pass(len(modified), len(deleted), reminders)
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

    try:
        with open(full_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # 匹配 .claude/ 开头的文件路径引用（带扩展名）
        for ref in re.findall(r"\.claude/[\w\-/]+\.[\w]+", content):
            if not os.path.exists(os.path.join(cwd, ref)):
                issues.append(f"`{filepath}` 引用了不存在的路径: `{ref}`")

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
                f"`{ref_file}` 仍引用已删除的文件 `{deleted_file}`"
            )
    except Exception:
        pass

    return issues


def check_java_compilation(cwd, modified):
    """如果本次改了 .java 文件，执行 mvn compile 检查编译。失败 → 返回 issues（deny）。"""
    java_files = [f for f in modified if f.endswith(".java")]
    if not java_files:
        return []

    if not os.path.exists(os.path.join(cwd, "pom.xml")):
        return []

    try:
        r = subprocess.run(
            ["mvn", "compile", "-q", "-T", "1C"],
            capture_output=True, text=True, cwd=cwd, timeout=120
        )
        if r.returncode != 0:
            errors = [l for l in r.stdout.split("\n") + r.stderr.split("\n")
                      if "[ERROR]" in l][:5]
            return ["Java 编译失败:\n" + "\n".join(errors)]
    except subprocess.TimeoutExpired:
        return ["Java 编译超时（>120s），请手动执行 `mvn compile` 检查"]
    except FileNotFoundError:
        return []  # mvn 不在 PATH 中，跳过

    return []


def check_knowledge_doc_freshness(cwd, modified):
    """检查业务代码变更是否需要同步更新知识文档。返回定向提醒列表（不阻止完成）。"""
    reminders = []

    # 读取 ecw.yml 获取 knowledge_root 路径
    knowledge_root = ".claude/knowledge/"
    ecw_yml = os.path.join(cwd, ".claude", "ecw", "ecw.yml")
    if os.path.exists(ecw_yml) and yaml:
        try:
            with open(ecw_yml, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            knowledge_root = cfg.get("paths", {}).get("knowledge_root", knowledge_root)
        except Exception:
            pass

    # 确保 knowledge_root 末尾有 /
    if not knowledge_root.endswith("/"):
        knowledge_root += "/"

    knowledge_abs = os.path.join(cwd, knowledge_root)
    if not os.path.isdir(knowledge_abs):
        return reminders

    # 扫描受影响的域：从 modified 文件中提取
    biz_domains_changed = set()
    knowledge_domains_changed = set()

    for f in modified:
        # 启发式匹配业务代码路径
        m = re.search(r'/biz/(\w+)/', f)
        if m:
            biz_domains_changed.add(m.group(1))
        # 也匹配 /service/ 路径
        m = re.search(r'/service/(\w+)/', f)
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
            f"域 `{domain}` 的业务代码有变更，但知识文档未更新。"
            f"请检查以下文档是否需要同步：\n{file_list}"
        )

    return reminders


def output_fail(issues):
    """技术检查失败 → 阻止完成"""
    msg = "**【ECW 完成验证】实现结果存在技术问题，请修复后重试：**\n\n"
    msg += "\n".join(f"- {i}" for i in issues[:10])
    if len(issues) > 10:
        msg += f"\n- ...还有 {len(issues) - 10} 个问题"

    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny"
        },
        "systemMessage": msg
    }
    print(json.dumps(result, ensure_ascii=False))


def output_pass(modified_count, deleted_count, reminders=None):
    """技术检查通过 → 放行 + 语义验证提醒 + 知识文档定向提醒"""
    msg = (
        f"**【ECW 完成验证】** 技术检查通过"
        f"（{modified_count} 个修改文件、{deleted_count} 个删除文件，无断裂引用）。\n\n"
        "请确认你已完成语义验证：\n"
        "1. **需求对标** — 原始需求的每一项是否都已实现？\n"
        "2. **产出验证** — 改动的代码/文档内容是否正确完整？\n"
        "3. **残留检查** — 有没有该删未删、该同步未同步的文件？"
    )

    if reminders:
        msg += "\n\n---\n\n**【知识文档同步提醒】** 以下域的业务代码有变更，请确认知识文档是否需要同步更新：\n\n"
        msg += "\n\n".join(f"- {r}" for r in reminders)

    result = {"systemMessage": msg}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # hook 出错不应阻塞正常工作流
        print(json.dumps({"systemMessage": f"ECW verify-completion hook error: {e}"}))
        sys.exit(0)
