# Round Verification Checklists

Reasoning instructions for impl-verify subagents. Each Round subagent receives the checklist for its assigned Round.

---

## Round 1 — Requirements ↔ Code (Bidirectional Tracing)

**Goal**: Every requirement is correctly implemented; every code change has requirement backing.

**A→B Direction (Requirements→Code)**:

1. Extract all requirement items from requirement document (feature points, business rules, data changes, boundary conditions)
2. For each requirement, locate code implementation (file:line)
3. **Don't just confirm existence — verify logic**:
   - Do conditional branches match the requirement's conditions?
   - Are boundary values handled per requirements?
   - Do data changes match requirement-described fields/types/constraints?
   - Are error scenarios handled per requirements?
4. Tag results:
   - ✅ Correct — logic matches
   - ⚠️ Deviation — implementation differs from requirement (describe the deviation) → **must-fix**
   - ❌ Missing — not implemented → **must-fix**

**B→A Direction (Code→Requirements)**:

1. Scan all added/modified code in `git diff`
2. For each significant change (new method, modified logic, new class, new field), trace back to requirement or design decision
3. Tag results:
   - ✅ Has backing — maps to specific requirement item
   - ❓ No backing — no corresponding item in requirement document → **needs confirmation** (may be scope creep, or may be a reasonable implementation detail)

---

## Round 2 — Domain Knowledge ↔ Code (Rule Alignment)

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

**Goal**: Code implementation is consistent with domain-level business rules and data model.

**Operations**:

1. Locate the domain of changed code via `ecw-path-mappings.md`
2. Read that domain's `business-rules.md` and `data-model.md`. **Only read sections relevant to diff changes**: state machine section (if diff involves state changes), validation rules section (if diff involves validation logic), concurrency section (if diff involves lock operations), idempotency section (if diff involves MQ consumers). If unsure which sections are relevant, read the full file.
3. Compare item by item:

| Dimension | Reference Source | What to Check |
|-----------|-----------------|---------------|
| **State machine** | business-rules.md state machine section | Do code state transitions = document definitions? Any illegal jumps? Do side effects (notifications/MQ) match? |
| **Validation rules** | business-rules.md validation section | Does code validation logic = document constraints? Are required fields, value ranges, formats consistent? |
| **Concurrency control** | business-rules.md concurrency section | Does code lock pattern (optimistic/pessimistic/distributed) = document rules? |
| **Idempotency** | business-rules.md idempotency section | Do MQ consumers / API endpoints deduplicate per document? |
| **Data model** | data-model.md | Do new field types/constraints/defaults = document definitions? Do enum values = document enums? |
| **Cross-domain interaction** | business-rules.md cross-domain section | Do cross-domain calls go through document-defined Facade? Do parameters/return values match? |

4. Tag inconsistencies: deviation description + severity (**must-fix** or **suggestion**)

---

## Round 3 — Plan ↔ Code (Decision Verification)

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

**Goal**: Every design decision in the Plan is followed in code.

**Operations**:

1. Read Plan file, extract all design decisions (architecture choices, reuse directives, execution order, error handling strategy, test requirements)
2. Verify each:

| Decision Type | Verification Method |
|--------------|-------------------|
| Architecture choice | Plan says "use strategy pattern" → Did code use strategy pattern (not if-else chain)? |
| Reuse directive | Plan says "reuse XxxManager.doSomething()" → Did code call that method (not re-implement)? |
| Execution order | Plan says "send MQ after state change" → Is MQ send after state update? |
| Error handling | Plan says "log + alert on failure, don't block" → Does catch block implement this? |
| Test coverage | Plan listed test scenarios → Do corresponding test cases exist for all? |
| Test quality | Do tests include precise assertions (assertThat / assertEquals) rather than just println or Assert.notNull? |
| Test-first | Were test files produced before or in the same batch as implementation code? (reference git log; non-blocking hint) |

3. Tag deviations → **must-fix** (test-first is **suggestion** level, does not block convergence)

---

## Round 4 — Engineering Standards ↔ Code (Quality Review)

> Each subagent reads code changes independently using targeted `git diff -- {file}` for files relevant to its verification dimension.

**Goal**: Code quality meets project engineering standards. Absorbs code-reviewer responsibilities.

**Operations**:

1. Scan changed code against project existing patterns and engineering standards:

| Dimension | What to Check |
|-----------|---------------|
| **Naming consistency** | Do new class/method/variable names match project existing patterns? |
| **Duplicate code** | Are there opportunities to reuse existing methods? Any large duplications with other classes? |
| **Method complexity** | Does a single method have too many responsibilities and need splitting? Is nesting depth excessive? |
| **Layering violation** | Controller directly calling Mapper? Service directly operating HTTP request? |
| **Dependency direction** | Does it introduce reverse dependency (lower layer calling upper layer)? |
| **Error handling pattern** | Consistent with project existing error handling pattern (unified exception types, error code conventions)? |
| **Resource management** | Are database connections/file handles/streams properly closed? |

2. **Severity tagging**:
   - **must-fix**: Layering violations, resource leaks, severe duplication (50+ lines of identical logic), reverse dependencies
   - **suggestion**: Method too long, naming could be better, minor duplication, extractable but not urgent

If ecw.yml `rules.enabled: true`: pass engineering rules files from `rules.path` (default `.claude/ecw/rules/`) to the Round 4 subagent. Verification against `[must-follow]` rules → must-fix; `[recommended]` rules → suggestion.
