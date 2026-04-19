# Phase 3 Output Templates

Three output variants based on calibration determination.

## Significant Deviation (level difference ≥ 2, or key dimension deviation ≥ 50%)

```markdown
## Risk Prediction Calibration Suggestions (Phase 3)

### Predicted vs. Actual
| Dimension | Phase 1 Predicted | Phase 2 Precise | biz-impact-analysis Actual |
|-----------|------------------|-----------------|---------------------------|
| Risk Level | P{x} | P{y} | Should be P{z} |
| Affected domain count | {n} | {n} | {n} |
| Cross-domain calls | {n} | {n} | {n} |
| MQ Topics | {n} | {n} | {n} |
| External systems | {n} | {n} | {n} |

### Deviation Analysis
{Root cause analysis: Why was the prediction inaccurate?}
- Keyword match missed? → change-risk-classification.md needs additional keywords
- Shared resource table incomplete? → shared-resources.md needs consumer domain list additions
- Domain registry scope inaccurate? → domain-registry.md needs code directory adjustment
- Cross-domain call matrix missing? → cross-domain-calls.md needs call relationship additions

### Suggested Adjustments
- `change-risk-classification.md`: {specific suggestion, e.g., "Upgrade keyword XXX from P2 to P1"}
- `shared-resources.md`: {e.g., "Add consumer domain list for shared resource XXX"}
- `domain-registry.md`: {e.g., "Expand code directory scope for domain XXX"}
- `cross-domain-calls.md`: {e.g., "Add call relationship A→B"}

> Above are suggestions only. Require user confirmation before manual configuration changes.
```

## Accurate Prediction

```
Phase 3 calibration complete: Predicted level P{x} matches actual impact. No adjustments needed.
```

## Minor Deviation (level difference 1 and key dimension deviation < 50%)

```
Phase 3 calibration complete: Predicted level P{x}, actual closer to P{y}. Minor deviation within acceptable range.
```
