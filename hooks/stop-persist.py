#!/usr/bin/env python3
"""ECW Stop hook — context health advisory on phase transitions.

Runs after every assistant response to:
1. Detect phase transitions → check context health → write advisory file
2. Never block normal workflow — all errors are swallowed

Input (stdin JSON):
  - stop_hook_active: bool
  - tool_calls: list of {tool_name, ...} from this response
  - cwd: working directory
"""

import glob
import json
import os
import sys

# Import shared marker utilities (same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_utils import find_session_state, parse_status  # noqa: E402

MAX_CONTEXT = 200_000
ADVISORY_FILE = ".claude/ecw/state/context-health.txt"
PHASE_CACHE_FILE = ".claude/ecw/state/.last-phase"


def _extract_current_phase(content):
    """Extract current_phase from session-state JSON string."""
    try:
        return json.loads(content).get("current_phase") or None
    except Exception:
        return None


def _check_context_health(cwd):
    """Check context window usage from session JSONL. Returns (level, pct)."""
    try:
        project_key = cwd.replace("/", "-")
        session_dir = os.path.expanduser(f"~/.claude/projects/{project_key}")
        if not os.path.isdir(session_dir):
            return None, 0

        files = glob.glob(os.path.join(session_dir, "*.jsonl"))
        if not files:
            return None, 0

        latest = max(files, key=os.path.getmtime)
        last_usage = None
        with open(latest, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("type") == "assistant":
                    usage = obj.get("message", {}).get("usage", {})
                    if usage:
                        last_usage = usage

        if not last_usage:
            return None, 0

        total = (
            last_usage.get("input_tokens", 0)
            + last_usage.get("cache_creation_input_tokens", 0)
            + last_usage.get("cache_read_input_tokens", 0)
        )
        pct = (total / MAX_CONTEXT) * 100

        if pct > 70:
            return "HIGH", pct
        elif pct > 50:
            return "MEDIUM", pct
        else:
            return "LOW", pct
    except Exception:
        return None, 0


def _update_context_advisory(cwd, state_content):
    """Detect phase transition → check context health → write advisory."""
    try:
        current_phase = _extract_current_phase(state_content)
        if not current_phase:
            return

        # Read cached last phase
        cache_path = os.path.join(cwd, PHASE_CACHE_FILE)
        last_phase = None
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                last_phase = f.read().strip()

        # Write current phase to cache
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(current_phase)

        advisory_path = os.path.join(cwd, ADVISORY_FILE)

        if current_phase != last_phase and last_phase is not None:
            # Phase transition detected — check context health
            level, pct = _check_context_health(cwd)
            if level == "HIGH":
                with open(advisory_path, "w", encoding="utf-8") as f:
                    f.write(f"HIGH|{pct:.0f}%|{current_phase}")
            else:
                # Not high — clear advisory
                if os.path.exists(advisory_path):
                    os.remove(advisory_path)
        # No phase change — don't touch advisory file
    except Exception:
        pass  # Never block


def _is_ecw_project(cwd):
    return bool(cwd) and os.path.isfile(os.path.join(cwd, ".claude", "ecw", "ecw.yml"))


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not _is_ecw_project(cwd):
        print(json.dumps({"result": "continue"}))
        return

    # Skip when no tool calls — pure text responses don't represent real progress
    # and checking phase on every turn creates noise (Issue #21).
    tool_calls = input_data.get("tool_calls", [])
    if not tool_calls:
        print(json.dumps({"result": "continue"}))
        return

    state_path = find_session_state(cwd)
    if not state_path:
        print(json.dumps({"result": "continue"}))
        return

    try:
        data = parse_status(state_path) or {}
        if data.get("session_status", "").startswith("ended"):
            print(json.dumps({"result": "continue"}))
            return
        _update_context_advisory(cwd, json.dumps(data))
    except Exception:
        pass  # Stop hook errors must never block workflow

    print(json.dumps({"result": "continue"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Absolute safety — never block
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
