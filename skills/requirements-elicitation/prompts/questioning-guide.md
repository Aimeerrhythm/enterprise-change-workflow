# Questioning Guide

## Questioning Dimension Checklist

You **must** consider every dimension below. Only skip a dimension when it is genuinely irrelevant to the current requirement.

### Business & Context
- What specific problem does this solve? Who requested it?
- What are the expected business outcomes or metric improvements?
- Who are the end users? Are different user roles involved?
- Priority and timeline?

### Process & Workflow
- What does the current workflow look like? Walk through step by step.
- Which steps change? What new steps are added?
- Are there approval flows, review steps, or handoffs?
- What triggers this process? What ends it?
- Are there parallel paths or conditional branches?
- How does this interact with existing workflows?

### Data Model & State
- What new entities, fields, or tables are needed?
- What existing data is modified or reinterpreted?
- What are the valid states and state transitions?
- Are there calculated or derived fields?
- Data retention and archival rules?

### Business Rules & Validation
- What validation rules apply to each field?
- What calculation logic is involved?
- Are there business constraints (min/max values, dependencies, mutual exclusions)?
- What formulas or algorithms drive the logic?
- Which rules are configurable vs. hardcoded?

### Inventory, Resources & Quantities
- Does this affect inventory, stock, or resource levels?
- Are there reservation, lock, or allocation mechanisms?
- How are quantity changes handled (increase, decrease, zero out)?
- Are there unit conversions or multi-warehouse considerations?
- How to handle backorders, pre-sales, or negative inventory?

### Edge Cases & Error Handling
- What happens if an operation fails midway?
- What if required data is missing or invalid?
- What if two users do the same thing simultaneously?
- What are the boundary conditions (zero, max, empty, overflow)?
- What if a dependent system is unavailable?
- Timeout and retry behavior?

### Migration & Compatibility
- How is existing data handled?
- Is a migration path or data backfill needed?
- Backward compatibility with existing features?
- Can this be rolled out in phases (feature flags, A/B testing)?

### Business Scenarios
- List all typical business scenarios involving this requirement
- How does processing logic differ across scenarios?
- Walk through each scenario step by step — are the rules the same?
- Are there seasonal, cyclical, or conditional variations?
- What real-world examples can the user provide?

### Acceptance Criteria
- How to verify the feature works correctly?
- What are the specific test scenarios?
- What does "done" look like?

## Questioning Discipline

### Rules

1. **3-5 questions per round** — Don't dump 20 questions at once
2. **Prioritize high-impact dimensions** — Business rules before UI details
3. **Follow up on every answer** — Each answer likely opens new questions
4. **Never assume** — If you're guessing, ask
5. **Reference existing code** — "I see the current `Order` model has X. Will this change?"
6. **Be specific** — "What happens when inventory hits zero at checkout?" not "How about edge cases?"
7. **Challenge vague answers** — "All users" → "Including admins? Guests? API callers?"

### Red Flags — You're Not Asking Enough

| Signal | Action |
|--------|--------|
| Fewer than 10 total questions asked | Almost certainly missed dimensions |
| No questions about edge cases | Go back and ask about failures, concurrency, boundaries |
| No questions about existing data | Ask about migration and backward compatibility |
| User said "etc." or "something like" | Follow up and expand — complexity hides in there |
| Felt ready to implement after one round | No. Keep asking. |
| No questions about what happens on failure | Every happy path has an unhappy path |

### When to Stop

Stop only when ALL of these are true:
- Every relevant dimension has at least one question asked and answered
- All follow-ups from answers have been exhausted
- You can write a complete requirement summary without guessing
- User confirms the summary is accurate

### Termination Limits

To prevent unbounded questioning, enforce these hard caps by risk level:

| Risk Level | Max Question Rounds | Max Total Questions |
|-----------|--------------------|--------------------|
| P0 | 15 | 75 |
| P1 | 10 | 50 |
| P2 (fallback) | 5 | 25 |

When hitting the cap: stop questioning, proceed to synthesis analysis with available information. Output `[Termination: max rounds reached, proceeding with collected information]`.
