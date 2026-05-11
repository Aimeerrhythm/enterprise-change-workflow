# Dependency Graph Construction & Pre-flight

## Pre-flight Check

Before dispatching the first Task, run a build/test pre-flight to catch pre-existing failures early.

**Controlled by** `impl_orchestration.pre_check` in ecw.yml (default: `true`). Set to `false` to skip.

**Steps:**

1. Read ecw.yml to determine project type:
   - Java (`pom.xml` exists): run `mvn compile -q -T 1C` and `mvn test -q -T 1C`
   - Other project types: skip (no universal pre-flight command)
2. **Timeout**: 120s for compile, 600s (10 minutes) for tests
3. **On failure**:
   - Attempt one auto-fix pass (read error output, fix obvious issues like missing imports or syntax errors)
   - Re-run the failed check
   - If still failing: notify user with the error summary via AskUserQuestion — "Pre-flight check failed: {summary}. Continue anyway or fix first?" — then proceed based on user choice
4. **Record result** in session-state.json: `Pre-flight: PASS` or `Pre-flight: FAIL (continued)`
5. On success or user-approved continue: proceed to dependency graph construction

## Step 1: Extract Task Metadata from Plan (LLM)

For each `## Task N:` heading in the plan, extract:
- `id` (int): task number
- `files` (list of strings): files to create or modify — from "Files:" line or inferred from task description
- `depends_on` (list of ints): explicit dependency IDs — from "depends on Task N" / "after Task N" / "requires output from Task N" phrases

Plan task ordering often implies sequence — but only include in `depends_on` when explicitly stated or logically required (e.g., Task creates a class that another Task extends).

Heuristics for `files`:
- Plan usually lists "Files to create/modify" per task
- Same module + same class/file → include both tasks
- Same configuration file → include both tasks
- Uncertain → include the file (safe default — the script will serialize conflicting tasks)

## Step 2: Call dep_graph.py (Deterministic)

Format the extracted task list as JSON and run:

```bash
echo '[{"id": 1, "files": ["A.java"], "depends_on": []}, {"id": 2, "files": ["B.java", "Shared.java"], "depends_on": [1]}, {"id": 3, "files": ["C.java", "Shared.java"], "depends_on": []}]' | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/dep_graph.py"
```

The script handles:
- **File conflict detection**: tasks touching the same file are automatically serialized (lower ID first)
- **Topological sort**: Kahn's algorithm groups tasks into parallel execution layers
- **Cycle detection**: reports involved tasks if a cycle exists

Output:
```json
{"layers": [[1, 3], [2]], "conflicts": [{"tasks": [2, 3], "file": "Shared.java"}]}
```

If the output contains an `"error"` field (cycle detected), report the error to the user and ask how to resolve (remove a dependency, merge tasks, or restructure).

## Step 3: Display Execution Layers

Use the returned `layers` to display the execution plan to the user:

```
Execution Layers (max parallelism: 3):
  Layer 0: Task 1                       [1 task, serial]
  Layer 1: Task 2 | Task 4 | Task 6    [3 parallel]
  Layer 2: Task 3 | Task 5 | Task 7    [3 parallel]
  Layer 3: Task 8 | Task 9 | Task 10   [3 parallel]
  Layer 4: Task 12 | Task 13           [2 parallel]

  Estimated: 5 layers (vs 13 serial tasks)
```

If `conflicts` is non-empty, also display detected file conflicts so the user can verify the file-level serialization is correct.
