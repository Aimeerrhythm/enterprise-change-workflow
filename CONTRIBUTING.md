# Contributing to ECW

Conventions and processes for all contribution types.

## Repository Structure

```
skills/           — SKILL.md prompt files (one directory per skill)
agents/           — Standalone subagent definition files
commands/         — User-invocable command definitions (/ecw-init, etc.)
hooks/            — Python hook scripts (dispatcher architecture; no global registration)
templates/        — Configuration and knowledge file templates
  └── rules/      — Engineering rule templates (common/ + language-specific/)
docs/             — Architecture spec and component reference
tests/
  ├── static/     — Static linting, hook unit tests, contract & simulator tests
  └── eval/       — Behavioral eval via promptfoo + chain harness
```

## Contribution Types

### Adding or Modifying a Skill

1. **SKILL.md structure**: YAML frontmatter with `name` (matching directory name) and `description` fields.

2. **Subagent dispatch conventions** (see `.claude/ecw-patterns/conventions.md`):
   - Specify `model: {haiku|sonnet|opus}` on every subagent dispatch
   - Include error handling: failure → Ledger record + user notification + degraded path
   - Include termination conditions for loops: max rounds + no-improvement escalation
   - Write checkpoints to `session-data/` after each Round/Phase completes

3. **Cross-references**: Use `ecw:skill-name` format. The linter validates all references resolve.

4. **Testing**: Run `make lint` + `make eval-quick` after modifying a SKILL.md. Add/update anchor keywords in `tests/static/anchor_keywords.yaml` if new critical terms are introduced.

### Adding or Modifying a Hook

1. **Language**: Python 3.8+
2. **Entry point**: `def main():` reading JSON from `sys.stdin`
3. **Output**: JSON to stdout — `{"result": "continue"}`, `{"result": "continue", "systemMessage": "..."}`, or `{"result": "block", "reason": "..."}`
4. **Error handling**: See `docs/component-design-patterns.md` §7. Hooks must never block the workflow due to their own bugs.
5. **Logging**: stderr only (`sys.stderr.write`), never stdout (reserved for JSON output)
6. **Registration**: hooks are registered project-level via `scripts/merge-settings.py` into `.claude/settings.json`. `hooks/hooks.json` is intentionally empty — do not add entries there.
7. **Testing**: Create `tests/static/test_{hook_name}.py`

### Adding Engineering Rules

1. **Location**: `templates/rules/common/` for universal, `templates/rules/{language}/` for language-specific
2. **Format**: YAML frontmatter with `name`, `description`, `scope`, `paths`, optional `extends`
3. **Scope**: Actionable and verifiable — "do X" or "do not do Y" with clear boundaries
4. **Update README**: Add new rules to `templates/rules/README.md`

### Adding Templates

- Use `{{PLACEHOLDER}}` for values the user must fill
- Keep templates self-contained — understandable without reading external docs

## Development Workflow

### Running Tests

```bash
cd tests

make lint            # Static structure validation (<3s, $0)
make test-hook       # Hook unit tests (<10s, $0)
make test-contracts  # Data contract tests (<5s, $0)
make test-simulator  # Workflow simulator tests (<5s, $0)
make eval-quick      # P0 scenario behavioral eval (~2min, ~$0.50)
make all             # Full suite: lint + tests + eval-quick
```

### Code Quality

```bash
make lint-md         # Markdown linting (requires markdownlint-cli)
make lint-py         # Python linting (requires ruff)
```

### Commit Conventions

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

Semantic versioning:

- **Major**: Breaking changes to ecw.yml format, hook API, or Skill interface contracts
- **Minor**: New Skills, new rule sets, new hook capabilities
- **Patch**: Bug fixes, documentation improvements, rule content updates

Version tracked in `package.json`. Update `CHANGELOG.md` with every release.

## Review Checklist

### Functional

- [ ] `make all` passes
- [ ] `make test-hook` passes (if hooks were modified)
- [ ] `make test-contracts` passes (if data contracts or SKILL.md I/O changed)
- [ ] No new warnings in `lint_skills.py` output
- [ ] `docs/artifact-reference.md` updated if new artifacts or required files were added
- [ ] `templates/ecw.yml` updated if new configuration keys were introduced

### Architecture Compliance (mandatory for hook/skill changes)

- [ ] **State Ownership**: `grep -rn "current_phase\|working_mode\|ECW:STATUS" skills/` returns 0 hits (excluding template files)
- [ ] **No Downstream Handoff**: `grep -rn "Downstream Handoff" skills/` returns 0 hits
- [ ] **Single Source**: Any new mapping/routing declared in `workflow-routes.yml`, not hardcoded in Python
- [ ] **Determinism**: If behavior MUST happen reliably, it's a Hook/script, not a Prompt instruction
- [ ] `docs/design-principles.md` 8 litmus tests pass
- [ ] `docs/component-design-patterns.md` anti-patterns not introduced

### Issue Writing (mandatory)

- [ ] Issue uses the appropriate template (bug.md / arch.md), all required sections filled
- [ ] Bug fixes: acceptance criteria cover all affected paths (not just the reproduction path)
- [ ] Bug fixes: affected file list verified via `grep` for completeness
- [ ] Architecture changes: impact analysis includes global search results, all hits modified in same PR
- [ ] Architecture changes: coupling elimination table filled (how many places need changing after refactor?)
- [ ] Architecture changes: regression guardrail defined (automated mechanism to prevent future omissions)
