#!/usr/bin/env python3
"""ECW marker-based idempotent update utilities.

Provides functions for updating specific sections of session-state.md
(and other marker-delimited files) without overwriting unrelated content.

Marker format:
    <!-- ECW:{NAME}:START -->
    ... section content ...
    <!-- ECW:{NAME}:END -->

Standard marker names for session-state.md:
    LEDGER  — Subagent Ledger table
    STATUS  — Current workflow status fields
    MODE    — Working mode declaration
    STOP    — Stop hook auto-update (timestamp + activity)
"""

import os
import re


def make_markers(name):
    """Return (start_marker, end_marker) for a given section name.

    >>> make_markers("LEDGER")
    ('<!-- ECW:LEDGER:START -->', '<!-- ECW:LEDGER:END -->')
    """
    return (f"<!-- ECW:{name}:START -->", f"<!-- ECW:{name}:END -->")


def update_marker_section(content, name, new_inner):
    """Replace the content between markers, or append if markers not found.

    Args:
        content: Full file content.
        name: Marker name (e.g. "LEDGER", "STATUS", "STOP").
        new_inner: New content to place between the start/end markers.
            The markers themselves are added automatically.

    Returns:
        Updated file content with the marker section replaced/appended.
    """
    start, end = make_markers(name)
    new_section = f"{start}\n{new_inner}\n{end}"

    pattern = re.compile(
        re.escape(start) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    if pattern.search(content):
        return pattern.sub(new_section, content)
    else:
        return content.rstrip() + "\n\n" + new_section + "\n"


def read_marker_section(content, name):
    """Extract the content between markers. Returns None if not found.

    Args:
        content: Full file content.
        name: Marker name.

    Returns:
        Inner content (without the marker lines themselves), or None.
    """
    start, end = make_markers(name)
    pattern = re.compile(
        re.escape(start) + r"\n(.*?)\n" + re.escape(end),
        re.DOTALL,
    )
    m = pattern.search(content)
    return m.group(1) if m else None


def find_session_state(cwd):
    """Find session-state.md file. Returns path or None.

    Checks session-data/{workflow-id}/ subdirectories first (most recent),
    then falls back to legacy paths.
    """
    # New convention: session-state.md in session-data/{workflow-id}/
    session_data_dir = os.path.join(cwd, ".claude", "ecw", "session-data")
    if os.path.isdir(session_data_dir):
        try:
            subdirs = sorted(
                [d for d in os.listdir(session_data_dir)
                 if os.path.isdir(os.path.join(session_data_dir, d))],
                reverse=True,
            )
            for d in subdirs:
                candidate = os.path.join(session_data_dir, d, "session-state.md")
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass
    # Legacy fallback
    candidates = [
        os.path.join(cwd, ".claude", "ecw", "session-state.md"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def update_session_state_section(cwd, name, new_inner):
    """Find session-state.md and update a marker section in-place.

    Args:
        cwd: Working directory.
        name: Marker name.
        new_inner: New content for the section.

    Returns:
        True if updated successfully, False otherwise.
    """
    state_path = find_session_state(cwd)
    if not state_path:
        return False

    try:
        with open(state_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        updated = update_marker_section(content, name, new_inner)

        with open(state_path, "w", encoding="utf-8") as f:
            f.write(updated)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Checkpoint file names known to ECW
# ---------------------------------------------------------------------------
CHECKPOINT_NAMES = {
    "session-state",
    "phase2-assessment",
    "knowledge-summary",
    "requirements-summary",
    "domain-collab-report",
    "impl-verify-findings",
    "spec-challenge-report",
    "cross-service-plan",
}


class CheckpointStore:
    """Unified read/write/exists/list API for ECW session-data checkpoint files.

    All checkpoint files live under:
        {cwd}/.claude/ecw/session-data/{workflow_id}/{name}.md

    Usage:
        store = CheckpointStore(cwd, workflow_id)
        # or: store = CheckpointStore.from_latest_workflow(cwd)

        store.write("phase2-assessment", content)
        content = store.read("knowledge-summary")      # None if missing
        store.exists("impl-verify-findings")           # bool
        store.list()                                   # ["session-state", ...]
        store.list(return_paths=True)                  # ["/abs/path/session-state.md", ...]
    """

    def __init__(self, cwd: str, workflow_id: str) -> None:
        self.cwd = cwd
        self.workflow_id = workflow_id
        self._dir = os.path.join(
            cwd, ".claude", "ecw", "session-data", workflow_id
        )

    @classmethod
    def from_latest_workflow(cls, cwd: str) -> "CheckpointStore | None":
        """Return a store pointing to the most recent workflow-id subdirectory.

        Returns None if no session-data directory or no subdirectories exist.
        """
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
            return None
        latest = sorted(subdirs, reverse=True)[0]
        return cls(cwd, latest)

    def path(self, name: str) -> str:
        """Return absolute path for a checkpoint file (always .md extension)."""
        filename = name if name.endswith(".md") else f"{name}.md"
        return os.path.join(self._dir, filename)

    def exists(self, name: str) -> bool:
        """Return True if the checkpoint file exists."""
        return os.path.isfile(self.path(name))

    def read(self, name: str) -> "str | None":
        """Read checkpoint content. Returns None if the file does not exist."""
        p = self.path(name)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return None

    def write(self, name: str, content: str) -> bool:
        """Write content to a checkpoint file. Creates parent dirs as needed.

        Returns True on success, False on failure.
        """
        p = self.path(name)
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    def list(self, return_paths: bool = False) -> list:
        """List checkpoint files in this workflow's session-data directory.

        Args:
            return_paths: If True, return absolute paths; otherwise return
                          stem names (filename without .md extension).

        Returns:
            Sorted list of names or absolute paths for existing .md files.
        """
        if not os.path.isdir(self._dir):
            return []
        try:
            result = []
            for fname in sorted(os.listdir(self._dir)):
                if fname.endswith(".md"):
                    full = os.path.join(self._dir, fname)
                    if os.path.isfile(full):
                        result.append(full if return_paths else fname[:-3])
            return result
        except Exception:
            return []
