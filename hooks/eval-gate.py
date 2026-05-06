#!/usr/bin/env python3
"""ECW eval gate hook — SKILL.md 变更时自动运行 eval-quick，确保路由决策正确。

PreToolUse 拦截 TaskUpdate(status=completed)：
1. 检测变更文件中是否有 skills/*/SKILL.md 或 workflow-routes.yml
2. 若有，检查 eval-cleared.stamp 是否存在且比变更文件新
3. stamp 新鲜 → 放行
4. stamp 缺失/过时 → 自动运行 eval-quick
   - 通过 → 放行，systemMessage 注入结果摘要
   - 失败 → block，注入失败详情
   - 超时 → remind，不 block（工具问题不阻断工作流）
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

STAMP_RELPATH = ".claude/ecw/state/eval-cleared.stamp"
LOG_RELPATH = ".claude/ecw/state/eval-last-run.log"
EVAL_TIMEOUT = 240  # seconds, under the 300s hook timeout


def _get_plugin_root() -> str:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root and os.path.isdir(env_root):
        return env_root
    return str(Path(__file__).parent.parent)


def _is_skill_file(filepath: str) -> bool:
    normalized = filepath.replace(os.sep, "/")
    if normalized.startswith("skills/") and normalized.endswith("SKILL.md"):
        return True
    if normalized == "skills/risk-classifier/workflow-routes.yml":
        return True
    return False


def get_changed_skill_files(plugin_root: str) -> list[str]:
    """Git diff HEAD in plugin_root, filter to skill-related files."""
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
            capture_output=True, text=True, cwd=plugin_root, timeout=5,
        )
        files = [f for f in r.stdout.strip().split("\n") if f]
        return [f for f in files if _is_skill_file(f)]
    except Exception:
        return []


def stamp_is_fresh(plugin_root: str, skill_files: list[str]) -> bool:
    """stamp 存在且比所有变更 skill 文件新时返回 True。"""
    stamp_path = os.path.join(plugin_root, STAMP_RELPATH)
    if not os.path.exists(stamp_path):
        return False
    stamp_mtime = os.path.getmtime(stamp_path)
    for f in skill_files:
        full = os.path.join(plugin_root, f)
        if os.path.exists(full) and os.path.getmtime(full) > stamp_mtime:
            return False
    return True


def run_eval(plugin_root: str) -> tuple[Optional[bool], str]:
    """运行 make eval-quick，返回 (passed, output)。passed=None 表示超时。"""
    tests_dir = os.path.join(plugin_root, "tests")
    log_path = os.path.join(plugin_root, LOG_RELPATH)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    try:
        result = subprocess.run(
            ["make", "eval-quick"],
            capture_output=True, text=True,
            cwd=tests_dir, timeout=EVAL_TIMEOUT,
        )
        output = result.stdout + result.stderr
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n{output}")
        return result.returncode == 0, output

    except subprocess.TimeoutExpired:
        msg = f"eval-quick 超时（>{EVAL_TIMEOUT}s）"
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] TIMEOUT\n{msg}")
        return None, msg

    except Exception as e:
        return None, str(e)


def _failure_summary(output: str) -> str:
    """从 promptfoo 输出中提取关键失败行。"""
    keywords = ("fail", "✗", "error", "assert")
    lines = [
        l for l in output.split("\n")
        if any(k in l.lower() for k in keywords)
    ][:10]
    if lines:
        return "\n".join(lines)
    return output[-500:] if len(output) > 500 else output


def check(input_data: dict) -> tuple[str, str]:
    """返回 (action, message)，action 为 'block' 或 'continue'。"""
    if input_data.get("tool_name") != "TaskUpdate":
        return "continue", ""
    if input_data.get("tool_input", {}).get("status") != "completed":
        return "continue", ""

    plugin_root = _get_plugin_root()
    skill_files = get_changed_skill_files(plugin_root)
    if not skill_files:
        return "continue", ""

    if stamp_is_fresh(plugin_root, skill_files):
        return "continue", ""

    changed_list = ", ".join(f"`{f}`" for f in skill_files)
    log_path = LOG_RELPATH

    passed, output = run_eval(plugin_root)

    if passed is None:
        return "continue", (
            f"**[ECW Eval Gate]** eval-quick 超时（>{EVAL_TIMEOUT}s），路由决策未验证。\n"
            f"变更文件：{changed_list}\n"
            f"请手动运行 `make -C tests eval-quick` 确认。"
        )

    if passed:
        return "continue", (
            f"**[ECW Eval Gate]** eval-quick 通过，路由决策验证完成。\n"
            f"变更文件：{changed_list}"
        )

    summary = _failure_summary(output)
    return "block", (
        f"**[ECW Eval Gate]** eval-quick 失败，路由决策验证未通过。\n"
        f"变更文件：{changed_list}\n\n"
        f"失败详情（完整日志：`{log_path}`）：\n"
        f"```\n{summary}\n```\n\n"
        f"请修复 SKILL.md 后重新运行 `make -C tests eval-quick`。"
    )


def main() -> None:
    input_data = json.load(sys.stdin)

    if input_data.get("tool_name") != "TaskUpdate":
        sys.exit(0)
    if input_data.get("tool_input", {}).get("status") != "completed":
        sys.exit(0)

    action, message = check(input_data)

    if action == "block":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
            },
            "systemMessage": message,
        }, ensure_ascii=False))
        sys.exit(2)
    else:
        if message:
            print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"systemMessage": f"ECW eval-gate hook error: {e}"}))
        sys.exit(0)
