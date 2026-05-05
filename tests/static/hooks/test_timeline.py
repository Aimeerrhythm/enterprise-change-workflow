"""Unit tests for TIMELINE tracking in marker_utils.py

Tests the append_timeline_entry function that:
- Appends new timeline entries with start=now, end=null, duration_s=null
- Backfills the previous entry's end and duration_s when appending
- Handles empty TIMELINE blocks and missing session-state.md
"""
from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def marker_utils():
    """Import marker_utils.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "marker_utils",
        HOOKS_DIR / "marker_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# append_timeline_entry
# ══════════════════════════════════════════════════════

class TestAppendTimelineEntry:
    def test_append_first_entry_to_empty_timeline(self, marker_utils):
        """Appends first entry to empty TIMELINE block."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:TIMELINE:START -->\n"
            "<!-- ECW:TIMELINE:END -->\n"
        )
        result = marker_utils.append_timeline_entry(content, "requirements-elicitation")

        # Should have one entry with start time, null end, null duration
        assert "phase: requirements-elicitation" in result
        assert "start:" in result
        assert "end: null" in result
        assert "duration_s: null" in result

    def test_backfill_previous_entry_when_appending(self, marker_utils):
        """When appending new entry, backfills previous entry's end and duration_s."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:TIMELINE:START -->\n"
            "- phase: requirements-elicitation\n"
            "  start: \"2026-05-05T12:00:00\"\n"
            "  end: null\n"
            "  duration_s: null\n"
            "<!-- ECW:TIMELINE:END -->\n"
        )
        result = marker_utils.append_timeline_entry(content, "writing-plans")

        # Previous entry should have end and duration filled
        assert "phase: requirements-elicitation" in result
        assert 'start: "2026-05-05T12:00:00"' in result or "start: '2026-05-05T12:00:00'" in result
        # end should no longer be null for first entry
        lines = result.split('\n')
        req_section = []
        in_req = False
        for line in lines:
            if 'requirements-elicitation' in line:
                in_req = True
            if in_req:
                req_section.append(line)
                if 'duration_s:' in line:
                    break
        req_text = '\n'.join(req_section)
        # The first entry should NOT have "end: null" anymore
        assert "end: null" not in req_text or req_text.count("end: null") == 0

        # New entry should exist with null end
        assert "phase: writing-plans" in result
        assert result.count("end: null") >= 1  # at least the new entry has null end

    def test_duration_calculation_correct(self, marker_utils):
        """Duration is calculated as integer seconds between start and end."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:TIMELINE:START -->\n"
            "- phase: requirements-elicitation\n"
            "  start: \"2026-05-05T12:00:00\"\n"
            "  end: null\n"
            "  duration_s: null\n"
            "<!-- ECW:TIMELINE:END -->\n"
        )
        result = marker_utils.append_timeline_entry(content, "writing-plans")

        # Extract duration_s value for first entry
        lines = result.split('\n')
        for i, line in enumerate(lines):
            if 'requirements-elicitation' in line:
                # Find duration_s in next few lines
                for j in range(i, min(i+5, len(lines))):
                    if 'duration_s:' in lines[j] and 'null' not in lines[j]:
                        # Should be a positive integer
                        duration_str = lines[j].split('duration_s:')[1].strip()
                        duration = int(duration_str)
                        assert duration >= 0
                        return
        pytest.fail("Could not find non-null duration_s for first entry")

    def test_missing_timeline_block_silent_skip(self, marker_utils):
        """When TIMELINE block doesn't exist, function handles gracefully."""
        content = "# ECW Session State\n<!-- ECW:STATUS:START -->\nrisk_level: P1\n<!-- ECW:STATUS:END -->\n"
        result = marker_utils.append_timeline_entry(content, "requirements-elicitation")

        # Should create TIMELINE block
        assert "<!-- ECW:TIMELINE:START -->" in result
        assert "<!-- ECW:TIMELINE:END -->" in result
        assert "phase: requirements-elicitation" in result

    def test_multiple_entries_accumulate(self, marker_utils):
        """Multiple consecutive appends accumulate correctly."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:TIMELINE:START -->\n"
            "<!-- ECW:TIMELINE:END -->\n"
        )

        # Append first entry
        result = marker_utils.append_timeline_entry(content, "requirements-elicitation")
        assert "requirements-elicitation" in result

        # Append second entry
        result = marker_utils.append_timeline_entry(result, "writing-plans")
        assert "requirements-elicitation" in result
        assert "writing-plans" in result

        # Append third entry
        result = marker_utils.append_timeline_entry(result, "impl-verify")
        assert "requirements-elicitation" in result
        assert "writing-plans" in result
        assert "impl-verify" in result

    def test_no_duplicate_backfill_when_end_already_set(self, marker_utils):
        """When last entry already has end set, don't overwrite it."""
        content = (
            "# ECW Session State\n"
            "<!-- ECW:TIMELINE:START -->\n"
            "- phase: requirements-elicitation\n"
            "  start: \"2026-05-05T12:00:00\"\n"
            "  end: \"2026-05-05T12:01:00\"\n"
            "  duration_s: 60\n"
            "<!-- ECW:TIMELINE:END -->\n"
        )
        result = marker_utils.append_timeline_entry(content, "writing-plans")

        # First entry should keep its original end time
        assert 'end: "2026-05-05T12:01:00"' in result or "end: '2026-05-05T12:01:00'" in result
        assert "duration_s: 60" in result

        # New entry should be appended
        assert "phase: writing-plans" in result
