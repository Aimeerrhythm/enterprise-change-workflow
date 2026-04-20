# Knowledge Summary Template

Used when writing to `.claude/ecw/session-data/{workflow-id}/knowledge-summary.md`.

```markdown
# Knowledge Summary (extracted during domain-collab analysis)

## Involved Domains: {domain list}

## Related Shared Resources
{Entries extracted from shared-resources.md relevant to this change}

## Related Cross-Domain Calls
{Entries extracted from cross-domain-calls.md involving changed domains}

## Related MQ Topics
{Entries extracted from mq-topology.md involving changed domains}

## Related Business Rules Summary
{For each involved domain: summary of state machines and validation rules from business-rules.md relevant to this change}
```
