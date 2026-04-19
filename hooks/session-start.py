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
from marker_utils import find_session_state  # noqa: E402
from ecw_config import read_ecw_config as _read_full_ecw_config  # noqa: E402


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
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def _get_checkpoint_files(cwd):
    """List session-data/ checkpoint files sorted by mtime (newest first).

    Supports workflow-id subdirectories (D-3 isolation): scans the most recent
    subdirectory first. Falls back to root session-data/ for backward compat.
    """
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if not os.path.isdir(session_data_dir):
        return []

    files = []
    try:
        # Check for workflow-id subdirectories first
        subdirs = []
        root_files = []
        for name in os.listdir(session_data_dir):
            full = os.path.join(session_data_dir, name)
            if os.path.isdir(full):
                subdirs.append((full, os.path.getmtime(full), name))
            elif os.path.isfile(full) and name.endswith(".md"):
                root_files.append((full, os.path.getmtime(full), name))

        if subdirs:
            # Use the most recent subdirectory
            subdirs.sort(key=lambda x: x[1], reverse=True)
            latest_dir = subdirs[0][0]
            subdir_name = subdirs[0][2]
            for name in os.listdir(latest_dir):
                full = os.path.join(latest_dir, name)
                if os.path.isfile(full) and name.endswith(".md"):
                    files.append((full, os.path.getmtime(full), name))
        else:
            # Backward compat: scan root session-data/
            files = root_files
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


def _get_project_info(cwd):
    """Read ecw.yml and extract key project info."""
    cfg = _read_full_ecw_config(cwd)
    return {
        "project_name": cfg.get("project", {}).get("name", ""),
        "language": cfg.get("project", {}).get("language", ""),
    }


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
