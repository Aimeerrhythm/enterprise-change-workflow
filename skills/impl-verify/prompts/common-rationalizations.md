# Verification Discipline — Severity Definitions and Common Rationalizations

Reasoning guard for impl-verify subagents. Read this before tagging severity on any finding.

---

## Severity Definitions

| Severity | Definition | Blocks Convergence | Typical Scenarios |
|----------|-----------|-------------------|-------------------|
| **must-fix** | Not fixing will cause functional errors, data corruption, security vulnerabilities, or severe architectural issues | Yes | State machine missing transition, validation omission, exception swallowed, resource leak, layering violation, cross-domain contract violation |
| **suggestion** | Fixing improves code quality and maintainability but does not affect functional correctness | No | Method too long, inconsistent naming, minor duplication, extractable common method |

**Judgment principle**: If unsure whether it's must-fix or suggestion, ask yourself: **Will this issue cause a bug or incident in production?** Yes → must-fix. No → suggestion.

---

## Common Rationalizations — You Are Bypassing Verification

When these thoughts occur, **stop** — you are rationalizing skipping or weakening verification:

| Your Thought | Reality |
|-------------|---------|
| "This is a reasonable implementation detail, not a deviation" | If the requirement explicitly specifies behavior, implementation differences are deviations. Tag ⚠️ not ✅ |
| "The requirement was unclear, so it's not a miss" | Tag as ❓ needs confirmation, not ignore. Ambiguous requirements are risk, not exemption |
| "This must-fix doesn't really have much impact, let me tag it suggestion" | Return to severity definition: Will it cause a bug or incident in production? Yes → must-fix. Do not downgrade |
| "Round 4 is all suggestion-level, let me skip it" | Round 4 can also find resource leaks, layering violations — these are must-fix. Must execute |
| "Previous rounds were clean, later rounds are just formality" | Each round covers different dimensions. Round 1 passing does not mean Round 2 will pass |
| "Too many fixes, let me mark as passed and fix next time" | Convergence condition is zero must-fix, not "close enough." This is non-negotiable |
| "I didn't change this code, no need to verify" | Everything in git diff gets verified. Your changes may break assumptions of surrounding code |
| "Tests all pass, logic must be fine" | Tests passing ≠ logic correct. Tests may not cover that path. impl-verify checks logic, not test results |

**Iron law: Convergence condition (zero must-fix) cannot be achieved by the verifier self-downgrading severity. Only fixing code achieves convergence.**
