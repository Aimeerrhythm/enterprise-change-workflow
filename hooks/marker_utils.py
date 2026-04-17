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

    Checks two candidate locations:
    1. .claude/ecw/state/session-state.md (current)
    2. .claude/ecw/session-state.md (legacy)
    """
    candidates = [
        os.path.join(cwd, ".claude", "ecw", "state", "session-state.md"),
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
