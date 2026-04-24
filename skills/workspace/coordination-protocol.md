# Coordination Protocol Reference

File-based coordination between master coordinator and child sessions.

## status.json Schema

Written by child session on completion. Read by coordinator for polling.

```json
{
  "service": "{service_id}",
  "status": "completed",
  "summary": "Brief description of what was implemented",
  "files_changed": [
    "src/main/java/com/example/{pkg}/service/XxxService.java"
  ],
  "commits": [
    "abc1234 feat: brief commit message"
  ],
  "error": null
}
```

Status values:
- `completed`: all implementation and verification done
- `failed`: implementation attempted but encountered errors
- `blocked`: cannot proceed, needs coordinator/user intervention

## Polling Mechanism

Coordinator polls via Bash:

```bash
for i in $(seq 1 360); do
  all_done=true
  for service in {service_list}; do
    if [ ! -f "${service}/status.json" ]; then
      all_done=false
    fi
  done
  if [ "$all_done" = true ]; then break; fi
  sleep 5
done
```

Timeout: 30 minutes (360 iterations x 5 seconds).

## Timeout Handling

If a service doesn't complete within 30 minutes:
1. Notify user (language follows output_language)
2. AskUserQuestion: Continue waiting / Skip this service / Abort all

## Artifact Locations

| File | Location | Written by | Timing |
|------|----------|-----------|--------|
| workspace.yml | `{ws}/.claude/ecw/workspace.yml` | create command | workspace creation |
| CLAUDE.md | `{ws}/CLAUDE.md` | create command | workspace creation |
| cross-service-plan.md | `{ws}/.claude/ecw/session-data/{wf-id}/cross-service-plan.md` | coordinator | Phase 1 + updated Phase 3 |
| workspace-analysis-task.md | `{ws}/{svc}/.claude/ecw/workspace-analysis-task.md` | coordinator | Phase 1 end |
| analysis-report.md | `{ws}/{svc}/.claude/ecw/analysis-report.md` | child session | Phase 2 end |
| confirmed-contract.md | `{ws}/{svc}/.claude/ecw/confirmed-contract.md` | coordinator | Phase 3 end |
| status.json | `{ws}/{svc}/status.json` | child session | Phase 4 end |
