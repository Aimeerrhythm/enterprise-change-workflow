#!/usr/bin/env python3
"""ECW marker-based idempotent update utilities.

Provides functions for updating specific sections of session-state.md
(and other marker-delimited files) without overwriting unrelated content.

Marker format:
    <!-- ECW:{NAME}:START -->
    ... section content ...
    <!-- ECW:{NAME}:END -->

Standard marker names for session-state.md:
    STATUS  — Current workflow status fields
    STOP    — Stop hook auto-update (timestamp + activity)
"""

import os
import re

import yaml


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


def parse_yaml_section(content, name):
    """Extract marker section and parse as YAML.

    Returns parsed YAML (dict, list, or scalar), or None if:
    - Marker section does not exist
    - YAML parsing fails
    """
    section = read_marker_section(content, name)
    if section is None:
        return None
    try:
        return yaml.safe_load(section)
    except yaml.YAMLError:
        return None


def update_yaml_section(content, name, data):
    """Serialize data as YAML and write into marker section."""
    yaml_str = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    return update_marker_section(content, name, yaml_str)


def parse_status(content):
    """Parse STATUS section as YAML dict. Returns dict or None."""
    result = parse_yaml_section(content, "STATUS")
    if result is None or not isinstance(result, dict):
        return None
    return result




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


def update_status_fields(content, fields):
    """Update specific fields within the STATUS marker block.

    Args:
        content: Full file content.
        fields: Dict mapping field names (snake_case YAML keys) to new values.

    Returns:
        Updated file content.
    """
    status = parse_status(content)
    if status is None:
        return content

    status.update(fields)
    return update_yaml_section(content, "STATUS", status)




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


def parse_instincts(cwd, skill_name=None, min_confidence=0.0):
    """Parse instincts.md and return entries, optionally filtered by skill and confidence.

    Unified implementation for both auto-continue (per-skill injection) and
    session-start (global high-confidence injection). Issue #62 Part 4.

    Args:
        cwd: Project working directory.
        skill_name: If provided (e.g. "ecw:tdd"), only return instincts from
            that skill's section. If None, return all instincts across sections.
        min_confidence: Minimum confidence threshold (0.0-1.0). Entries below
            this are excluded. session-start uses 0.7; auto-continue uses 0.0.

    Returns:
        List of dicts with keys: pattern, action, confidence, source, skill.
        Empty list if file not found or no matching entries.
    """
    instincts_path = os.path.join(cwd, ".claude", "ecw", "state", "instincts.md")
    if not os.path.exists(instincts_path):
        return []
    try:
        with open(instincts_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []

    if not content.strip():
        return []

    skill_key = None
    if skill_name:
        skill_key = skill_name.replace("ecw:", "") if skill_name.startswith("ecw:") else skill_name

    results = []

    # Parse multi-section format: ## skill-key\n<!-- INSTINCT -->\n...
    sections = re.split(r'\n##\s+', content)
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        section_skill = lines[0].strip().lower()

        # Filter by skill if requested
        if skill_key and section_skill != skill_key.lower():
            continue

        # Skip "no instincts yet" sections
        section_body = "\n".join(lines[1:])
        if "no instincts yet" in section_body.lower():
            continue

        # Extract individual instinct entries using <!-- INSTINCT --> markers
        blocks = section_body.split("<!-- INSTINCT -->")
        for block in blocks[1:]:
            entry = {"skill": section_skill}
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("- **Pattern**:"):
                    entry["pattern"] = line.split(":", 1)[1].strip()
                elif line.startswith("- **Action**:"):
                    entry["action"] = line.split(":", 1)[1].strip()
                elif line.startswith("- **Confidence**:"):
                    try:
                        entry["confidence"] = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        entry["confidence"] = 0.0
                elif line.startswith("- **Source**:"):
                    entry["source"] = line.split(":", 1)[1].strip()

            if not entry.get("pattern") or not entry.get("action"):
                continue
            if entry.get("confidence", 0.0) < min_confidence:
                continue
            results.append(entry)

    return results


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
        # workflow_id="" means files live directly in session-data/ (legacy)
        if workflow_id:
            self._dir = os.path.join(
                cwd, ".claude", "ecw", "session-data", workflow_id
            )
        else:
            self._dir = os.path.join(cwd, ".claude", "ecw", "session-data")

    @classmethod
    def from_latest_workflow(cls, cwd: str) -> "CheckpointStore | None":
        """Return a store pointing to the most recent workflow-id subdirectory.

        Falls back to the root session-data/ directory for backward compat
        when no subdirectories exist but root .md files are present.
        Returns None if session-data directory does not exist.
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
            # Backward compat: fall back to root session-data/ files
            return cls(cwd, "")
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

    def list(self, return_paths: bool = False) -> "list[str]":
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
