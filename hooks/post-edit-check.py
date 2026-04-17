#!/usr/bin/env python3
"""ECW PostToolUse quality gate — immediate feedback after Edit/Write operations.

Runs after each Edit or Write tool call to:
1. Accumulate modified file list to .claude/ecw/state/modified-files.txt
2. Detect common anti-patterns in the changed content
3. Warn about protected path modifications

Anti-pattern detection is lightweight (regex-based) to keep latency minimal.
Findings are surfaced as systemMessage warnings, never blocking.
"""

import json
import os
import re
import sys


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

# State file for accumulating modified files
MODIFIED_FILES_STATE = ".claude/ecw/state/modified-files.txt"


def _get_file_extension(filepath):
    """Extract file extension, lowercased."""
    _, ext = os.path.splitext(filepath)
    return ext.lower()


def _accumulate_modified_file(cwd, filepath):
    """Append filepath to the modified-files state file (deduped)."""
    state_path = os.path.join(cwd, MODIFIED_FILES_STATE)
    state_dir = os.path.dirname(state_path)

    try:
        os.makedirs(state_dir, exist_ok=True)

        existing = set()
        if os.path.exists(state_path):
            with open(state_path, encoding="utf-8") as f:
                existing = {line.strip() for line in f if line.strip()}

        if filepath not in existing:
            with open(state_path, "a", encoding="utf-8") as f:
                f.write(filepath + "\n")
    except Exception:
        pass  # State tracking is best-effort


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

    # 1. Accumulate modified file
    _accumulate_modified_file(cwd, rel_path)

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

    msg = _MESSAGES["quality_gate_header"]
    msg += "\n".join(f"- {w}" for w in warnings[:5])
    if len(warnings) > 5:
        msg += f"\n- {_MESSAGES['more_items'].format(n=len(warnings) - 5)}"

    return ("continue", msg)


def main():
    """Standalone entry point for PostToolUse hook."""
    input_data = json.load(sys.stdin)

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
