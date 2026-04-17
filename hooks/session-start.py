#!/usr/bin/env python3
"""ECW SessionStart hook — auto-inject workflow context for warm restart.

On each new session, detects and injects:
1. session-state.md — active workflow state (risk level, routing, phase)
2. session-data/ checkpoints — latest checkpoint files summary
3. ecw.yml key config — project name, language, risk level
4. Pending task recovery hint

Output is additionalContext injected into the session system prompt.
"""

import json
import os
import re
import sys
from datetime import datetime


# Maximum lines to include from session-state.md
MAX_STATE_LINES = 60
# Maximum checkpoint files to summarize
MAX_CHECKPOINTS = 5
# Maximum bytes to read from each checkpoint file for summary
CHECKPOINT_PREVIEW_BYTES = 512


def _read_session_state(cwd):
    """Read session-state.md content. Returns (content, path) or (None, None)."""
    candidates = [
        os.path.join(cwd, ".claude", "ecw", "state", "session-state.md"),
        os.path.join(cwd, ".claude", "ecw", "session-state.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if content.strip():
                    return content, path
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
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def _get_checkpoint_files(cwd):
    """List session-data/ checkpoint files sorted by mtime (newest first)."""
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data_dir):
        return []

    files = []
    try:
        for name in os.listdir(session_data_dir):
            full = os.path.join(session_data_dir, name)
            if os.path.isfile(full) and name.endswith(".md"):
                files.append((full, os.path.getmtime(full), name))
    except Exception:
        return []

    files.sort(key=lambda x: x[1], reverse=True)
    return files[:MAX_CHECKPOINTS]


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


def _read_ecw_config(cwd):
    """Read ecw.yml and extract key config values."""
    try:
        import yaml
    except ImportError:
        return {}

    ecw_yml = os.path.join(cwd, ".claude", "ecw", "ecw.yml")
    if not os.path.exists(ecw_yml):
        return {}
    try:
        with open(ecw_yml, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return {
            "project_name": cfg.get("project", {}).get("name", ""),
            "language": cfg.get("project", {}).get("language", ""),
        }
    except Exception:
        return {}


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


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        print(json.dumps({"result": "continue"}))
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
    ecw_cfg = _read_ecw_config(cwd)
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
        sections.append(
            "# [ECW] Project config\n\n" + "\n".join(cfg_lines)
        )

    # 4. Task recovery hint
    if state_content and state_fields.get("status", "").lower() != "ended":
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
