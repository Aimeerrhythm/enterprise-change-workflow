# Task Result File Schema

Each worktree implementer MUST write this file before reporting back.

**Location:** `{worktree-root}/.claude/ecw/task-result.json`

The coordinator reads this file from the worktree path BEFORE running `git merge`, using it as the authoritative data source for the Subagent Ledger.

## Schema

```json
{
  "task_id": "Task 2: Add InventoryLockDTO",
  "status": "completed",
  "summary": "Added InventoryLockDTO with 4 fields (lockId, itemId, quantity, expiry)",
  "files_changed": [
    "src/main/java/com/example/inventory/dto/InventoryLockDTO.java"
  ],
  "commits": [
    "abc1234 feat: add InventoryLockDTO"
  ],
  "error": null
}
```

## Field Definitions

| Field | Type | Required | Values |
|-------|------|----------|--------|
| `task_id` | string | yes | Full task label from the plan (e.g., "Task 2: Add InventoryLockDTO") |
| `status` | string | yes | `completed` \| `failed` \| `blocked` |
| `summary` | string | yes | One-sentence description of what was done (or what failed) |
| `files_changed` | string[] | yes | List of file paths created or modified |
| `commits` | string[] | yes | List of commits in format `"{sha} {message}"` |
| `error` | string\|null | yes | Error description if `status != completed`; `null` otherwise |

## Write Instructions

Implementer writes this file as the LAST step before the `## Report Format` section:

```bash
cat > .claude/ecw/task-result.json << 'RESULT_EOF'
{
  "task_id": "<task label from prompt>",
  "status": "completed",
  "summary": "<one-sentence summary>",
  "files_changed": ["<file1>", "<file2>"],
  "commits": ["<sha> <message>"],
  "error": null
}
RESULT_EOF
```

For `status: failed` or `status: blocked`, set `error` to a concise description.

## Coordinator Protocol

After each worktree Agent call returns:

1. **Read result file** (BEFORE `git merge`):
   ```bash
   cat {worktree_path}/.claude/ecw/task-result.json
   ```
2. **If file found**: use its fields as the authoritative source for the Subagent Ledger entry
3. **If file missing**: fall back to git log inference AND write
   `.claude/ecw/session-data/{wf-id}/task-{N}-aggregation-warning.md` to record the gap
4. **Then**: run `git merge {worktree-branch} --no-edit`
