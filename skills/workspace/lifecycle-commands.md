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
    before proceeding. An empty requirement blocks the initial decomposition step and makes the workspace useless.
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

Step 6.5: Sync ignored ECW infrastructure into each worktree ★ CRITICAL

  Source repos with ECW installed have `.claude/ecw/scripts/` (hook-runner.sh) and
  `.claude/settings.json` (or `.claude/settings.local.json`) — both are typically
  in `.gitignore`. `git worktree add` does NOT copy ignored files, so the worktree
  ends up with `.claude/ecw/ecw.yml` (tracked) but no `scripts/` and no `settings.json`.
  When the child session starts, every ECW hook fails silently because
  `${CLAUDE_PROJECT_DIR}/.claude/ecw/scripts/hook-runner.sh` does not exist.
  Symptoms: baseline_commit stays "TBD", auto-continue never advances current_phase,
  knowledge-reads.jsonl is never written.

  For each service worktree, mirror these from the source repo:

  ```bash
  src="{source_path}/.claude"
  dst="{workspace_path}/{service_id}/.claude"
  wf_id="{wf-id}"

  # 1. ECW hook runner directory (bash scripts under .claude/ecw/scripts/)
  hook_runner_ok=false
  if [ -f "${src}/ecw/scripts/hook-runner.sh" ]; then
    mkdir -p "${dst}/ecw"
    cp -R "${src}/ecw/scripts" "${dst}/ecw/scripts"
    hook_runner_ok=true
  else
    echo "WARN: ${service_id} source repo has no .claude/ecw/scripts/hook-runner.sh — child session will run with NO ECW hooks. baseline_commit, auto-continue, knowledge-read-logger all disabled."
  fi

  # 2. Project-local hook registration (settings.json / settings.local.json)
  for f in settings.json settings.local.json; do
    [ -f "${src}/${f}" ] && cp "${src}/${f}" "${dst}/${f}"
  done

  # 2a. Verify settings actually reference hook-runner.sh (file present ≠ hooks active).
  # Hook scripts are useless if settings don't register them. Surface the gap.
  if $hook_runner_ok; then
    settings_referencing_runner=$(grep -l "ecw/scripts/hook-runner.sh" "${dst}/settings.json" "${dst}/settings.local.json" 2>/dev/null)
    if [ -z "$settings_referencing_runner" ]; then
      echo "WARN: ${service_id} has hook-runner.sh but no settings*.json registers it. Hooks will not fire. The source repo's ECW install may be incomplete — re-run the ECW init script in the source repo."
    fi
  fi

  # 2b. Augment settings.local.json with worktree-specific write permissions.
  # The source repo's settings allow `Write(.claude/ecw/session-data/{any-wf-id}/*)`,
  # which uses a relative path and resolves correctly inside the worktree (cwd-relative
  # patterns travel with the cp). But the new wf-id from this workspace must be
  # writable — use `merge-settings.py` to union-merge instead of trusting the source
  # to already cover it.
  if command -v python3 >/dev/null 2>&1 && [ -f "${PLUGIN_ROOT:-}/scripts/merge-settings.py" ]; then
    python3 "${PLUGIN_ROOT}/scripts/merge-settings.py" "${dst}/.." || \
      echo "WARN: merge-settings.py failed for ${service_id}; child session may hit permission prompts when writing .claude/ecw/session-data/${wf_id}/*"
  fi
  ```

  Run this BEFORE Step 7 (pre-trust). Failures here are warnings — the run continues
  with reduced observability — but every warning must be surfaced so the user knows
  which services have degraded child sessions.

Step 7: Pre-trust workspace directories
  - For each service: cd {workspace_path}/{service_id} && claude -p "echo ok"
  - Triggers trust dialog (one-time per directory)

Step 8: Generate configuration files

  > **Permission notice**: Writing `settings.local.json` to the workspace `.claude/` directory
  > is the FIRST write — it will trigger one prompt: "allow Claude to edit its own settings".
  > Select that option. After that, subsequent ecw/ writes in the same session are covered.
  > If a second prompt appears (for ecw/ writes), select "allow all edits in ecw/ during this session".
  > The run session opened in Step 9 reads the injected settings.local.json and needs no prompts.

  Write files in this order (settings.local.json first — its allow rules prevent prompts
  for the run session that follows):

  a. settings.local.json → {workspace}/.claude/settings.local.json
     Build the JSON dynamically. Use the ABSOLUTE workspace path — Bash prefix matching
     requires exact path prefix, relative paths will not match Claude's absolute-path commands.
     ```json
     {
       "permissions": {
         "allow": [
           "Bash(mkdir -p {workspace_path}/.claude/)",
           "Write({workspace_path}/.claude/ecw/*)",
           "Write({workspace_path}/.claude/ecw/session-data/*/*)",
           "Bash(mkdir -p {workspace_path}/{svc1}/.claude/)",
           "Write({workspace_path}/{svc1}/.claude/ecw/*)",
           "Write({workspace_path}/{svc1}/.claude/ecw/session-data/*/*)",
           "Bash(mkdir -p {workspace_path}/{svc2}/.claude/)",
           "Write({workspace_path}/{svc2}/.claude/ecw/*)",
           "Write({workspace_path}/{svc2}/.claude/ecw/session-data/*/*)"
         ]
       }
     }
     ```
     Replace {workspace_path} with the actual workspace absolute path.
     Replace {svc1}, {svc2}, ... with actual service IDs from the confirmed service list.
     This file is read when the run session starts, preventing prompts during all
     phase artifact writes (`session-state.json`, cross-service-plan.md, confirmed-contract.md, etc.).

  b. workspace.yml → {workspace}/.claude/ecw/workspace.yml (include requirement description)
  c. CLAUDE.md → {workspace}/CLAUDE.md
     Use templates/workspace-claude.md as a STATIC template.
     Fill ONLY placeholder variables by plain string substitution.
     Copy requirement text verbatim from workspace.yml — do NOT re-generate in Chinese.
     This eliminates uXXXX encoding issues in the create phase.
  d. mkdir -p {workspace}/.claude/ecw/session-data/

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
