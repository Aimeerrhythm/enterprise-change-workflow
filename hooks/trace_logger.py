"""ECW structured hook trace logger — append-only JSONL diagnostic log.

Provides a single function ``log_trace(cwd, hook, event, **kwargs)`` that
appends one JSON record per call to ``.claude/ecw/state/hook-trace.jsonl``.

Design principles:
- **Best-effort**: never raises exceptions; trace failures must not affect
  hook behaviour or block any workflow.
- **Append-only JSONL**: one JSON object per line for easy ``grep`` / ``jq``
  consumption.
- **Auto-rotation**: when the file exceeds 512 KB, the first half of lines
  is discarded to keep the file bounded.
"""

import json
import os
from datetime import datetime


_TRACE_FILE = ".claude/ecw/state/hook-trace.jsonl"
_MAX_SIZE_BYTES = 512 * 1024  # 512 KB


def log_trace(cwd, hook, event, **kwargs):
    """Append a structured trace record.  Best-effort — never raises.

    Args:
        cwd:   Project root directory (from hook input_data["cwd"]).
               If falsy or not an ECW project, the call is silently ignored.
        hook:  Hook name (e.g. "auto-continue", "dispatcher").
        event: Hook event (e.g. "PreToolUse", "PostToolUse").
        **kwargs: Arbitrary extra fields merged into the JSON record.
    """
    if not cwd:
        return
    if not os.path.isfile(os.path.join(cwd, ".claude", "ecw", "ecw.yml")):
        return
    try:
        trace_path = os.path.join(cwd, _TRACE_FILE)
        os.makedirs(os.path.dirname(trace_path), exist_ok=True)

        # Rotation: truncate when file exceeds max size (keep second half)
        if os.path.exists(trace_path) and os.path.getsize(trace_path) > _MAX_SIZE_BYTES:
            with open(trace_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(trace_path, "w", encoding="utf-8") as f:
                f.writelines(lines[len(lines) // 2:])

        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "hook": hook,
            "event": event,
            **kwargs,
        }
        with open(trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Trace is best-effort
