#!/usr/bin/env python3
"""ECW compact-suggest sub-hook — proactive compaction suggestion based on tool-call counter.

Tracks cumulative tool calls via a file counter. When the count reaches a
configurable threshold, injects a systemMessage suggesting the user compact
context at the current logical breakpoint.

Counter file: .claude/ecw/state/tool-call-count.txt
Threshold:    ECW_COMPACT_THRESHOLD env var (default 50), then every 25 after

This module is invoked by the dispatcher (PreToolUse) on every tool call.
It follows the sub-hook interface: check(input_data, config) -> (action, message)
"""

import os

# Default thresholds
DEFAULT_FIRST_THRESHOLD = 50
DEFAULT_REPEAT_INTERVAL = 25

COUNTER_FILENAME = "tool-call-count.txt"


def _get_counter_path(cwd):
    """Return path to the tool-call counter file."""
    return os.path.join(cwd, ".claude", "ecw", "state", COUNTER_FILENAME)


def _read_counter(counter_path):
    """Read current count from the counter file. Returns 0 if not found."""
    try:
        if os.path.exists(counter_path):
            with open(counter_path, encoding="utf-8") as f:
                return int(f.read().strip())
    except (ValueError, OSError):
        pass
    return 0


def _write_counter(counter_path, count):
    """Write current count to the counter file."""
    try:
        os.makedirs(os.path.dirname(counter_path), exist_ok=True)
        with open(counter_path, "w", encoding="utf-8") as f:
            f.write(str(count))
    except OSError:
        pass


def _get_thresholds():
    """Read threshold from environment or use defaults.

    Returns (first_threshold, repeat_interval).
    """
    env_val = os.environ.get("ECW_COMPACT_THRESHOLD", "").strip()
    if env_val:
        try:
            first = int(env_val)
            if first > 0:
                return first, max(first // 2, 10)
        except ValueError:
            pass
    return DEFAULT_FIRST_THRESHOLD, DEFAULT_REPEAT_INTERVAL


def _should_suggest(count, first_threshold, repeat_interval):
    """Determine whether to suggest compaction at this count.

    Returns True at count == first_threshold, then every repeat_interval after.
    """
    if count < first_threshold:
        return False
    if count == first_threshold:
        return True
    return (count - first_threshold) % repeat_interval == 0


def check(input_data, config):
    """Sub-hook entry point. Increment counter and suggest compaction if threshold reached.

    Args:
        input_data: PreToolUse hook input (tool_name, tool_input, cwd, ...).
        config: ECW config dict from dispatcher.

    Returns:
        ("continue", message) — never blocks, only suggests via systemMessage.
    """
    cwd = input_data.get("cwd", "")
    if not cwd:
        return ("continue", "")

    counter_path = _get_counter_path(cwd)
    count = _read_counter(counter_path) + 1
    _write_counter(counter_path, count)

    first_threshold, repeat_interval = _get_thresholds()
    if not _should_suggest(count, first_threshold, repeat_interval):
        return ("continue", "")

    msg = (
        f"**[ECW] Compaction suggested** — {count} tool calls in this session. "
        f"Consider running `/compact` at this logical breakpoint to free context. "
        f"session-state.md and session-data/ checkpoints will preserve progress."
    )
    return ("continue", msg)
