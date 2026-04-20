# Engineering Rules

Structured engineering standards referenced by ECW agents during implementation and verification.

## Structure

```
rules/
  common/               # Universal rules (all languages/projects)
    coding-style.md     # Naming, formatting, code organization
    security.md         # Security standards (OWASP, input validation)
    testing.md          # Testing standards (coverage, patterns, assertions)
    ecw-development.md  # ECW plugin internal development rules
  {language}/           # Optional language-specific rules (e.g., java/, go/)
```

## How Rules Are Used

- **implementer agent**: Reads applicable rules before implementing each task
- **impl-verifier agent (Round 4)**: Verifies code compliance against rules
- **impl-orchestration**: Includes rules path in implementer dispatch prompt

## Severity Levels

- `[must-follow]` — Violations produce **must-fix** findings in impl-verify Round 4
- `[recommended]` — Violations produce **suggestion** findings

## Configuration

In `ecw.yml`:

```yaml
rules:
  enabled: true                    # Set false to skip rules enforcement
  path: .claude/ecw/rules/         # Directory containing rules files
```

## Adding Custom Rules

1. Create a new `.md` file under the appropriate subdirectory
2. Use `[must-follow]` or `[recommended]` severity tags
3. Rules are automatically picked up by agents — no config change needed
4. Language-specific rules override common rules when both exist
