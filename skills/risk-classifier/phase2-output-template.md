# Phase 2 Output Template

Use this format when outputting the Phase 2 Precise Classification report.

```markdown
## Change Risk Precise Assessment (Phase 2)

### Risk Level: P{X} (Phase 1 pre-assessment: P{Y}, {upgraded/downgraded/unchanged})

### Classification Factors
| Factor | Level | Rationale |
|--------|-------|-----------|
| Impact Scope | P{X} | {details: which shared resources/cross-domain calls/MQ Topics} |
| Change Type | P{X} | {details: state machine/signature/SQL etc.} |
| Business Sensitivity | P{X} | {details: inventory/tasks/orders etc.} |

### Impact Scope Details
- **Shared resources:** {list}
- **Cross-domain calls:** {list}
- **MQ Topics:** {list}
- **End-to-end paths:** {path ID + affected steps}
- **External systems:** {list}

### Level Change
{upgrade → list workflow steps to backfill}
{downgrade → list workflow steps that can be skipped (suggested, user decides)}
{unchanged → "Phase 1 pre-assessment was accurate, proceed as planned"}

### Downstream Workflow (Updated)
{list remaining workflow steps based on final level}
```
