---
name: java-coding-style
description: Java-specific coding style rules — extends common/coding-style
scope: java
paths: ["*.java"]
extends: common/coding-style
---

# Java Coding Style Rules

> Extends `common/coding-style.md`. All common rules apply unless overridden below.

## 1. Modern Java Constructs

- **Records**: Use `record` for immutable data carriers (DTOs, value objects) instead of classes with manual equals/hashCode/toString
- **Sealed classes**: Use `sealed` + `permits` for closed type hierarchies (state enums, command types)
- **Pattern matching**: Prefer `instanceof Pattern` over cast-after-check
- **Text blocks**: Use `"""` for multi-line strings (SQL, JSON templates)

## 2. Optional Usage

- Return `Optional<T>` from methods that may not produce a result — never return `null`
- Do not use `Optional` as a method parameter or field type
- Prefer `orElseThrow()` with a descriptive exception over `get()`
- Chain: `map` → `filter` → `orElse` is fine; do not nest `Optional` inside `Optional`

## 3. Stream Operations

- **Limit**: Maximum 5 chained stream operations — beyond that, extract intermediate variables or helper methods
- Do not use streams for side effects only — use a for-loop if the purpose is mutation
- Prefer `toList()` (Java 16+) over `collect(Collectors.toList())`
- Parallel streams: only for CPU-bound operations on large collections (>10k elements) with no shared mutable state

## 4. Spring Conventions

- **Constructor injection**: Prefer `@RequiredArgsConstructor` (Lombok) or explicit constructor over `@Autowired` on fields
- **Transaction boundaries**: `@Transactional` belongs on the service layer, not on repository or controller
- **Exception handling**: Use `@ControllerAdvice` for global exception mapping — do not catch and re-throw in every controller method
- **Configuration**: Use `@ConfigurationProperties` for groups of related settings, not scattered `@Value` annotations

## 5. Null Safety

- Annotate nullable return types with `@Nullable` — callers must handle the null case
- Use `Objects.requireNonNull()` at public API boundaries for required parameters
- Prefer empty collections (`Collections.emptyList()`) over `null` for "no results"

## 6. Naming — Java Specific

- **Interfaces**: Do not prefix with `I` (use `OrderService`, not `IOrderService`)
- **Implementations**: Suffix with `Impl` only when there is a genuine interface contract with multiple implementations
- **Test classes**: Mirror source class name + `Test` suffix (`OrderService` → `OrderServiceTest`)
- **Builder/Factory**: Name the method `of()`, `from()`, or `create()` — not `build()` when it is a static factory
