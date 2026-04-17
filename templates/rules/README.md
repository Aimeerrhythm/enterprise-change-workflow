# ECW Rules System

Rules are engineering standards that apply **always** during implementation — regardless of whether a specific Skill is active. They complement Skill-level guidance by providing a baseline of quality expectations.

## Layer Override Model

```
Language-specific rules  (templates/rules/{language}/)
        ↓ overrides
Common rules             (templates/rules/common/)
```

When a language-specific rule file exists for the same topic (e.g., `coding-style.md`), it **extends** the common rule — inheriting all common constraints and overriding only where the language demands different behavior.

## Rule File Format

Each rule file uses YAML frontmatter:

```yaml
---
name: security
description: Pre-commit security checklist
scope: common          # common | java | go | typescript | python
paths: []              # empty = all files; or ["*.java", "*.go"] etc.
extends: common/security  # (language rules only) base rule to extend
---
```

## Installation

Rules are installed to the target project's `.claude/ecw/rules/` directory during `/ecw-init`. The `ecw.yml` `rules` section controls which rule sets are active.

## Available Rule Sets

### Common (all languages)

| File | Topic | Key Constraints |
|------|-------|----------------|
| `security.md` | Security | No hardcoded secrets, input validation at boundaries, dependency audit |
| `testing.md` | Testing | AAA pattern, no test interdependence, boundary coverage |
| `coding-style.md` | Code style | Function length, nesting depth, naming conventions |
| `performance.md` | Performance | N+1 query prevention, pagination, resource cleanup |
| `design-patterns.md` | Design patterns | Repository pattern, DTO boundaries, error propagation |

### Language-Specific

| Directory | Extends | Key Overrides |
|-----------|---------|--------------|
| `java/` | `common/*` | Records, Optional, Stream limits, Spring conventions |
| `go/` | `common/*` | gofmt, error wrapping, interface design, goroutine safety |
