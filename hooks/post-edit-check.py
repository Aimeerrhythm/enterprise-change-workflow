#!/usr/bin/env python3
"""ECW PostToolUse quality gate — immediate feedback after Edit/Write operations.

Runs after each Edit or Write tool call to:
1. Detect common anti-patterns in the changed content
2. Warn about protected path modifications

Anti-pattern detection is lightweight (regex-based) to keep latency minimal.
Findings are surfaced as systemMessage warnings, never blocking.
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_logger import log_trace  # noqa: E402

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ── User-visible messages (locale: zh-CN) ──
# All user-facing strings are collected here for future i18n.

_MESSAGES = {
    "empty_catch": "空 catch 块 — 异常被吞没，考虑至少记录日志",
    "hardcoded_secret": "疑似硬编码凭据 — 应使用环境变量或配置中心",
    "aws_key": "疑似 AWS Access Key — 不应提交到代码仓库",
    "private_key": "私钥内容 — 不应提交到代码仓库",
    "todo_comment": "新增 TODO/FIXME 注释 — 确认是否需要创建跟踪任务",
    "quality_gate_header": "**[ECW Quality Gate]** 编辑后检测到以下注意事项：\n\n",
    "more_items": "...还有 {n} 项",
}

# ── Anti-pattern definitions ──
# (pattern, description, file_extensions_to_check)

ANTI_PATTERNS = [
    # Empty catch blocks (Java/JS/TS)
    (
        r'catch\s*\([^)]*\)\s*\{\s*\}',
        _MESSAGES["empty_catch"],
        {".java", ".js", ".ts", ".jsx", ".tsx"},
    ),
    # Hardcoded secrets
    (
        r'(?:password|passwd|secret|api_key|apikey|token|access_key)\s*[=:]\s*["\'][^"\']{8,}["\']',
        _MESSAGES["hardcoded_secret"],
        None,  # Check all file types
    ),
    # AWS access keys
    (
        r'(?:AKIA|ASIA)[A-Z0-9]{16}',
        _MESSAGES["aws_key"],
        None,
    ),
    # Private keys
    (
        r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
        _MESSAGES["private_key"],
        None,
    ),
    # TODO/FIXME/HACK comments (informational, not warning)
    (
        r'(?://|#)\s*(?:TODO|FIXME|HACK|XXX)\b',
        _MESSAGES["todo_comment"],
        None,
    ),
]

# File extensions for anti-pattern scanning (skip binaries, images, etc.)
SCANNABLE_EXTENSIONS = {
    ".java", ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".rb", ".php", ".cs", ".kt", ".scala", ".swift",
    ".yml", ".yaml", ".json", ".xml", ".properties", ".env",
    ".md", ".txt", ".sql", ".sh", ".bash",
}



def _find_git_root(path):
    """Walk up from path until a .git directory is found. Returns the directory or None."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _inject_baseline_commit(filepath, cwd):  # noqa: ARG001 — cwd kept for signature compat
    """If session-state.json was just written with baseline_commit: TBD, replace with actual HEAD hash.

    Resolves the git root from filepath (not from cwd, which points to the plugin install dir).
    No-op if file doesn't match, git fails, or hash already present.
    """
    if not filepath.endswith("session-state.json"):
        return
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return

    if '"baseline_commit"' not in content and "'baseline_commit'" not in content:
        return
    if not re.search(r'"baseline_commit"\s*:\s*"TBD"', content):
        return

    git_root = _find_git_root(filepath)
    if git_root is None:
        return

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return
        commit_hash = result.stdout.strip()
        if not re.fullmatch(r'[0-9a-f]{7,40}', commit_hash):
            return
    except Exception:
        return

    updated = re.sub(
        r'("baseline_commit"\s*:\s*)"TBD"',
        rf'\g<1>"{commit_hash}"',
        content,
    )
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception:
        pass


def _get_file_extension(filepath):
    """Extract file extension, lowercased."""
    _, ext = os.path.splitext(filepath)
    return ext.lower()



def _validate_session_state_yaml(tool_input, tool_name, filepath=""):
    """Validate session-state.json format after edit.

    Returns a list of error strings (empty = all valid).
    """
    if not filepath or not filepath.endswith(".json"):
        return []

    if tool_name == "Write":
        content = tool_input.get("content", "")
    else:
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []
    if not content:
        return []
    try:
        import json as _json
        _json.loads(content)
    except Exception as e:
        return [f"session-state.json: invalid JSON — {e}"]
    return []


def _scan_anti_patterns(content, filepath):
    """Scan content for anti-patterns. Returns list of warning strings."""
    warnings = []
    ext = _get_file_extension(filepath)

    for pattern, description, applicable_exts in ANTI_PATTERNS:
        if applicable_exts is not None and ext not in applicable_exts:
            continue
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            warnings.append(f"`{filepath}`: {description}")

    return warnings


def check(input_data, config=None):
    """PostToolUse sub-hook entry point.

    Args:
        input_data: Hook input dict with tool_name, tool_input, tool_result, cwd

    Returns:
        (action, message) tuple — always "continue" (PostToolUse cannot block)
    """
    cwd = input_data.get("cwd", "")
    if not cwd:
        return ("continue", "")

    from ecw_config import is_ecw_project
    if not is_ecw_project(cwd):
        return ("continue", "")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # Extract the file path from Edit or Write tool input
    filepath = tool_input.get("file_path", "")
    if not filepath:
        return ("continue", "")

    # Convert absolute path to relative for display and state tracking
    if filepath.startswith(cwd):
        rel_path = os.path.relpath(filepath, cwd)
    else:
        rel_path = filepath

    # 1. Auto-fill baseline_commit placeholder in new session-state.json files
    if tool_name == "Write":
        _inject_baseline_commit(filepath, cwd)

    # 1c. JSON validity check for session-state.json
    if filepath.endswith("session-state.json"):
        json_warnings = _validate_session_state_yaml(tool_input, tool_name, filepath)
        if json_warnings:
            log_trace(cwd, "post-edit-check", "PostToolUse",
                      file=rel_path, warnings=["json_invalid"])
            msg = "**[ECW JSON Error]** session-state.json 包含无效 JSON，请立即修正：\n\n"
            msg += "\n".join(f"- {w}" for w in json_warnings)
            return ("continue", msg)

    # 2. Scan for anti-patterns (only for scannable file types)
    ext = _get_file_extension(filepath)
    if ext not in SCANNABLE_EXTENSIONS:
        return ("continue", "")

    warnings = []

    if tool_name == "Write":
        # For Write, scan the full content being written
        content = tool_input.get("content", "")
        if content:
            warnings = _scan_anti_patterns(content, rel_path)
    elif tool_name == "Edit":
        # For Edit, scan only the new_string being inserted
        new_string = tool_input.get("new_string", "")
        if new_string:
            warnings = _scan_anti_patterns(new_string, rel_path)

    if not warnings:
        return ("continue", "")

    # Summarize warning types for trace (not the full text)
    warning_types = []
    for w in warnings:
        if "catch" in w:
            warning_types.append("empty_catch")
        elif "凭据" in w or "secret" in w.lower():
            warning_types.append("hardcoded_secret")
        elif "AWS" in w:
            warning_types.append("aws_key")
        elif "私钥" in w or "PRIVATE KEY" in w:
            warning_types.append("private_key")
        elif "TODO" in w or "FIXME" in w:
            warning_types.append("todo_comment")
        else:
            warning_types.append("other")
    log_trace(cwd, "post-edit-check", "PostToolUse",
              file=rel_path, warnings=warning_types)

    msg = _MESSAGES["quality_gate_header"]
    msg += "\n".join(f"- {w}" for w in warnings[:5])
    if len(warnings) > 5:
        msg += f"\n- {_MESSAGES['more_items'].format(n=len(warnings) - 5)}"

    return ("continue", msg)


def main():
    """Standalone entry point for PostToolUse hook."""
    input_data = json.load(sys.stdin)

    cwd = input_data.get("cwd", "")
    if not cwd or not os.path.isfile(os.path.join(cwd, ".claude", "ecw", "ecw.yml")):
        print(json.dumps({"result": "continue"}))
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        print(json.dumps({"result": "continue"}))
        sys.exit(0)

    action, message = check(input_data)

    if message:
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
    else:
        print(json.dumps({"result": "continue"}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # PostToolUse hook errors must not block workflow
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
