#!/usr/bin/env python3
"""ECW dependency graph builder for impl-orchestration.

Reads Plan task definitions (JSON from stdin), detects file conflicts,
builds execution layers via topological sort (Kahn's algorithm).

Input (stdin): JSON array of task objects
    [{"id": 1, "files": ["A.java"], "depends_on": []}, ...]

Output (stdout): JSON object with execution layers
    {"layers": [[1, 3], [2, 4], [5]], "conflicts": [...]}

Usage:
    echo '[{"id": 1, "files": ["A.java"], "depends_on": []}]' | python3 hooks/dep_graph.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict, deque


def build_layers(tasks: list[dict]) -> dict:
    """Build execution layers from task definitions.

    Args:
        tasks: List of task dicts, each with:
            - id (int): unique task identifier
            - files (list[str], optional): files this task creates/modifies
            - depends_on (list[int], optional): IDs of tasks this depends on

    Returns:
        dict with:
            - layers: list of lists of task IDs (parallel execution groups)
            - conflicts: list of detected file conflicts
            - error (str, only if cycle detected): description of the cycle
    """
    if not tasks:
        return {"layers": [], "conflicts": []}

    n = len(tasks)
    task_map = {t["id"]: t for t in tasks}

    # Track edges as a set of (from, to) to avoid duplicate in_degree counting
    edges: set[tuple[int, int]] = set()

    # Explicit dependencies
    for t in tasks:
        for dep in t.get("depends_on", []):
            if dep in task_map:
                edges.add((dep, t["id"]))

    # File conflict detection: same file -> lower ID first
    file_to_tasks: dict[str, list[int]] = defaultdict(list)
    for t in tasks:
        for f in t.get("files", []):
            file_to_tasks[f].append(t["id"])

    conflicts = []
    for f, task_ids in file_to_tasks.items():
        if len(task_ids) > 1:
            sorted_ids = sorted(task_ids)
            conflicts.append({"tasks": sorted_ids, "file": f})
            # Chain adjacent pairs: task[0] -> task[1] -> task[2] -> ...
            for i in range(len(sorted_ids) - 1):
                edges.add((sorted_ids[i], sorted_ids[i + 1]))

    # Build adjacency list and in_degree from deduplicated edges
    adj: dict[int, set[int]] = defaultdict(set)
    in_degree: dict[int, int] = defaultdict(int)
    for src, dst in edges:
        adj[src].add(dst)
        in_degree[dst] += 1

    # Topological sort -> layers (Kahn's algorithm)
    all_ids = [t["id"] for t in tasks]
    queue = deque(tid for tid in all_ids if in_degree[tid] == 0)
    layers: list[list[int]] = []

    while queue:
        layer = sorted(queue)  # deterministic ordering within layer
        layers.append(layer)
        next_queue: deque[int] = deque()
        for tid in layer:
            for dep in adj[tid]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_queue.append(dep)
        queue = next_queue

    # Cycle detection
    scheduled = sum(len(layer) for layer in layers)
    if scheduled < n:
        scheduled_set = set()
        for layer in layers:
            scheduled_set.update(layer)
        remaining = [tid for tid in all_ids if tid not in scheduled_set]
        return {
            "layers": layers,
            "conflicts": conflicts,
            "error": f"cycle detected involving tasks {remaining}",
        }

    return {"layers": layers, "conflicts": conflicts}


def main() -> None:
    try:
        tasks = json.load(sys.stdin)
        result = build_layers(tasks)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
