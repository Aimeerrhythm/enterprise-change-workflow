<!-- STATIC TEMPLATE — Fill {PLACEHOLDERS} by string substitution only. Do NOT use AI to generate Chinese content. Requirement text: verbatim copy from workspace.yml. -->
# {WORKSPACE_NAME} — Cross-Service Workspace

This is an ECW multi-repo workspace. Multiple services are assembled here via git worktree for cross-service development.

## Workspace Info

- **Requirement**: {REQUIREMENT_DESCRIPTION}
- **Created**: {CREATED_TIMESTAMP}
- **Config**: `.claude/ecw/workspace.yml`

## Services

| Service | Directory | Branch | Base Branch |
|---------|-----------|--------|-------------|
{SERVICE_TABLE_ROWS}

## How to Use

### Start coordinator flow
```
/ecw:workspace run "requirement description"
```
This triggers the 6-Phase coordinator: requirement decomposition → per-service analysis & planning → contract alignment → multi-session parallel implementation → cross-service verification → summary & push.

### Other commands
```
/ecw:workspace status    # View all services' git and session status
/ecw:workspace push      # Batch push with per-service confirmation
/ecw:workspace destroy   # Clean up worktrees and workspace directory
```

## Important Notes

- Each service directory is an independent git worktree — commit and branch operations are per-service
- Each service runs its own standard ECW flow (risk-classifier → requirements → writing-plans → impl → verify)
- Cross-service interface contracts (Dubbo signatures, MQ DTOs) are aligned in Phase 3 before any implementation begins
- Provider services are implemented before Consumer services (Layer 1 → Layer 2)

## Service Directories

Each subdirectory is a full git repository (worktree). You can `cd` into any service and work with it directly:

```bash
cd ofc/   # Work on fulfillment service
cd wms/   # Work on warehouse service
cd sci/   # Work on supply chain service
```
