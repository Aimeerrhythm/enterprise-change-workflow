# Task Structure Template

Each task follows this format:

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Test Context:**
- Test framework: {from pom.xml, e.g., JUnit 5 + MockitoExtension}
- Base test class: {from ecw.yml tdd.base_test_class, or "none"}
- Key dependencies for test: {list interfaces/classes the test needs to mock or import, with file paths}

- [ ] **Step 1: Write the failing test**

```java
@Test
void shouldBehaveAsExpected() {
    // given
    // when
    // then
    assertEquals(expected, result);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn test -pl <module> -Dtest=<TestClass>#<testMethod>`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```java
public ReturnType methodName(ParamType param) {
    return expected;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn test -pl <module> -Dtest=<TestClass>#<testMethod>`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Key Requirements

- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits
- Each step is one action (2-5 minutes)
