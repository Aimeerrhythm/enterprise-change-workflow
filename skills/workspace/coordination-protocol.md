# Coordination Protocol Reference

File-based coordination between master coordinator and child sessions.

## status.json Schema

Written by child session on completion. Read by coordinator for polling.

```json
{
  "service": "ofc",
  "status": "completed",
  "summary": "Implemented cancelOrder with stock release and MQ notification",
  "files_changed": [
    "src/main/java/com/example/ofc/service/OrderService.java",
    "src/main/java/com/example/ofc/event/OrderCancelEvent.java"
  ],
  "commits": [
    "abc1234 feat: add cancelOrder stock release logic",
    "def5678 feat: add OrderCancelEvent MQ producer"
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
| cross-service-plan.md | `{ws}/.claude/ecw/session-data/{wf-id}/cross-service-plan.md` | coordinator | Phase 1-2 |
| workspace-task.md | `{ws}/{svc}/.claude/ecw/workspace-task.md` | coordinator | Phase 3 |
| status.json | `{ws}/{svc}/status.json` | child session | Phase 4 completion |
