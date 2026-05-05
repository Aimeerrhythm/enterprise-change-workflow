# Phase 3 Reasoning Steps

## Step 1: Compare Predicted vs. Actual

Extract actual impact metrics from biz-impact-analysis report, compare with Phase 1/Phase 2 predictions:

| Dimension | Phase 1 Predicted | Phase 2 Precise | biz-impact-analysis Actual | Deviation |
|-----------|------------------|-----------------|---------------------------|-----------|
| Affected domain count | {predicted} | {refined} | {actual} | {+/-N} |
| Cross-domain calls | {predicted} | {refined} | {actual} | {+/-N} |
| MQ Topics | {predicted} | {refined} | {actual} | {+/-N} |
| External systems | {predicted} | {refined} | {actual} | {+/-N} |
| End-to-end paths | {predicted} | {refined} | {actual} | {+/-N} |
| Changed file count | — | — | {actual} | — |

## Step 2: Determine Prediction Accuracy

Based on biz-impact-analysis actual impact scope, use the three-dimensional factor table (Impact Scope / Change Type / Business Sensitivity) in `change-risk-classification.md` to reverse-derive "actual appropriate level". Compare against Phase 2 level (if Phase 2 was executed) or Phase 1 level:

| Scenario | Determination |
|----------|--------------|
| Predicted level = actual appropriate level | **Accurate** |
| Over-predicted (e.g., P0 but actually only 1 domain, 0 MQ) | **Over-alert** |
| Under-predicted (e.g., P2 but actually 3+ domains, multiple MQ) | **Missed** |

## Step 3: Output Calibration Suggestions

**Before generating Phase 3 output**, Read `./phase3-output-template.md` for the three output format variants (significant deviation with suggestions, accurate prediction, minor deviation). Choose the variant matching the determination from Step 2.

## Steps 4-6: Persist Risk-Classifier Calibration Records

After outputting calibration suggestions (Step 3), persist results to three files. Read `./phase3-calibration-formats.md` for the exact format of each:
- Step 4: Append Risk Classification section to `calibration-log.md`
- Step 5: Append to `calibration-history.md` (quick-lookup structured index for Phase 1)
- Step 6: Extract/update risk-classifier instincts in `instincts.md` (under `## risk-classifier` section)

> Write failure handling for all three: Retry once → still fails → output content in conversation and continue workflow.

## Step 7: Collect Multi-Skill Calibration Data

Run the calibration data collection script to get structured metrics for all skill dimensions:

```bash
python3 {ecw_plugin_root}/scripts/calibration-collector.py {project_root} {session_data_dir}
```

Where:
- `{ecw_plugin_root}` = the directory containing this plugin (parent of `skills/`)
- `{project_root}` = the project being analyzed (read `ecw.yml` → project root)
- `{session_data_dir}` = `.claude/ecw/session-data/{workflow-id}/`

The script outputs YAML with four dimensions: `domain_calibration`, `plan_calibration`, `spec_challenge_calibration`, `requirements_calibration`. Each dimension has either `skipped: true` (prerequisite not met) or concrete data.

> If the script fails: note the failure in conversation and skip Steps 8-11. Risk-classifier calibration (Steps 4-6) is already persisted.

## Step 8: Domain Identification Calibration

**Skip if**: `domain_calibration.skipped: true`

Analyze the YAML output:
- `over_predicted`: domains predicted but no files changed → skill was too broad
- `missed`: files changed but domain not predicted → skill missed coverage

Append to `calibration-log.md` under `### Domain Identification` (read format from `./phase3-calibration-formats.md`).

**Instinct trigger**: If `missed` is non-empty in 3+ calibration records for the same domain pair → write instinct under `## domain-collab` in `instincts.md`.

## Step 9: Plan Accuracy Calibration

**Skip if**: `plan_calibration.skipped: true`

Analyze the YAML output:
- `task_ratio`: actual_commits / planned_tasks
  - > 1.5 → severe under-estimation
  - < 0.5 → over-decomposed
  - 0.7–1.3 → acceptable range
- `uncovered_files`: files changed but not listed in Plan

Append to `calibration-log.md` under `### Plan Accuracy`.

**Instinct trigger**: If `task_ratio` > 1.3 in 3+ calibration records → write instinct under `## writing-plans` in `instincts.md`.

## Step 10: Spec-Challenge Precision Calibration

**Skip if**: `spec_challenge_calibration.skipped: true`

Analyze the YAML output:
- `acceptance_rate`: accepted / (accepted + rejected)
  - < 0.5 → most findings rejected = low precision
  - > 0.8 → high precision

Append to `calibration-log.md` under `### Spec-Challenge Precision`.

**Instinct trigger**: If certain finding types have consistently high/low acceptance in 3+ records → write instinct under `## spec-challenge` in `instincts.md`.

## Step 11: Requirements Completeness Calibration

**Skip if**: `requirements_calibration.skipped: true`

Analyze the YAML output:
- `requirement_gap_count`: impl-verify findings with dimension=requirements
  - 0 → requirements-elicitation was complete
  - > 0 → gaps exist; list the specific findings

Append to `calibration-log.md` under `### Requirements Completeness`.

**Instinct trigger**: If requirement gaps appear in 3+ records for similar change types → write instinct under `## requirements-elicitation` in `instincts.md`.

## Step 12: Update Multi-Skill Instincts

For each skill section updated in Steps 8-11:
- Check calibration history (in `calibration-log.md`) for the dimension
- If a consistent pattern exists across ≥3 records and confidence ≥ 0.7 → write/update instinct entry
- Use `## {skill-name}` section format in `instincts.md` (e.g., `## domain-collab`, `## writing-plans`)
- Each instinct uses `<!-- INSTINCT -->` marker within its section (backward compatible with SessionStart)

Read `./phase3-calibration-formats.md` for the exact format of per-skill instinct entries.

> Steps 8-12 are best-effort. Any write failure: output content in conversation and continue.
