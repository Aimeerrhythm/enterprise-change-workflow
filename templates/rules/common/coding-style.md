---
name: coding-style
description: Code style limits — function length, nesting depth, naming conventions
scope: common
paths: []
---

# Coding Style Rules

## 1. Function Length

- **Limit**: 50 lines per function/method (excluding blank lines and comments)
- If a function exceeds 50 lines, extract helper methods with descriptive names
- Exception: data mapping functions (DTO converters) and switch/match blocks with many cases

## 2. File Length

- **Limit**: 800 lines per source file
- If a file exceeds 800 lines, consider splitting by responsibility
- Configuration files and generated code are exempt

## 3. Nesting Depth

- **Limit**: 4 levels of nesting (if/for/try/lambda)
- Use early returns, guard clauses, and extracted methods to reduce nesting
- Example: replace `if (condition) { ... long block ... }` with `if (!condition) return;`

## 4. Naming Conventions

- **Classes/Types**: PascalCase — describe what it *is* (`OrderService`, `PaymentResult`)
- **Functions/Methods**: camelCase or snake_case per language convention — describe what it *does* (`calculateTotal`, `validate_input`)
- **Boolean variables**: prefix with `is`, `has`, `can`, `should` (`isActive`, `hasPermission`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_MS`)
- Avoid abbreviations unless universally understood (`ctx`, `req`, `err` are fine; `prcOrdSvc` is not)

## 5. Comments

- Do not add comments that restate the code (`// increment counter` above `counter++`)
- Add comments for *why*, not *what* — explain business decisions, workarounds, and non-obvious constraints
- TODO comments must include a tracking reference (ticket ID or author) — bare `TODO` without context is not allowed

## 6. Dead Code

- Delete unused functions, variables, imports, and commented-out blocks
- Do not keep "just in case" code — version control preserves history
- Do not rename unused parameters with `_` prefix to suppress warnings — remove the parameter if possible

## 7. Consistent Formatting

- Follow the project's existing formatter configuration (Prettier, gofmt, Black, etc.)
- Do not mix tabs and spaces within the same project
- Do not reformat files unrelated to your change (noise in diffs)
