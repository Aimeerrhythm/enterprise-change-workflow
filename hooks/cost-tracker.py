#!/usr/bin/env python3
"""ECW cost-tracker hook — token-based cost tracking + smart compaction suggestion.

Runs as a Stop hook (async) after each assistant response:
1. Reads latest usage from session JSONL
2. Appends cost metrics to .claude/ecw/state/cost-metrics.jsonl
3. When context usage exceeds threshold, injects compaction suggestion

Replaces the old tool-call-count based compact-suggest approach with
token-based measurement for more accurate compaction timing.

Environment variables:
  ECW_COMPACT_TOKEN_THRESHOLD: context % to suggest compaction (default 60)
  ECW_MODEL_OVERRIDE: force pricing model (haiku|sonnet|opus)
"""

import glob
import json
import os
import sys
from datetime import datetime

# Pricing per 1M tokens (USD)
PRICING = {
    "haiku":  {"input": 0.80,  "output": 4.0},
    "sonnet": {"input": 3.00,  "output": 15.0},
    "opus":   {"input": 15.00, "output": 75.0},
}

DEFAULT_COMPACT_THRESHOLD = 60
STRONG_COMPACT_THRESHOLD = 80
METRICS_FILE = "cost-metrics.jsonl"


def _get_max_context():
    """Detect max context window from ANTHROPIC_MODEL env var."""
    model = os.environ.get("ANTHROPIC_MODEL", "")
    if "[1m]" in model:
        return 1_000_000
    return 200_000


def _detect_model():
    """Detect model from ANTHROPIC_MODEL env var."""
    model = os.environ.get("ANTHROPIC_MODEL", "").lower()
    if "haiku" in model:
        return "haiku"
    elif "opus" in model:
        return "opus"
    return "sonnet"


def _get_compact_threshold():
    """Read compact threshold from env, default 60%."""
    env_val = os.environ.get("ECW_COMPACT_TOKEN_THRESHOLD", "").strip()
    if env_val:
        try:
            val = int(env_val)
            if 10 <= val <= 95:
                return val
        except ValueError:
            pass
    return DEFAULT_COMPACT_THRESHOLD


def _calc_cost(usage, model):
    """Calculate cost in USD from usage dict."""
    prices = PRICING.get(model, PRICING["sonnet"])
    input_tokens = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    output_tokens = usage.get("output_tokens", 0)
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000
    return round(cost, 6)


def _get_latest_usage(cwd):
    """Read latest usage from session JSONL file."""
    try:
        project_key = cwd.replace("/", "-")
        session_dir = os.path.expanduser(f"~/.claude/projects/{project_key}")
        if not os.path.isdir(session_dir):
            return None

        files = glob.glob(os.path.join(session_dir, "*.jsonl"))
        if not files:
            return None

        latest = max(files, key=os.path.getmtime)
        last_usage = None
        session_id = os.path.splitext(os.path.basename(latest))[0]

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

        return last_usage, session_id
    except Exception:
        return None


def _append_metrics(cwd, usage, session_id, model, cost, context_pct):
    """Append metrics entry to cost-metrics.jsonl."""
    try:
        metrics_dir = os.path.join(cwd, ".claude", "ecw", "state")
        os.makedirs(metrics_dir, exist_ok=True)
        metrics_path = os.path.join(metrics_dir, METRICS_FILE)

        entry = {
            "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "session_id": session_id,
            "model": model,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_read": usage.get("cache_read_input_tokens", 0),
            "cache_create": usage.get("cache_creation_input_tokens", 0),
            "cost_usd": cost,
            "context_pct": round(context_pct, 1),
        }

        with open(metrics_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")

    if not cwd:
        print(json.dumps({"result": "continue"}))
        return

    result = _get_latest_usage(cwd)
    if not result:
        print(json.dumps({"result": "continue"}))
        return

    usage, session_id = result
    if not usage:
        print(json.dumps({"result": "continue"}))
        return

    model = os.environ.get("ECW_MODEL_OVERRIDE", "").lower() or _detect_model()
    cost = _calc_cost(usage, model)

    total_input = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    max_context = _get_max_context()
    context_pct = (total_input / max_context) * 100

    _append_metrics(cwd, usage, session_id, model, cost, context_pct)

    threshold = _get_compact_threshold()
    msg = ""
    if context_pct > STRONG_COMPACT_THRESHOLD:
        msg = (
            f"**[ECW] Context at {context_pct:.0f}%** — strongly recommend `/compact` now. "
            f"Session cost: ${cost:.4f} ({model}). "
            f"Context window is nearly full; compaction will preserve progress via session-state.md checkpoints."
        )
    elif context_pct > threshold:
        msg = (
            f"**[ECW] Context at {context_pct:.0f}%** — consider `/compact` at next logical breakpoint. "
            f"Session cost: ${cost:.4f} ({model})."
        )

    print(json.dumps({"result": "continue", "systemMessage": msg}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"result": "continue"}))
        sys.exit(0)
