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

Append format (one workflow entry, with Risk Classification always present + optional skill sections):

```markdown
## Workflow: {workflow-id} ({risk-level} {mode} {domain-summary})

### Risk Classification
| Dimension | Phase 1 | Phase 2 | Actual |
|-----------|---------|---------|--------|
| Risk Level | P{x} | P{y} | P{z} |
| Affected domain count | {n} | {n} | {n} |
| Cross-domain calls | {n} | {n} | {n} |
| MQ Topics | {n} | {n} | {n} |
| External systems | {n} | {n} | {n} |

**Determination**: {Accurate / Over-alert / Missed / Minor deviation}
**Deviation cause**: {one-line explanation; write "—" if no deviation}

### Domain Identification
(skipped — single-domain, no domain-collab)
```

or when data available:

```markdown
### Domain Identification
| Metric | Value |
|--------|-------|
| Predicted | {domain list} |
| Actual | {domain list} |
| Over-predicted | {domain list or none} |
| Missed | {domain list or none} |
```

```markdown
### Plan Accuracy
| Metric | Value |
|--------|-------|
| Planned Tasks | {n} |
| Actual Commits | {n} |
| Task Ratio | {ratio} |
| Uncovered Files | {count} ({file list or none}) |
```

```markdown
### Spec-Challenge Precision
| Metric | Value |
|--------|-------|
| Total Findings | {n} ({fatal} fatal, {improvement} improvement) |
| Accepted | {n} |
| Rejected | {n} |
| Deferred | {n} |
| Acceptance Rate | {rate} |
```

```markdown
### Requirements Completeness
| Metric | Value |
|--------|-------|
| impl-verify Requirement Findings | {n} |
| Gaps | {none or finding summaries} |

---
```

> If file does not exist, create with header: `# ECW Calibration Log\n\n> Auto-appended by Phase 3.\n\n---\n`

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

Instincts are lightweight heuristic rules that SessionStart hook injects into future sessions when confidence is high enough. Multi-skill instincts (Issue #47) are stored in per-skill sections; auto-continue PreToolUse injects the relevant section when loading each skill.

**File format** (if file does not exist, create with header):

```markdown
# ECW Learned Instincts

> Auto-managed by Phase 3. SessionStart injects risk-classifier entries with confidence > 0.7.
> auto-continue PreToolUse injects per-skill entries when loading each skill.
> Do not edit manually — scores are calibrated by repeated observations.

---
```

**File structure — per-skill sections**:

```markdown
## risk-classifier

<!-- INSTINCT -->
- **Pattern**: {when these keywords/modules appear}
- **Action**: {consider raising/lowering level by 1}
- **Confidence**: {0.0-1.0}
- **Source**: {YYYY-MM-DD calibration: {determination} — {one-line cause}}
- **Updated**: {YYYY-MM-DD}

## domain-collab

(no instincts yet — insufficient calibration data)

## writing-plans

<!-- INSTINCT -->
- **Pattern**: {pattern for this project's planning}
- **Action**: {adjustment action}
- **Confidence**: {0.0-1.0}
- **Source**: {YYYY-MM-DD calibration}
- **Updated**: {YYYY-MM-DD}

## spec-challenge

(no instincts yet — insufficient calibration data)

## requirements-elicitation

(no instincts yet — insufficient calibration data)
```

**Extraction rules for risk-classifier (existing)**:

| Determination | Instinct Extraction |
|---------------|-------------------|
| **Missed** (under-predicted) | Pattern: "when keywords [{keywords}] appear" → Action: "consider raising level by 1" → base confidence: 0.5 |
| **Over-alert** (over-predicted) | Pattern: "when keywords [{keywords}] appear" → Action: "consider lowering level by 1" → base confidence: 0.5 |
| **Accurate** | If a matching instinct exists (same keywords), increase confidence by 0.1 (cap 1.0) |
| **Minor deviation** | No instinct extraction |

**Extraction rules for multi-skill instincts (new, Issue #47)**:

Write/update instinct in the corresponding `## {skill}` section when **≥3 calibration records** for this project show a consistent pattern with confidence ≥ 0.7:

| Skill | Trigger Condition | Pattern Format |
|-------|------------------|---------------|
| `domain-collab` | Same domain consistently missed/over-predicted | "order domain change often involves inventory domain" |
| `writing-plans` | `task_ratio` consistently > 1.3 | "Task estimates for {change_type} are typically under by {avg_ratio}x" |
| `spec-challenge` | Certain finding types consistently rejected | "{finding_type} findings have {acceptance_rate}% acceptance rate" |
| `requirements-elicitation` | Requirement gaps in ≥2 records for similar change type | "{change_type} requirements often miss {gap_pattern}" |

**Update rules (all skills)**:
- Before writing a new instinct, scan existing entries in the `## {skill}` section for keyword overlap (≥50% match = same instinct)
- If a matching instinct exists: increase confidence by 0.15 (cap 1.0), update `Updated` date
- New instinct starts at confidence 0.5
- Sections without enough data: write `(no instincts yet — insufficient calibration data)` instead of entries

> **Robustness**: If the file cannot be written, skip silently. Instinct extraction is best-effort and does not block Phase 3.
