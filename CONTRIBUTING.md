# Contributing to ECW

Thank you for your interest in contributing to Enterprise Change Workflow. This guide covers the conventions and processes for all contribution types.

## Repository Structure

```
skills/           — SKILL.md prompt files (one directory per skill)
agents/           — Standalone subagent definition files
commands/         — User-invocable command definitions (/ecw-init, etc.)
hooks/            — Python hook scripts + hooks.json registration
templates/        — Configuration and knowledge file templates
  └── rules/      — Engineering rule templates (common/ + language-specific/)
docs/             — Design reference and advisory documentation
tests/
  ├── static/     — Static linting and unit tests (Layer 1)
  └── eval/       — Behavioral eval scenarios via promptfoo (Layer 2)
```

## Contribution Types

### Adding or Modifying a Skill

1. **SKILL.md structure**: Every SKILL.md must have YAML frontmatter with `name` (matching directory name) and `description` fields.

2. **Subagent dispatch conventions** (from `.claude/ecw-patterns/conventions.md`):
   - Specify `model: {haiku|sonnet|opus}` on every subagent dispatch
   - Include error handling: failure → Ledger record + user notification + degraded path
   - Include termination conditions for loops: max rounds + no-improvement escalation
   - Write checkpoints to `session-data/` after each Round/Phase completes

3. **Cross-references**: Use `ecw:skill-name` format. The linter validates all references resolve to existing skills.

4. **Testing**: After modifying a SKILL.md:
   - Run `make lint` — validates structure, cross-references, routing tables, and anchor keywords
   - Run `make eval-quick` — behavioral eval for P0 scenarios (requires `ANTHROPIC_API_KEY`)
   - Add/update anchor keywords in `tests/static/anchor_keywords.yaml` if new critical terms are introduced

### Adding or Modifying a Hook

1. **Language**: Python 3.8+ (consistent with existing hooks)

2. **Entry point**: `def main():` reading JSON from `sys.stdin`

3. **Output**: JSON to stdout:
   - Pass: `{"result": "continue"}`
   - Pass with message: `{"result": "continue", "systemMessage": "..."}`
   - Block: `{"result": "block", "reason": "..."}`

4. **Error handling**: Wrap `main()` in `try/except` — on error, output `{"result": "continue"}` and `sys.exit(0)`. Hooks must never block the workflow due to their own bugs.

5. **Logging**: Write to stderr (`sys.stderr.write`), never stdout (reserved for JSON output).

6. **Registration**: Register in `hooks/hooks.json` under the appropriate event type.

7. **Testing**: Create `tests/static/test_{hook_name}.py` with unit tests.

### Adding Engineering Rules

1. **Location**: `templates/rules/common/` for universal rules, `templates/rules/{language}/` for language-specific.

2. **Format**: YAML frontmatter with `name`, `description`, `scope`, `paths`, and optional `extends` fields.

3. **Scope**: Rules should be actionable and verifiable — "do X" or "do not do Y" with clear boundaries, not vague guidelines. See `templates/rules/common/ecw-development.md` for ECW internal development rules as an example.

4. **Update README**: Add new rules to the table in `templates/rules/README.md`.

### Adding Templates

Templates under `templates/` are copied to target projects during `/ecw-init`. Follow these conventions:

- Use `{{PLACEHOLDER}}` for values that must be filled by the user
- Use comments to explain each section's purpose
- Keep templates self-contained — a user should understand what to fill without reading external docs

## Development Workflow

### Running Tests

```bash
cd tests

# Layer 1: Static structure validation (<3s, $0)
make lint

# Layer 1b: Hook unit tests (<10s, $0)
make test-hook

# Layer 2: P0 scenario behavioral eval (~2min, ~$0.50)
make eval-quick

# Full suite
make all
```

### Code Quality

```bash
# Markdown linting (requires: npm install -g markdownlint-cli)
make lint-md

# Python linting (requires: pip install ruff)
make lint-py
```

### Commit Conventions

Use conventional commit format:

```
feat(scope): add new feature
fix(scope): fix a bug
docs(scope): documentation changes
refactor(scope): code restructuring
test(scope): add or update tests
chore(scope): maintenance tasks
```

Common scopes: `hooks`, `rules`, `skills`, `templates`, `devex`, `eval`

### Branch Naming

For organized development waves: `wave{N}/{category-slug}` (e.g., `wave1/rules-devex`)

## Versioning

ECW follows semantic versioning:

- **Major**: Breaking changes to ecw.yml format, hook API, or Skill interface contracts
- **Minor**: New Skills, new rule sets, new hook capabilities
- **Patch**: Bug fixes, documentation improvements, rule content updates

Version is tracked in `package.json`. Update `CHANGELOG.md` with every release.

## Review Checklist

Before submitting changes:

- [ ] `make lint` passes with no new errors
- [ ] `make test-hook` passes (if hooks were modified)
- [ ] No new warnings introduced in `lint_skills.py` output
- [ ] CLAUDE.md updated if new Skills, Artifacts, or Required Files were added
- [ ] `templates/ecw.yml` updated if new configuration keys were introduced
- [ ] Cross-references between Skills validated (linter checks this)
