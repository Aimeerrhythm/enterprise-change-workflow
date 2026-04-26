# Lifecycle Commands Reference

Detailed process for create, status, push, destroy sub-commands.

## create

### Prerequisites

- Current directory must be inside a git repository (to detect sibling service directories)
- OR user must provide explicit service paths

### Process

```
Step 1: Parse service list + requirement
  - Extract service names from arguments or user's natural language input
  - Extract requirement description from user's input — this is REQUIRED.
    (e.g. "订单取消后需要释放wms的库存" from the user's message)
  - If requirement cannot be extracted from the input → AskUserQuestion to get it
    before proceeding. An empty requirement blocks Phase 1 and makes the workspace useless.
  - Save requirement for writing to workspace.yml in Step 8

Step 2: Service discovery
  - For each service name, scan parent directory's children for matching directory name
  - Validate each match is a git repository (has .git/)
  - Not found → AskUserQuestion: ask user to provide the full path
  - Display discovered services and ask user to confirm

Step 3: Branch conflict detection
  - Default branch name: ws/{workspace-name} (or user-specified via --branch)
  - For each service: check if target branch is already checked out
    - Currently checked out → ERROR: suggest switching or using different branch name
    - Exists but not checked out → WARN: worktree will use existing branch
  - Detect each service's default branch (master/main)
  - For each service: run `git fetch origin {base_branch}` to ensure remote tracking is up to date

Step 4: User confirmation ★ MANDATORY
  - AskUserQuestion (language follows output_language):
    Show workspace name, path, requirement text, service table (service | source | base branch | workspace branch),
    plus any warnings. Ask user to confirm or modify.
  - If requirement is empty at this step → STOP. Do not proceed without a requirement.

Step 5: Create workspace directory
  - Path: {parent_of_current_dir}/workspaces/{name}-{YYYYMMDD}/

Step 6: Create git worktrees (always based on origin/{base_branch})
  - For each service:
    git -C {source_path} worktree add {workspace_path}/{service_id} -b {branch} origin/{base_branch}
  - Always use origin/{base_branch} (not local) to guarantee worktree starts from latest remote code.
  - On failure: log error, continue with remaining. ALL fail → abort and clean up.

Step 7: Pre-trust workspace directories
  - For each service: cd {workspace_path}/{service_id} && claude -p "echo ok"
  - Triggers trust dialog (one-time per directory)

Step 8: Generate configuration files
  - workspace.yml → {workspace}/.claude/ecw/workspace.yml (include requirement description)
  - CLAUDE.md → {workspace}/CLAUDE.md
    Use templates/workspace-claude.md as a STATIC template.
    Fill ONLY placeholder variables by plain string substitution.
    Copy requirement text verbatim from workspace.yml — do NOT re-generate in Chinese.
    This eliminates uXXXX encoding issues in the create phase.
  - mkdir -p {workspace}/.claude/ecw/session-data/

  For each service worktree, update .gitignore (Issue 21 — ECW artifacts must not be committed):
    1. Check if {workspace}/{service}/.gitignore exists; create if not
    2. Check if ".claude/ecw/session-data/" line exists; append if not
    3. Check if ".claude/ecw/state/" line exists; append if not
    Comment to add: "# ECW workspace session artifacts"

Step 9: Auto-enter workspace and start run
  - Use terminal adapter (see ./terminal-adapters.md) to open new tab and run start.sh
  - start.sh runs: cd {workspace_path} && claude "/ecw:workspace run"
    (run reads requirement from workspace.yml — no need to pass as argument)
  - If terminal adapter fails → fallback: print command for user to copy
  - Current session's create work is done
```

### Error Handling

| Scenario | Handling |
|----------|---------|
| Service directory not found | AskUserQuestion for manual path |
| Not a git repo | Skip with warning, continue |
| Branch already checked out | Error with clear message, suggest alternative |
| Worktree creation fails (single) | Log error, continue with others |
| Worktree creation fails (all) | Abort, clean up workspace directory |
| Workspace directory already exists | AskUserQuestion: overwrite or choose new name |

## status

```
For each service in workspace.yml:
  1. git status --porcelain → clean / dirty
  2. git log {base_branch}..{branch} --oneline → unpushed commits
  3. Check status.json → child session status

Display table:
  Service | Branch | Status | Unpushed | Session
```

## push

```
For each service with unpushed commits:
  1. Show commit list
  2. AskUserQuestion: confirm push?
  3. If yes: git push -u origin {branch}
  4. Report result
```

## destroy

```
Step 1: Safety check — warn about uncommitted/unpushed changes
Step 2: AskUserQuestion to confirm deletion
Step 3: git worktree remove for each service
Step 4: rm -rf workspace directory
Step 5: Optionally delete remote branches (AskUserQuestion)
```
