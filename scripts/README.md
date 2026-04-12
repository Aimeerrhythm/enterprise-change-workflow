# Scanner Output Format Specification

All scanners output **Markdown tables to stdout**. The `ecw-init` command captures this output and writes it to the appropriate knowledge file under `.claude/knowledge/`.

Errors and progress messages go to **stderr** so they don't pollute the parseable output.

## Cross-Domain Calls

**Scanner:** `scripts/java/scan-cross-domain-calls.sh`

Detects `@Resource` / `@Inject` dependencies that cross domain boundaries.

| Column | Description |
|--------|-------------|
| Caller Domain | Domain of the file containing the injection |
| Caller Class | Fully qualified or simple class name with the injection |
| Callee Domain | Domain where the injected class is defined |
| Callee Class | Simple class name being injected |
| Method | Field name (proxy for usage intent) |
| Call Type | `@Resource` or `@Inject` |

**Output example:**

```
| Caller Domain | Caller Class | Callee Domain | Callee Class | Method | Call Type |
|---------------|--------------|---------------|--------------|--------|-----------|
| outbound | OutboundBizService | inventory | InventoryFacade | inventoryFacade | @Resource |
```

## Shared Resources

**Scanner:** `scripts/java/scan-shared-resources.sh`

Identifies classes referenced (injected or imported) by 2+ domains.

| Column | Description |
|--------|-------------|
| Resource Name | Simple class name of the shared resource |
| Type | Inferred type: `Facade`, `Service`, `Manager`, `Mapper`, `Utils`, or `Other` |
| Consumer Domains | Comma-separated list of domains that reference this class |
| Consumer Count | Number of distinct domains |
| Key Methods | Field names used for injection (first 3, then `...`) |

**Output example:**

```
| Resource Name | Type | Consumer Domains | Consumer Count | Key Methods |
|---------------|------|------------------|----------------|-------------|
| InventoryFacade | Facade | outbound, inbound, replenishment | 3 | inventoryFacade |
```

## MQ Topology

**Scanner:** `scripts/java/scan-mq-topology.sh`

Maps RocketMQ topic relationships: who publishes, who consumes, what business action.

| Column | Description |
|--------|-------------|
| Topic | MQ topic name |
| Publisher Domain | Domain of the class that sends to this topic |
| Publisher Class | Class containing the send call |
| Consumer Domain | Domain of the listener class |
| Consumer Listener | Class annotated with `@RocketMQMessageListener` |
| Business Action | Inferred from listener class name or method (best-effort) |

**Output example:**

```
| Topic | Publisher Domain | Publisher Class | Consumer Domain | Consumer Listener | Business Action |
|-------|-----------------|----------------|-----------------|-------------------|-----------------|
| OUTBOUND_ORDER_CREATED | outbound | OutboundEventPublisher | inventory | InventoryAllocationListener | allocate inventory |
```

## Integration with ecw-init

The `ecw-init` command runs each scanner and writes output to:

- Cross-domain calls -> `.claude/knowledge/common/cross-domain-calls.md`
- Shared resources -> `.claude/knowledge/common/shared-resources.md`
- MQ topology -> `.claude/knowledge/common/mq-topology.md`

These files are then referenced by the domain knowledge index and used during impact analysis.

## Accuracy Expectations

These scanners use **grep/awk heuristics**, not AST parsing. They are starting points for manual curation:

- **Cross-domain calls:** High recall, may have false positives from test files or unused injections
- **Shared resources:** Reliable for injection-based sharing; misses runtime/reflection usage
- **MQ topology:** Best-effort topic extraction; string-interpolated topics will be missed

After initial scan, review and curate the output before committing to knowledge files.
