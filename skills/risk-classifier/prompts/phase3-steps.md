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

## Steps 4-6: Persist Calibration Records

After outputting calibration suggestions (Step 3), persist results to three files. Read `./phase3-calibration-formats.md` for the exact format of each:
- Step 4: Append to `calibration-log.md` (full-dimension comparison log)
- Step 5: Append to `calibration-history.md` (quick-lookup structured index for Phase 1)
- Step 6: Extract/update instincts in `instincts.md` (heuristic rules for future predictions)

> Write failure handling for all three: Retry once → still fails → output content in conversation and continue workflow.
