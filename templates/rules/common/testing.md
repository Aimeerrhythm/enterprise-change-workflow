# Testing Rules

## Test Naming

- `[recommended]` Test names describe behavior: `test_{method}_{scenario}_{expected}`
- `[recommended]` Test class names match the class under test: `OrderServiceTest` for `OrderService`

## Assertions

- `[must-follow]` Every test must have at least one meaningful assertion
- `[must-follow]` Use specific assertions (`assertEqual`, `assertContains`) not generic (`assertTrue`)
- `[recommended]` One logical assertion per test — test one behavior at a time

## Test Isolation

- `[must-follow]` Tests must not depend on execution order
- `[must-follow]` No shared mutable state between test methods
- `[must-follow]` Clean up test data after each test (or use transactions/rollback)

## Mock Boundaries

- `[must-follow]` Only mock external systems (databases, APIs, message queues) — not internal classes
- `[recommended]` Prefer integration tests with real dependencies over extensive mocking
- `[recommended]` Mock at the boundary, not in the middle of the call chain

## Coverage Expectations

- `[must-follow]` P0 changes: 90%+ line coverage for new/modified code
- `[must-follow]` P1 changes: 80%+ line coverage for new/modified code
- `[recommended]` P2 changes: 70%+ line coverage for new/modified code
- `[recommended]` Critical business logic (state machines, payment, auth): 95%+ branch coverage

## TDD Compliance

- `[must-follow]` Test file committed before or with implementation (never after)
- `[must-follow]` Failing test must exist before writing production code (Red phase)
- `[recommended]` Each commit contains either test-only or test+implementation changes
