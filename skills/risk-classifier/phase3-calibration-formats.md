# Phase 3 Calibration File Formats

## Two Calibration Files — Distinct Roles

| File | Role | Format | Consumer |
|------|------|--------|----------|
| `calibration-log.md` | Full-dimension comparison log | Detailed table (Phase 1/2/Actual per dimension) | Human review, pattern analysis |
| `calibration-history.md` | Quick-lookup structured index | Concise bullet list (Predicted/Actual/Keywords) | Phase 1 automated reference |

`calibration-log.md` is the source of truth; `calibration-history.md` is a derived index optimized for Phase 1 to scan quickly without parsing tables. Both are appended in the same Phase 3 execution — log first, then history.

---

## Step 4: Append to calibration-log.md

Path: `.claude/ecw/calibration-log.md` (configurable via ecw.yml `paths.calibration_log`).

Append format:

```markdown
### {YYYY-MM-DD} — {change summary}

| Dimension | Phase 1 | Phase 2 | Actual |
|-----------|---------|---------|--------|
| Risk Level | P{x} | P{y} | P{z} |
| Affected domain count | {n} | {n} | {n} |
| Cross-domain calls | {n} | {n} | {n} |
| MQ Topics | {n} | {n} | {n} |
| External systems | {n} | {n} | {n} |

**Determination**: {Accurate / Over-alert / Missed / Minor deviation}
**Deviation cause**: {one-line explanation; write "—" if no deviation}

---
```

> If file does not exist, first copy initial template from `templates/calibration-log.md` (or create an empty file with header).

---

## Step 5: Append to calibration-history.md

Path: `.claude/ecw/state/calibration-history.md` (configurable via ecw.yml `paths.calibration_history`).

If the file does not exist, create it with header:

```markdown
# Calibration History

> Auto-appended by Phase 3. Phase 1 reads recent entries as prediction reference.

---
```

Append format:

```markdown
### {YYYY-MM-DD HH:mm} — {change summary}

- **Predicted**: P{x}
- **Actual**: P{z}
- **Determination**: {Accurate / Over-alert / Missed / Minor deviation}
- **Cause**: {one-line deviation cause; "—" if accurate}
- **Keywords**: {Phase 1 keywords that triggered original classification}

---
```

> **Write failure handling**: Retry once → still fails: output content in conversation and continue workflow. This file is supplementary; failure does not block Phase 3.

---

## Step 6: Extract Instinct

Path: `.claude/ecw/state/instincts.md` (configurable via ecw.yml `paths.instincts`).

Instincts are lightweight heuristic rules that SessionStart hook injects into future sessions when confidence is high enough.

**Extraction rules:**

| Determination | Instinct Extraction |
|---------------|-------------------|
| **Missed** (under-predicted) | Pattern: "when keywords [{keywords}] appear" → Action: "consider raising level by 1" → base confidence: 0.5 |
| **Over-alert** (over-predicted) | Pattern: "when keywords [{keywords}] appear" → Action: "consider lowering level by 1" → base confidence: 0.5 |
| **Accurate** | If a matching instinct exists (same keywords), increase confidence by 0.1 (cap 1.0) |
| **Minor deviation** | No instinct extraction |

**Update rules:**
- Before writing a new instinct, scan existing entries for keyword overlap (≥50% keyword match = same instinct)
- If a matching instinct exists: increase confidence by 0.15 (cap 1.0), update `Updated` date
- New instinct starts at confidence 0.5

**File format** (if file does not exist, create with header):

```markdown
# Risk Classification Instincts

> Auto-managed by Phase 3. SessionStart injects entries with confidence > 0.7.
> Do not edit manually — scores are calibrated by repeated observations.

---
```

Each instinct entry:

```markdown
<!-- INSTINCT -->
- **Pattern**: {when these keywords/modules appear}
- **Action**: {consider raising/lowering level by 1}
- **Confidence**: {0.0-1.0}
- **Source**: {YYYY-MM-DD calibration: {determination} — {one-line cause}}
- **Updated**: {YYYY-MM-DD}
```

> **Robustness**: If the file cannot be written, skip silently. Instinct extraction is best-effort and does not block Phase 3.
