# Phase 2–4: Analysis, Hypothesis, and Implementation

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

1. **Find Working Examples** — Locate similar working code in same codebase
2. **Compare Against References** — If implementing pattern, read reference implementation COMPLETELY. Don't skim.
3. **Identify Differences** — What's different between working and broken? List every difference.
4. **Understand Dependencies** — What other components, config, environment does this need?

## Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form Single Hypothesis** — State clearly: "I think X is the root cause because Y." Be specific.
2. **Test Minimally** — Make the SMALLEST possible change. One variable at a time.
3. **Verify** — Did it work? Yes → Phase 4. No → form NEW hypothesis. Don't stack fixes.
4. **When You Don't Know** — Say so. Research more. Use AskUserQuestion to ask the user.

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

1. **Create Failing Test Case**
   - Simplest possible reproduction
   - Automated test if possible
   - MUST have before fixing
   - Follow `ecw:tdd` for proper test-first discipline: write the failing reproduction test (RED), then implement the fix to make it pass (GREEN), then refactor if needed
   - For risk level, refer to `ecw:tdd` enforcement table (Bug row = Mandatory)

2. **Implement Single Fix**
   - Address the root cause identified
   - ONE change at a time
   - No "while I'm here" improvements

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?
   - Issue actually resolved?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze with new information
   - **If >= 3: STOP and question the architecture (step 5 below)**

5. **If 3+ Fixes Failed: Question Architecture**

   Pattern indicating architectural problem:
   - Each fix reveals new shared state/coupling in different place
   - Fixes require massive refactoring
   - Each fix creates new symptoms elsewhere

   **STOP and question fundamentals:**
   - Is this pattern fundamentally sound?
   - Should we refactor architecture vs. continue fixing symptoms?
   - Suggest `ecw:risk-classifier --recheck` to re-evaluate risk level

   **Use AskUserQuestion to discuss with user before more fixes.**
