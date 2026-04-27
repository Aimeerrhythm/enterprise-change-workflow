#!/usr/bin/env python3
"""ECW SessionStart hook — auto-inject workflow context for warm restart.

On each new session, detects and injects:
1. session-state.md — active workflow state (risk level, routing, phase)
2. session-data/ checkpoints — latest checkpoint files summary
3. ecw.yml key config — project name, language, risk level
4. Pending task recovery hint
5. High-confidence instincts from Phase 3 calibration

Output is additionalContext injected into the session system prompt.
"""

import json
import os
import re
import sys
from datetime import datetime

# Import shared utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state, CheckpointStore  # noqa: E402
from ecw_config import read_ecw_config as _read_full_ecw_config  # noqa: E402
from ecw_config import read_plugin_version as _read_plugin_version  # noqa: E402


# Maximum lines to include from session-state.md
MAX_STATE_LINES = 60
# Maximum checkpoint files to summarize
MAX_CHECKPOINTS = 5
# Maximum bytes to read from each checkpoint file for summary
CHECKPOINT_PREVIEW_BYTES = 512


def _read_session_state(cwd):
    """Read session-state.md content. Returns (content, path) or (None, None)."""
    state_path = find_session_state(cwd)
    if not state_path:
        return None, None
    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if content.strip():
            return content, state_path
    except Exception:
        pass
    return None, None


def _extract_state_fields(content):
    """Extract key fields from session-state.md content."""
    fields = {}
    patterns = {
        "risk_level": r'\*\*Risk Level\*\*:\s*(P[0-3])',
        "domains": r'\*\*Domains\*\*:\s*(.+)',
        "mode": r'\*\*Mode\*\*:\s*(.+)',
        "routing": r'\*\*Routing\*\*:\s*(.+)',
        "current_phase": r'\*\*Current Phase\*\*:\s*(.+)',
        "status": r'\*\*Status\*\*:\s*(.+)',
        "working_mode": r'\*\*Working Mode\*\*:\s*(.+)',
        "next_skill": r'\*\*Next\*\*:\s*(.+)',
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def _get_checkpoint_files(cwd):
    """List session-data/ checkpoint files sorted by mtime (newest first)."""
    store = CheckpointStore.from_latest_workflow(cwd)
    if store is None:
        return []
    paths = store.list(return_paths=True)
    result = []
    for p in paths:
        try:
            result.append((p, os.path.getmtime(p), os.path.basename(p)))
        except Exception:
            pass
    result.sort(key=lambda x: x[1], reverse=True)
    return result[:MAX_CHECKPOINTS]


def _summarize_checkpoint(filepath, name):
    """Read first N bytes of a checkpoint file and return a summary line."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            preview = f.read(CHECKPOINT_PREVIEW_BYTES)
        # Extract the first heading or first non-empty line as description
        for line in preview.splitlines():
            line = line.strip()
            if line and not line.startswith("---"):
                # Remove markdown heading markers
                desc = re.sub(r'^#+\s*', '', line)
                return f"- `{name}` — {desc[:80]}"
        return f"- `{name}`"
    except Exception:
        return f"- `{name}`"


def _get_project_info(cwd):
    """Read ecw.yml and extract key project info."""
    cfg = _read_full_ecw_config(cwd)
    info = {
        "project_name": cfg.get("project", {}).get("name", ""),
        "language": cfg.get("project", {}).get("language", ""),
    }
    models = cfg.get("models", {})
    defaults = models.get("defaults", {})
    overrides = models.get("overrides", {})
    STANDARD_DEFAULTS = {
        "analysis": "opus",
        "planning": "opus",
        "implementation": "sonnet",
        "verification": "sonnet",
        "mechanical": "haiku",
    }
    non_default = {k: v for k, v in defaults.items() if STANDARD_DEFAULTS.get(k) != v}
    if non_default or overrides:
        info["model_config"] = non_default
        if overrides:
            info["model_overrides"] = overrides
    return info


def _check_modified_files(cwd):
    """Check if modified-files.txt exists from a previous session."""
    state_file = os.path.join(cwd, ".claude", "ecw", "state", "modified-files.txt")
    if os.path.exists(state_file):
        try:
            with open(state_file, encoding="utf-8") as f:
                files = [l.strip() for l in f if l.strip()]
            if files:
                return files
        except Exception:
            pass
    return []


# Minimum confidence threshold for instinct injection
INSTINCT_CONFIDENCE_THRESHOLD = 0.7


def _read_instincts(cwd):
    """Read instincts.md and return entries with confidence > threshold.

    Returns a list of dicts with keys: pattern, action, confidence, source.
    """
    candidates = [
        os.path.join(cwd, ".claude", "ecw", "state", "instincts.md"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        instincts = []
        # Split by INSTINCT markers
        blocks = content.split("<!-- INSTINCT -->")
        for block in blocks[1:]:  # skip header before first marker
            entry = {}
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("- **Pattern**:"):
                    entry["pattern"] = line.split(":", 1)[1].strip()
                elif line.startswith("- **Action**:"):
                    entry["action"] = line.split(":", 1)[1].strip()
                elif line.startswith("- **Confidence**:"):
                    try:
                        entry["confidence"] = float(
                            line.split(":", 1)[1].strip()
                        )
                    except ValueError:
                        entry["confidence"] = 0.0
                elif line.startswith("- **Source**:"):
                    entry["source"] = line.split(":", 1)[1].strip()
            if (
                entry.get("pattern")
                and entry.get("action")
                and entry.get("confidence", 0) >= INSTINCT_CONFIDENCE_THRESHOLD
            ):
                instincts.append(entry)
        return instincts
    return []


def _check_version_mismatch(cwd):
    """Compare plugin version vs ecw.yml ecw_version.

    Returns (mismatch: bool, plugin_ver: str, config_ver: str).
    """
    plugin_ver = _read_plugin_version()
    if not plugin_ver:
        return False, "", ""
    cfg = _read_full_ecw_config(cwd)
    if not cfg:
        return False, plugin_ver, ""
    config_ver = cfg.get("ecw_version", "")
    if not config_ver:
        return True, plugin_ver, "(missing)"
    return config_ver != plugin_ver, plugin_ver, config_ver


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        print(json.dumps({"result": "continue"}))
        return

    # 0. Version check — block everything else if mismatch
    mismatch, plugin_ver, config_ver = _check_version_mismatch(cwd)
    if mismatch:
        warning = (
            f"# [ECW] 配置版本不匹配\n\n"
            f"- 插件版本: `{plugin_ver}`\n"
            f"- 项目 ecw.yml 版本: `{config_ver}`\n\n"
            "**必须先执行 `/ecw-upgrade` 同步配置后再处理用户请求。**\n"
            "直接告知用户需要执行升级命令，不要尝试处理其他任何任务。"
        )
        print(json.dumps(
            {"result": "continue", "additionalContext": warning},
            ensure_ascii=False,
        ))
        return

    sections = []

    # 1. Session state
    state_content, state_path = _read_session_state(cwd)
    state_fields = {}
    if state_content:
        state_fields = _extract_state_fields(state_content)

        # Check if session was marked as ended
        status = state_fields.get("status", "").lower()
        if status == "ended":
            # Previous session ended normally — no recovery needed
            pass
        else:
            # Truncate to MAX_STATE_LINES for context budget
            lines = state_content.splitlines()[:MAX_STATE_LINES]
            truncated = "\n".join(lines)
            if len(lines) < len(state_content.splitlines()):
                truncated += "\n... (truncated)"

            rel_path = os.path.relpath(state_path, cwd)
            sections.append(
                f"# [ECW] Active workflow state (`{rel_path}`)\n\n{truncated}"
            )

    # 2. Checkpoint files
    checkpoints = _get_checkpoint_files(cwd)
    if checkpoints:
        summaries = [_summarize_checkpoint(fp, name) for fp, _, name in checkpoints]
        sections.append(
            "# [ECW] Session-data checkpoints (read for full context)\n\n"
            + "\n".join(summaries)
        )

    # 3. ECW project config
    ecw_cfg = _get_project_info(cwd)
    if ecw_cfg.get("project_name") or ecw_cfg.get("language"):
        cfg_lines = []
        if ecw_cfg.get("project_name"):
            cfg_lines.append(f"- Project: {ecw_cfg['project_name']}")
        if ecw_cfg.get("language"):
            cfg_lines.append(f"- Language: {ecw_cfg['language']}")
        if state_fields.get("risk_level"):
            cfg_lines.append(f"- Active risk level: {state_fields['risk_level']}")
        if state_fields.get("working_mode"):
            cfg_lines.append(f"- Working mode: {state_fields['working_mode']}")
        if ecw_cfg.get("model_config"):
            cfg_lines.append(f"- Model config (non-default): {ecw_cfg['model_config']}")
        if ecw_cfg.get("model_overrides"):
            cfg_lines.append(f"- Model overrides: {ecw_cfg['model_overrides']}")
        sections.append(
            "# [ECW] Project config\n\n" + "\n".join(cfg_lines)
        )

    # 4. Task recovery hint
    if state_content and state_fields.get("status", "").lower() != "ended":
        next_skill = state_fields.get("next_skill", "").strip()
        if next_skill and next_skill.lower() not in ('tbd', 'none', 'complete', ''):
            sections.append(
                "# [ECW] Recovery hint\n\n"
                f"An active ECW workflow was detected. Next skill to invoke: `{next_skill}`. "
                "Check TaskList for pending work. If no tasks exist, re-create "
                "them based on the `Post-Implementation Tasks` field in session-state.md."
            )
        else:
            sections.append(
                "# [ECW] Recovery hint\n\n"
                "An active ECW workflow was detected from a previous session. "
                "Check TaskList for pending work. If no tasks exist, re-create "
                "them based on the `Post-Implementation Tasks` field in session-state.md."
            )

    # 5. Modified files from previous session
    prev_modified = _check_modified_files(cwd)
    if prev_modified:
        file_list = "\n".join(f"- `{f}`" for f in prev_modified[:10])
        if len(prev_modified) > 10:
            file_list += f"\n- ...and {len(prev_modified) - 10} more"
        sections.append(
            f"# [ECW] Previously modified files\n\n{file_list}"
        )

    # 6. High-confidence instincts from Phase 3 calibration
    instincts = _read_instincts(cwd)
    if instincts:
        lines = []
        for inst in instincts:
            conf = inst.get("confidence", 0)
            lines.append(
                f"- [{conf:.1f}] {inst['pattern']} → {inst['action']}"
            )
        sections.append(
            "# [ECW] Risk classification instincts (learned from Phase 3)\n\n"
            "These heuristics are derived from past calibration. "
            "Consider them during Phase 1 risk assessment.\n\n"
            + "\n".join(lines)
        )

    if not sections:
        print(json.dumps({"result": "continue"}))
        return

    context = "\n\n---\n\n".join(sections)
    result = {
        "result": "continue",
        "additionalContext": context,
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # SessionStart hook errors must not block session initialization
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
