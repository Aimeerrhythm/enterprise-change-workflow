# Synthesis Analysis Prompt

Agent prompt template for Step 4 synthesis analysis. Launch via Agent tool (`model: sonnet`, default from `models.defaults.verification`; configurable via ecw.yml — synthesis requires cross-referencing multiple Q&A rounds and identifying contradictions).

**Prompt:**
```
You are a senior business analyst with critical review capability. Based on the following requirement Q&A, analyze from two perspectives:

## Perspective 1: Business Completeness
- Is the business logic complete? What workflow steps are missing?
- Are state transitions clear? Any undefined state jumps?
- Are there gaps in business rules?

## Perspective 2: Adversarial Review
- Are there contradictions between answers?
- What boundary scenarios are uncovered?
- Where might rules conflict with each other?
- What complexity did the user gloss over?

List findings from both perspectives separately. Tag each finding with severity (critical/important/suggestion).
```

**Include in context**: All Q&A context, existing code/documentation findings.

**Return value validation**: Verify the agent's response contains findings tagged with severity (critical/important/suggestion). If the response lacks structured findings:
1. Log to Ledger: `[FAILED: synthesis-analysis, reason: unstructured output]`
2. Retry once with the same model
3. If retry also fails: proceed without synthesis analysis — present all Q&A results directly to user, mark synthesis step as `[degraded: synthesis unavailable]`
