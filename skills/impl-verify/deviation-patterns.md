# Common Implementation Deviation Patterns

For focused attention in each Round:

| Pattern | Round | Example |
|---------|-------|---------|
| **State machine transition missing** | 1, 2 | Requirement defines A→B→C, code allows direct A→C jump |
| **Validation rule omitted** | 1, 2 | Requirement says "quantity must be positive", code has no check |
| **Error handling mismatch** | 1, 3 | Plan says "rollback on failure", code swallows exception |
| **Calculation formula error** | 1 | Requirement: price × qty - discount, code: (price - discount) × qty |
| **Scope creep** | 1 | Code adds functionality not required by requirements |
| **Idempotency missing** | 2 | New MQ consumer has no deduplication, violating business-rules.md idempotency section |
| **Cross-domain contract violation** | 2 | Code directly calls cross-domain internal method, not going through document-defined Facade |
| **Reuse decision not followed** | 3 | Plan specifies reusing existing method, code re-implements it |
| **Test scenario omitted** | 3 | Plan lists normal/exception/boundary 3 test scenarios, only normal scenario test written |
| **Assertion missing** | 3 | Plan requires verifying failure return, test only prints result with no assert |
| **Mock abuse** | 3 | Mocked the output of the dependency being tested — test is testing Mock behavior, not real code |
| **Layering violation** | 4 | Controller directly calls Mapper, bypassing Service layer |
| **Resource leak** | 4 | Database connection/file handle not closed in finally |
| **Severe duplication** | 4 | 50+ lines of identical logic with another class — should extract common method |
