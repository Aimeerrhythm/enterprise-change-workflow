# Plan Quality Checks

## No Placeholders

Every step must contain the actual content. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may read tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Design Completeness Check

Before saving the plan, verify ALL open design questions are resolved. The plan must be **self-contained for TDD execution** — if the TDD phase would need to ask "how should this work?", the plan is incomplete.

**Checklist — resolve each applicable item before saving (skip items that don't apply to this change):**
- [ ] Data storage approach decided (new table vs. extend existing, field types)
- [ ] Field naming and data format specified (JSON structure, enum values, etc.)
- [ ] Configuration strategy defined (Nacos key names, default values, fallback behavior)
- [ ] Error codes and messages specified (exact code values, message text)
- [ ] External API contracts confirmed (method signatures of called services)

If any item has open questions, use **AskUserQuestion** to resolve them NOW. Do not save a plan with unresolved design decisions — TDD will inherit the ambiguity and waste turns re-asking.

## Self-Review

After writing the complete plan, review with fresh eyes:

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search for red flags — any patterns from the "No Placeholders" section. Fix them.

**3. Type consistency:** Do types, method signatures, and property names in later tasks match earlier definitions? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

**4. TDD readiness:** Could the TDD phase write tests from this Plan without reading any additional source files beyond the ones listed in each Task's **Files** and **Test Context** sections? If not, add the missing file paths, interface signatures, and import context.

If you find issues, fix them inline.

## Common Rationalizations

| Your Thought | Reality |
|-------------|---------|
| "The requirement is clear enough, skip design completeness check" | Unclear requirements become bugs during TDD. Every unresolved question costs 10x more to fix in implementation than in planning. |
| "I'll add details during implementation" | Plans with gaps produce implementations with gaps. The engineer reading this plan has zero context — they need everything spelled out. |
| "Similar to Task N is good enough" | The engineer may read tasks out of order. Repeat the code. DRY applies to production code, not plan documentation. |
| "This step is obvious, no code block needed" | Nothing is obvious to an engineer with zero project context. If a step changes code, show the code. |
| "TDD readiness check is overhead for simple plans" | Simple plans with missing test context cause TDD to waste turns discovering file paths and imports. Two minutes of checking saves twenty minutes of TDD thrashing. |
| "P2 plans don't need this level of detail" | P2 detail level is simplified, not absent. Task merging rules and 5-10 min granularity still apply. |
