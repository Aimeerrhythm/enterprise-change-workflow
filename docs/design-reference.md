# ECW Design Reference

Advisory guidance for ECW contributors. Not enforced by lint — see `templates/rules/common/ecw-development.md` for mandatory rules.

## Token Budget Guidelines

| Skill Type | Target | Examples |
|-----------|--------|---------|
| Simple single-step | ~2,500 tokens | cross-review |
| Standard multi-step | ~4,000 tokens | requirements-elicitation, tdd, biz-impact-analysis |
| Complex orchestrator | ~5,000 tokens | risk-classifier, impl-orchestration |

Run `python3 tests/static/lint_skills.py --check tokens` for current actual values. Warning threshold is 20,000 tokens.

## Model Selection Guidelines

| Model | Use When | Examples |
|-------|----------|---------|
| opus | Deep reasoning, adversarial review, cross-domain analysis | spec-challenge, biz-impact-analysis, domain-collab Round 1 |
| sonnet | Implementation, mechanical execution | implementer, TDD cycle subagent, spec-reviewer |
| haiku | Reserved for lightweight mechanical tasks | Not currently used |

**Principle**: Reasoning density determines model choice, not task "importance". A simple but critical config change still uses sonnet; a complex analysis of a P3 change still uses opus.

Model defaults are configured in `ecw.yml` under `models.defaults.*` and can be overridden per-project.

## Context Management

- **New session threshold**: Consider splitting when context exceeds ~100K tokens
- **State source of truth**: `session-state.md` is the sole cross-session recovery state
- **PreCompact hook**: Automatically saves checkpoints — skills don't need manual checkpoint logic
- **`Next` field**: Each skill updates this before handoff; pre-compact and session-start hooks use it for precise recovery

## Subagent Scale Classifications

| Scale | Token Range | Typical Use |
|-------|------------|-------------|
| small | <20K tokens | Single-file analysis, targeted verification |
| medium | 20-80K tokens | Multi-file scanning, domain analysis |
| large | >80K tokens | Global analysis with multiple knowledge files |

Used in Subagent Ledger entries for capacity planning and timeout calibration.

## Prompt Engineering Tips

### Lost-in-Middle Effect

Place critical instructions at the **beginning** and **end** of prompts. Information in the middle receives less attention. For long agent prompts, the Boundary block goes near the end as a final reinforcement.

### Structured Output

Specify output format explicitly (tables > prose). When the agent must return data, use YAML with a defined schema. When the agent produces a report for humans, use Markdown with required section headers.

### Common Rationalizations Pattern

Pre-block Claude's common self-rationalization paths with a "Your Thought → Reality" table. Each entry addresses a specific way the model might shortcut the skill's protocol. Keep entries unique per skill — shared anti-patterns belong in a common location, not duplicated.

### Subagent Boundary Blocks

Every agent template needs an explicit boundary declaration:
1. Identity statement ("You are a single-task agent")
2. Prohibition ("Do not invoke/load/spawn other skills")
3. Scope limit ("Your only job is...")

Without this, agents may attempt to invoke skills or dispatch sub-agents beyond their scope.
