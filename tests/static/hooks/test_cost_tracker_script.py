"""Unit tests for hooks/cost-tracker.py

Validates:
1. Token-based cost calculation
2. Model detection
3. Compact suggestion thresholds
4. Metrics file append
"""
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def cost_tracker():
    """Import cost-tracker.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "cost_tracker",
        HOOKS_DIR / "cost-tracker.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestModelDetection:
    def test_detects_opus(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-opus-4-6"}):
            assert cost_tracker._detect_model() == "opus"

    def test_detects_sonnet(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-sonnet-4-6"}):
            assert cost_tracker._detect_model() == "sonnet"

    def test_detects_haiku(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-haiku-4-5"}):
            assert cost_tracker._detect_model() == "haiku"

    def test_defaults_to_sonnet(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": ""}):
            assert cost_tracker._detect_model() == "sonnet"


class TestCostCalculation:
    def test_basic_cost(self, cost_tracker):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        cost = cost_tracker._calc_cost(usage, "sonnet")
        assert cost == 3.0

    def test_includes_cache_tokens(self, cost_tracker):
        usage = {
            "input_tokens": 500_000,
            "cache_read_input_tokens": 500_000,
            "cache_creation_input_tokens": 0,
            "output_tokens": 0,
        }
        cost = cost_tracker._calc_cost(usage, "sonnet")
        assert cost == 3.0

    def test_output_cost(self, cost_tracker):
        usage = {"input_tokens": 0, "output_tokens": 1_000_000}
        cost = cost_tracker._calc_cost(usage, "opus")
        assert cost == 75.0

    def test_empty_usage(self, cost_tracker):
        cost = cost_tracker._calc_cost({}, "sonnet")
        assert cost == 0.0


class TestMaxContext:
    def test_default_200k(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-opus-4-6"}):
            assert cost_tracker._get_max_context() == 200_000

    def test_1m_context(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-opus-4-6[1m]"}):
            assert cost_tracker._get_max_context() == 1_000_000

    def test_sonnet_1m(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": "pub-claude-sonnet-4-6[1m]"}):
            assert cost_tracker._get_max_context() == 1_000_000

    def test_empty_env(self, cost_tracker):
        with patch.dict(os.environ, {"ANTHROPIC_MODEL": ""}):
            assert cost_tracker._get_max_context() == 200_000


class TestCompactThreshold:
    def test_default_threshold(self, cost_tracker):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ECW_COMPACT_TOKEN_THRESHOLD", None)
            assert cost_tracker._get_compact_threshold() == 60

    def test_env_override(self, cost_tracker):
        with patch.dict(os.environ, {"ECW_COMPACT_TOKEN_THRESHOLD": "75"}):
            assert cost_tracker._get_compact_threshold() == 75

    def test_env_invalid_uses_default(self, cost_tracker):
        with patch.dict(os.environ, {"ECW_COMPACT_TOKEN_THRESHOLD": "abc"}):
            assert cost_tracker._get_compact_threshold() == 60

    def test_env_out_of_range_uses_default(self, cost_tracker):
        with patch.dict(os.environ, {"ECW_COMPACT_TOKEN_THRESHOLD": "5"}):
            assert cost_tracker._get_compact_threshold() == 60


class TestMetricsAppend:
    def test_creates_metrics_file(self, cost_tracker, tmp_path):
        usage = {"input_tokens": 100, "output_tokens": 50}
        cost_tracker._append_metrics(str(tmp_path), usage, "sess-1", "opus", 0.001, 0.05)
        metrics_file = tmp_path / ".claude" / "ecw" / "state" / "cost-metrics.jsonl"
        assert metrics_file.exists()
        entry = json.loads(metrics_file.read_text().strip())
        assert entry["session_id"] == "sess-1"
        assert entry["model"] == "opus"
        assert entry["input_tokens"] == 100
        assert entry["output_tokens"] == 50

    def test_appends_multiple_entries(self, cost_tracker, tmp_path):
        usage = {"input_tokens": 100, "output_tokens": 50}
        cost_tracker._append_metrics(str(tmp_path), usage, "s1", "opus", 0.001, 10.0)
        cost_tracker._append_metrics(str(tmp_path), usage, "s2", "opus", 0.002, 20.0)
        metrics_file = tmp_path / ".claude" / "ecw" / "state" / "cost-metrics.jsonl"
        lines = metrics_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestCostTrackerScript:
    def test_script_exists(self):
        assert (HOOKS_DIR / "cost-tracker.py").exists()

    def test_hooks_json_references_cost_tracker(self):
        hooks_json = HOOKS_DIR.parent / "hooks" / "hooks.json"
        data = json.loads(hooks_json.read_text())
        stop_entries = data["hooks"].get("Stop", [])
        found = any(
            "cost-tracker.py" in hook.get("command", "")
            for entry in stop_entries
            for hook in entry.get("hooks", [])
        )
        assert found, "hooks.json Stop event must reference cost-tracker.py"
