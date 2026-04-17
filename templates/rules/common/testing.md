---
name: testing
description: Testing standards — test structure, coverage expectations, and anti-patterns
scope: common
paths: []
---

# Testing Rules

## 1. Test Structure — AAA Pattern

Every test must follow Arrange-Act-Assert:

- **Arrange**: Set up test data and dependencies
- **Act**: Execute the operation under test (single call)
- **Assert**: Verify expected outcomes

One logical assertion group per test. Multiple related assertions on the same result object are fine; testing two unrelated behaviors in one test is not.

## 2. Test Independence

- Tests must not depend on execution order
- Tests must not share mutable state (reset between runs)
- Each test must set up its own fixtures or use fresh instances
- No `Thread.sleep()` or wall-clock waits — use countdown latches, polling with timeout, or test clocks

## 3. Boundary Coverage

At minimum, test:

- **Happy path**: Normal expected input produces correct output
- **Edge cases**: Empty input, null/nil, zero, max-length, boundary values
- **Error paths**: Invalid input triggers correct error handling (not a stack trace)

For state machines: test every valid transition and at least one invalid transition.

## 4. Naming Convention

Test names must describe what is being tested and the expected outcome:

- `test_cancel_order_already_shipped_throws_exception` (good)
- `testCancel2` (bad)
- `should return 404 when product not found` (good)

## 5. Test Data

- Use builder patterns or factory methods for complex test objects
- Do not hardcode magic numbers — use named constants or descriptive variables
- Fake/stub external dependencies; do not call production services in unit tests

## 6. Anti-Patterns to Avoid

- **Empty catch blocks in tests**: If an exception is expected, assert on it explicitly
- **Commented-out tests**: Delete them or fix them
- **Tests that always pass**: Assert on specific values, not just "no exception thrown"
- **Over-mocking**: If a test mocks more than 3 dependencies, consider an integration test instead
