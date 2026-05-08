#!/usr/bin/env python3
"""ECW session state utilities.

Provides functions for reading and writing session-state.json — the single
source of truth for workflow routing state.

Session state schema (all fields optional except risk_level):
    {
        "risk_level": "P0"|"P1"|"P2"|"P3",
        "current_phase": str,
        "routing": [str, ...],
        "next": str,
        "auto_continue": bool,
        "baseline_commit": str
    }
"""

import json
import os


def find_session_state(cwd):
    """Find session-state.json file. Returns path or None."""
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if os.path.isdir(session_data_dir):
        try:
            subdirs = sorted(
                [d for d in os.listdir(session_data_dir)
                 if os.path.isdir(os.path.join(session_data_dir, d))],
                reverse=True,
            )
            for d in subdirs:
                candidate = os.path.join(session_data_dir, d, "session-state.json")
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass
    return None


def _read_json(path):
    """Read and parse a JSON state file. Returns dict or None."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _write_json(path, data):
    """Write dict to JSON state file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def parse_status(state_path):
    """Parse session-state.json at state_path. Returns dict or None."""
    if isinstance(state_path, str) and os.path.isfile(state_path):
        return _read_json(state_path)
    return None


def update_status_fields(state_path, fields):
    """Merge fields into session-state.json. Returns updated dict."""
    data = _read_json(state_path) or {}
    data.update(fields)
    _write_json(state_path, data)
    return data


def validate_status(fields):
    """Validate STATUS fields against schema. Returns error list (empty = valid)."""
    errors = []

    for f in ("risk_level", "routing", "current_phase", "auto_continue"):
        if f not in fields:
            errors.append(f"missing required field: {f}")

    rl = fields.get("risk_level", "")
    if rl and rl not in ("P0", "P1", "P2", "P3"):
        errors.append(f"risk_level invalid: '{rl}' (expected P0-P3)")

    if "routing" in fields and not isinstance(fields["routing"], list):
        errors.append("routing must be a list")

    if "auto_continue" in fields and not isinstance(fields["auto_continue"], bool):
        errors.append("auto_continue must be boolean")

    if "domains" in fields and not isinstance(fields["domains"], list):
        errors.append("domains must be a list")

    return errors


def read_session_state(cwd):
    """Find and read session state. Returns (dict, path) or (None, None)."""
    state_path = find_session_state(cwd)
    if not state_path:
        return None, None
    return _read_json(state_path), state_path


def write_session_state(state_path, data):
    """Write session state dict to JSON file."""
    _write_json(state_path, data)


class CheckpointStore:
    """Unified read/write/exists/list API for ECW session-data checkpoint files."""

    def __init__(self, cwd: str, workflow_id: str) -> None:
        self.cwd = cwd
        self.workflow_id = workflow_id
        if workflow_id:
            self._dir = os.path.join(
                cwd, ".claude", "ecw", "session-data", workflow_id
            )
        else:
            self._dir = os.path.join(cwd, ".claude", "ecw", "session-data")

    @classmethod
    def from_latest_workflow(cls, cwd: str) -> "CheckpointStore | None":
        """Return a store pointing to the most recent workflow-id subdirectory."""
        session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
        if not os.path.isdir(session_data_dir):
            return None
        try:
            subdirs = [
                d for d in os.listdir(session_data_dir)
                if os.path.isdir(os.path.join(session_data_dir, d))
            ]
        except Exception:
            return None
        if not subdirs:
            return cls(cwd, "")
        latest = sorted(subdirs, reverse=True)[0]
        return cls(cwd, latest)

    def path(self, name: str) -> str:
        """Return absolute path for a checkpoint file (.md extension)."""
        filename = name if name.endswith(".md") else f"{name}.md"
        return os.path.join(self._dir, filename)

    def exists(self, name: str) -> bool:
        return os.path.isfile(self.path(name))

    def read(self, name: str) -> "str | None":
        p = self.path(name)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return None

    def write(self, name: str, content: str) -> bool:
        p = self.path(name)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    def list(self, return_paths: bool = False) -> "list[str]":
        if not os.path.isdir(self._dir):
            return []
        try:
            result = []
            for fname in sorted(os.listdir(self._dir)):
                if fname.endswith(".md") or fname.endswith(".json"):
                    full = os.path.join(self._dir, fname)
                    if os.path.isfile(full):
                        stem = fname.rsplit(".", 1)[0]
                        result.append(full if return_paths else stem)
            return result
        except Exception:
            return []
