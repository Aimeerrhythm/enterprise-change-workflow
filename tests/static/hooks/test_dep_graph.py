"""Unit tests for hooks/dep_graph.py

Covers: basic layering, linear dependencies, file conflict detection,
mixed dependencies, cycle detection, empty input, single task,
complex graphs, output format validation, and CLI stdin/stdout protocol.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ── Module loading ──

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"
DEP_GRAPH_SCRIPT = HOOKS_DIR / "dep_graph.py"


@pytest.fixture
def dep_graph():
    """Import dep_graph.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "dep_graph",
        DEP_GRAPH_SCRIPT,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════
# Basic Layering — no dependencies, full parallelism
# ══════════════════════════════════════════════════════


class TestBasicLayering:
    """Tasks with no dependencies should all land in a single layer."""

    def test_all_parallel(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": []},
            {"id": 3, "files": ["C.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 2, 3]]
        assert result["conflicts"] == []
        assert "error" not in result

    def test_ids_sorted_within_layer(self, dep_graph):
        """IDs within a layer are sorted for deterministic output."""
        tasks = [
            {"id": 5, "files": ["E.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": []},
            {"id": 9, "files": ["I.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[2, 5, 9]]


# ══════════════════════════════════════════════════════
# Linear Dependencies — fully sequential chain
# ══════════════════════════════════════════════════════


class TestLinearDependencies:
    """Chain: 1 → 2 → 3 produces three separate layers."""

    def test_three_layer_chain(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java"], "depends_on": [2]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2], [3]]
        assert "error" not in result

    def test_two_task_dependency(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2]]


# ══════════════════════════════════════════════════════
# File Conflict Detection
# ══════════════════════════════════════════════════════


class TestFileConflicts:
    """Two tasks modifying the same file become serialized (lower ID first)."""

    def test_same_file_creates_dependency(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["Config.java"], "depends_on": []},
            {"id": 2, "files": ["Config.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2]]
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["tasks"] == [1, 2]
        assert result["conflicts"][0]["file"] == "Config.java"

    def test_three_tasks_same_file_chain(self, dep_graph):
        """Three tasks on same file → chain: 1→3→5."""
        tasks = [
            {"id": 5, "files": ["Config.java"], "depends_on": []},
            {"id": 1, "files": ["Config.java"], "depends_on": []},
            {"id": 3, "files": ["Config.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [3], [5]]
        assert "error" not in result

    def test_partial_file_overlap(self, dep_graph):
        """Task 1 and Task 2 share one file, Task 3 is independent."""
        tasks = [
            {"id": 1, "files": ["A.java", "Shared.java"], "depends_on": []},
            {"id": 2, "files": ["B.java", "Shared.java"], "depends_on": []},
            {"id": 3, "files": ["C.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        # Task 3 can run in parallel with Task 1
        assert result["layers"] == [[1, 3], [2]]
        assert len(result["conflicts"]) == 1

    def test_no_false_conflict_on_different_files(self, dep_graph):
        """Tasks with entirely different files have no conflicts."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["conflicts"] == []


# ══════════════════════════════════════════════════════
# Mixed Dependencies — explicit + file conflicts
# ══════════════════════════════════════════════════════


class TestMixedDependencies:
    """Combining explicit depends_on with file conflict edges."""

    def test_explicit_plus_file_conflict(self, dep_graph):
        """Task 2 depends on Task 1 AND shares a file with Task 3."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java", "Shared.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java", "Shared.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        # Task 1 and Task 3 can run in parallel (layer 0)
        # Task 2 depends on Task 1 AND file-conflicts with Task 3 (lower ID 2 < 3, so 2→3)
        # Layer 0: [1, 3] — wait, Task 2 depends on 1 (layer 0), and
        #   file conflict: 2 and 3 share Shared.java → 2 before 3
        # So: layer 0: [1], layer 1: [2], layer 2: [3]?
        # Actually: Task 3 has no explicit dep, and file conflict puts 2→3.
        # Task 2 depends on 1. So: Layer 0: [1], Layer 1: [2], Layer 2: [3]
        # Wait — Task 3 has in_degree from file conflict (2→3), but Task 3 has
        # no explicit dep. Task 1 is free. So Layer 0: [1], Layer 1: [2], Layer 2: [3]
        assert result["layers"] == [[1], [2], [3]]
        assert len(result["conflicts"]) == 1

    def test_redundant_explicit_and_file_conflict(self, dep_graph):
        """Task 2 depends_on [1] AND shares a file with Task 1.
        Should not double-count the edge."""
        tasks = [
            {"id": 1, "files": ["Shared.java"], "depends_on": []},
            {"id": 2, "files": ["Shared.java"], "depends_on": [1]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2]]
        # Must not error from double-counted in_degree
        assert "error" not in result

    def test_diamond_dependency(self, dep_graph):
        """Diamond: 1 → {2, 3} → 4."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java"], "depends_on": [1]},
            {"id": 4, "files": ["D.java"], "depends_on": [2, 3]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2, 3], [4]]
        assert "error" not in result


# ══════════════════════════════════════════════════════
# Cycle Detection
# ══════════════════════════════════════════════════════


class TestCycleDetection:
    """Cycles in the dependency graph should be reported as errors."""

    def test_simple_cycle_a_b_a(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": [2]},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
        ]
        result = dep_graph.build_layers(tasks)
        assert "error" in result
        assert "cycle" in result["error"].lower()

    def test_three_node_cycle(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": [3]},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java"], "depends_on": [2]},
        ]
        result = dep_graph.build_layers(tasks)
        assert "error" in result

    def test_partial_cycle_with_valid_tasks(self, dep_graph):
        """Some tasks form a cycle, others are valid. Only cycled ones reported."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [3]},
            {"id": 3, "files": ["C.java"], "depends_on": [2]},
        ]
        result = dep_graph.build_layers(tasks)
        assert "error" in result
        # Task 1 should still be in layers
        assert [1] in result["layers"]


# ══════════════════════════════════════════════════════
# Edge Cases
# ══════════════════════════════════════════════════════


class TestEdgeCases:
    """Empty input, single task, and other edge cases."""

    def test_empty_input(self, dep_graph):
        result = dep_graph.build_layers([])
        assert result["layers"] == []
        assert result["conflicts"] == []
        assert "error" not in result

    def test_single_task(self, dep_graph):
        tasks = [{"id": 1, "files": ["A.java"], "depends_on": []}]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1]]
        assert result["conflicts"] == []

    def test_task_with_no_files(self, dep_graph):
        """Tasks with empty file lists should still work."""
        tasks = [
            {"id": 1, "files": [], "depends_on": []},
            {"id": 2, "files": [], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 2]]

    def test_missing_files_key_defaults_to_empty(self, dep_graph):
        """Tasks without 'files' key should be treated as having no files."""
        tasks = [
            {"id": 1, "depends_on": []},
            {"id": 2, "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 2]]

    def test_missing_depends_on_key_defaults_to_empty(self, dep_graph):
        """Tasks without 'depends_on' key should be treated as having no deps."""
        tasks = [
            {"id": 1, "files": ["A.java"]},
            {"id": 2, "files": ["B.java"]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 2]]

    def test_dependency_on_nonexistent_task_ignored(self, dep_graph):
        """depends_on referencing a task ID not in the list is ignored."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": [99]},
            {"id": 2, "files": ["B.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 2]]
        assert "error" not in result

    def test_duplicate_depends_on_no_double_count(self, dep_graph):
        """Duplicate entries in depends_on should not break in_degree counting."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1, 1, 1]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2]]
        assert "error" not in result


# ══════════════════════════════════════════════════════
# Complex Graph — multiple parallel paths + convergence
# ══════════════════════════════════════════════════════


class TestComplexGraph:
    """Multiple parallel paths converging at a single point."""

    def test_fan_out_fan_in(self, dep_graph):
        """
        1 → {2, 3, 4} → 5
        Three independent middle tasks converge on a final task.
        """
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java"], "depends_on": [1]},
            {"id": 4, "files": ["D.java"], "depends_on": [1]},
            {"id": 5, "files": ["E.java"], "depends_on": [2, 3, 4]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1], [2, 3, 4], [5]]

    def test_two_independent_chains(self, dep_graph):
        """
        Chain A: 1 → 2 → 3
        Chain B: 4 → 5
        No interaction between chains.
        """
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java"], "depends_on": [2]},
            {"id": 4, "files": ["D.java"], "depends_on": []},
            {"id": 5, "files": ["E.java"], "depends_on": [4]},
        ]
        result = dep_graph.build_layers(tasks)
        assert result["layers"] == [[1, 4], [2, 5], [3]]

    def test_file_conflict_bridges_independent_chains(self, dep_graph):
        """
        Chain A: 1 → 2
        Chain B: 3 → 4
        But Task 2 and Task 3 share a file → 2 must come before 3.
        """
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java", "Shared.java"], "depends_on": [1]},
            {"id": 3, "files": ["C.java", "Shared.java"], "depends_on": []},
            {"id": 4, "files": ["D.java"], "depends_on": [3]},
        ]
        result = dep_graph.build_layers(tasks)
        # Layer 0: [1] (3 is blocked by file conflict with 2, but 2→3, and 2 depends on 1)
        # Layer 1: [2]
        # Layer 2: [3]
        # Layer 3: [4]
        assert result["layers"] == [[1], [2], [3], [4]]

    def test_wide_parallel_layer(self, dep_graph):
        """Many tasks with no dependencies → single wide layer."""
        tasks = [{"id": i, "files": [f"F{i}.java"], "depends_on": []} for i in range(1, 11)]
        result = dep_graph.build_layers(tasks)
        assert len(result["layers"]) == 1
        assert result["layers"][0] == list(range(1, 11))


# ══════════════════════════════════════════════════════
# Output Format Validation
# ══════════════════════════════════════════════════════


class TestOutputFormat:
    """Verify the structure of the returned dict."""

    def test_layers_is_list_of_lists(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
        ]
        result = dep_graph.build_layers(tasks)
        assert isinstance(result["layers"], list)
        for layer in result["layers"]:
            assert isinstance(layer, list)
            for tid in layer:
                assert isinstance(tid, int)

    def test_conflicts_is_list_of_dicts(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["Shared.java"], "depends_on": []},
            {"id": 2, "files": ["Shared.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        assert isinstance(result["conflicts"], list)
        for c in result["conflicts"]:
            assert isinstance(c, dict)
            assert "tasks" in c
            assert "file" in c

    def test_result_is_json_serializable(self, dep_graph):
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["A.java"], "depends_on": []},
        ]
        result = dep_graph.build_layers(tasks)
        # Must not raise
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed == result


# ══════════════════════════════════════════════════════
# CLI Mode — subprocess stdin/stdout protocol
# ══════════════════════════════════════════════════════


class TestCLI:
    """Test the CLI interface via subprocess."""

    def test_cli_basic_input_output(self):
        """Basic CLI: JSON in via stdin, JSON out via stdout."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": []},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
        ]
        proc = subprocess.run(
            [sys.executable, str(DEP_GRAPH_SCRIPT)],
            input=json.dumps(tasks),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["layers"] == [[1], [2]]

    def test_cli_empty_input(self):
        """Empty list via CLI."""
        proc = subprocess.run(
            [sys.executable, str(DEP_GRAPH_SCRIPT)],
            input="[]",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert result["layers"] == []

    def test_cli_invalid_json(self):
        """Invalid JSON → exit 1 with error in output."""
        proc = subprocess.run(
            [sys.executable, str(DEP_GRAPH_SCRIPT)],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 1
        result = json.loads(proc.stdout)
        assert "error" in result

    def test_cli_cycle_reported(self):
        """Cycle detection reported via CLI."""
        tasks = [
            {"id": 1, "files": ["A.java"], "depends_on": [2]},
            {"id": 2, "files": ["B.java"], "depends_on": [1]},
        ]
        proc = subprocess.run(
            [sys.executable, str(DEP_GRAPH_SCRIPT)],
            input=json.dumps(tasks),
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Cycle is not a script-level error; script returns 0 with error field
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert "error" in result
        assert "cycle" in result["error"].lower()

    def test_cli_file_conflicts_in_output(self):
        """File conflicts are included in CLI output."""
        tasks = [
            {"id": 1, "files": ["Config.java"], "depends_on": []},
            {"id": 2, "files": ["Config.java"], "depends_on": []},
        ]
        proc = subprocess.run(
            [sys.executable, str(DEP_GRAPH_SCRIPT)],
            input=json.dumps(tasks),
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        result = json.loads(proc.stdout)
        assert len(result["conflicts"]) == 1
