# workspace-analysis-task.md Template

> When writing this file, coordinator must translate ALL section headers and instruction text
> into `output_language`. The template below uses English as the reference spec.

```markdown
## Workspace Analysis Task — {service}

output_language: {value from ecw.yml or workspace.yml}

## Original Requirement (verbatim — do not paraphrase)
{exact text from workspace.yml.requirement}

## Coordinator's Business Assessment (hypothesis — verify against your code)
- Your role: {Provider / Consumer / Both}
- Your business responsibility: {1-2 sentences, business language only — no class names or method names}
- Interaction type: {Dubbo / MQ / unclear}

## Cross-Service Context (for risk classification)
- Interaction type: {MQ / Dubbo / unclear}
- Contract change type: {new field (backward compatible) / field removal / signature change / new topic / other}
- Your layer (Dubbo only): {1 = Provider / 2 = Consumer / N/A}
- Provider service path (Dubbo Consumer only): {workspace-relative path to Provider service, e.g. ../ofc — N/A if not Dubbo Consumer}
- Other services involved:
  {for each other service: name → role → what they plan to do}

## Analysis Strategy
ECW Status: {ECW-ready / ECW-partial / ECW-absent}
{if ECW-ready or ECW-partial}:
  Read .claude/knowledge/<relevant domain>/ FIRST.
  Scan source code only for gaps not covered by knowledge docs.
{if ECW-absent}:
  No knowledge files available. Scan source code directly.

## Other Services Context
{for each other service: their role and business responsibility from Phase 1}

## Open Questions (flagged by Coordinator — needs code analysis to resolve)
{any ambiguities that Phase 2 must investigate, e.g. unclear interaction type, unknown entry points}

## Your Task — Full Flow (Phase 2 Analysis → Phase 4 Implementation)

### Phase 2: Analysis
1. Follow the Analysis Strategy above — knowledge files first if ECW-ready
2. Find the correct implementation entry points yourself (class + method + reason)
3. Verify or correct the Coordinator's business assessment — you have authority to override
4. Determine the interaction pattern if marked unclear
5. Write your technical plan to .claude/ecw/session-data/{wf-id}/analysis-report.md

### Wait for Phase 3 (Coordinator Contract Alignment)
After writing analysis-report.md, poll for confirmed-contract.md.
Maximum wait: 180 minutes. If exceeded, pause and wait for manual intervention.

```bash
wf_id="{wf-id}"
max_iterations=2160   # 180 min (2160 x 5s)
for i in $(seq 1 $max_iterations); do
  [ -f ".claude/ecw/session-data/${wf_id}/confirmed-contract.md" ] && echo "FOUND" && break
  # Print status every 5 minutes (60 iterations)
  [ $((i % 60)) -eq 0 ] && echo "Still waiting for confirmed-contract.md... ($((i * 5 / 60))min elapsed)"
  sleep 5
done
[ ! -f ".claude/ecw/session-data/${wf_id}/confirmed-contract.md" ] && echo "TIMEOUT"
```

If result is TIMEOUT (180min exceeded):
- Announce: "Polling timeout: confirmed-contract.md not found after 180 minutes. Coordinator may have exited or be waiting for user input. Session is paused."
- Use AskUserQuestion: "Continue waiting 30 more minutes?" / "Abort this session"
- On "Continue waiting": run another 360-iteration polling loop, then repeat the question if still not found
- On "Abort": exit session cleanly without writing any further artifacts

Once confirmed-contract.md appears → read it and proceed to Phase 4.

### Phase 4: Implementation
Before writing any code, invoke `ecw:risk-classifier`. Read `confirmed-contract.md` and `analysis-report.md` as the change context.

**Workspace wf-id override**: When ecw:risk-classifier reaches its "State Persistence" step (write session-state.md), do NOT generate a new timestamp as workflow-id. Instead, use the workspace `{wf-id}` from this task file and write to:
`.claude/ecw/session-data/{wf-id}/session-state.md`
This ensures coordinator can observe your ECW flow progress at a known path. Continue updating this same file as each ECW skill completes (mode switches, Subagent Ledger entries, etc.).

Read confirmed-contract.md to determine your interaction pattern and layer, then follow the matching path below.

**MQ (all services parallel):**
Proceed to implementation immediately. No cross-service dependency.

**Dubbo — Provider (layer 1):**
1. Implement API layer first (interfaces + DTOs defined in the contract)
2. Run `mvn install` for the API module only
3. Write api-ready.json → `.claude/ecw/session-data/{wf-id}/api-ready.json`
4. Continue with Service layer implementation without waiting for Consumer

**Dubbo — Consumer (layer 2):**
Use non-blocking dependency scheduling:
- Decompose all tasks from the contract and analysis-report.md
- For each task: if it requires Provider's API (imports Dubbo interface/DTO), check
  `{provider_service_path}/.claude/ecw/session-data/{wf-id}/api-ready.json`
  - Not found → skip for now, continue with other tasks
  - Found → execute
- After completing all independent tasks, retry any skipped tasks
- If api-ready.json still absent → poll with 60-minute timeout:
  ```bash
  wf_id="{wf-id}"
  provider_path="{provider_service_path}"
  for i in $(seq 1 720); do
    [ -f "${provider_path}/.claude/ecw/session-data/${wf_id}/api-ready.json" ] && echo "FOUND" && break
    [ $((i % 60)) -eq 0 ] && echo "Waiting for Provider api-ready.json... ($((i * 5 / 60))min elapsed)"
    sleep 5
  done
  [ ! -f "${provider_path}/.claude/ecw/session-data/${wf_id}/api-ready.json" ] && echo "TIMEOUT"
  ```
  If TIMEOUT: AskUserQuestion "Continue waiting 15 more minutes?" / "Skip Provider dependency" / "Abort this session"

**After all tasks done (all scenarios):**
- ECW-ready: ecw:impl-verify is auto-triggered by BLOCKING RULE. After pass, ecw:knowledge-track runs automatically.
- ECW-absent: run `/ecw:impl-verify` manually. After pass, run `/ecw:knowledge-track`.
- Write status.json → `.claude/ecw/session-data/{wf-id}/status.json`
  Use exactly this schema (fill in values, do not add or rename fields):
  ```json
  {
    "service": "{service_id}",
    "status": "completed",
    "summary": "one sentence describing what was implemented",
    "files_changed": ["relative/path/to/File.java"],
    "commits": ["abc1234 commit message"],
    "error": null
  }
  ```
  If implementation failed, set `"status": "failed"` and put the error message in `"error"`.

## Output Format
Write analysis-report.md to .claude/ecw/session-data/{wf-id}/analysis-report.md with:
  - Confirmed role (and corrections to coordinator's assessment if any)
  - Implementation entry points (class + method + reason, found by your own analysis)
  - Proposed interaction pattern (if was unclear)
  - Any concerns or blockers
All headings and labels in analysis-report.md must follow output_language above.

## Stale Plans Notice
Ignore any files in .claude/plans/ that predate this workspace session (wf-id: {wf-id}).
They belong to other workflows. Only act on plans tagged with this wf-id.

## Exit Criterion
Your task is complete when status.json is written. The session then exits.
Do NOT update coordinator's session-state.md — the coordinator owns that file exclusively.
```
