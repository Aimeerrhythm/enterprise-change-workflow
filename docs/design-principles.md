# ECW Architecture Specification

Defines ECW's architectural constraints. Each principle includes a rule statement and judgment criteria; anti-patterns are in `component-design-patterns.md` where applicable.

Full design rationale and derivation: `essays/design-principles-essay.md`.

---

## 1. Model Upgrade Test

**Rule: Invest in amplifiers, keep crutches lightweight and replaceable.**

### Criteria

| Amplifier | Crutch |
|-----------|--------|
| Orchestrates what models *cannot* do (governance, audit, compliance) | Compensates what models *currently* struggle with (format enforcement, step-by-step guidance) |
| Stronger model → better output | Stronger model → dead weight |

### Design Corollary

ECW defines **constraints** (what must happen), not **paths** (how to think).

- Compliant: "P0 changes must pass adversarial review before implementation"
- Violation: "When analyzing impact, first check direct deps, then transitive deps, then MQ chains..."

---

## 2. Process–Prompt Separation

**Rule: Process definitions are declarative and model-agnostic. Prompt engineering is replaceable without touching the workflow graph.**

### Criteria

A Skill file must not mix concerns with different lifecycles:

| Concern | Lifecycle | Separation method |
|---------|-----------|-------------------|
| Process logic | Durable (tied to governance) | `workflow-routes.yml` |
| Output templates | Medium (changes with consumers) | `templates/` |
| Thinking instructions | Short-lived (simplifies with model upgrades) | Inside SKILL.md |

### Anti-patterns

See `component-design-patterns.md` §1 anti-patterns, §3 new-Skill workflow.

---

## 3. Determinism over Probability

**Rule: Behavior that MUST happen reliably → implement as Hook/script/state machine, not Prompt instruction.**

### Criteria

Signals that a Prompt instruction should be mechanized:
- Appears 3+ times across Skill files (repetition = unreliable compliance)
- Uses emphasis words: "MUST", "CRITICAL", "NEVER" (emphasis = compensating for non-compliance)
- Violation causes workflow corruption (high consequence = needs guarantee)

### Anti-patterns

See `component-design-patterns.md` §1 design constraints.

---

## 4. Single Source of Truth

**Rule: Any fact, rule, or mapping is defined in exactly one authoritative location. Other locations reference, never redefine.**

### Criteria

Violation signals:
- Same mapping exists in both Python dict and YAML
- Same rule described in both SKILL.md and Hook code
- Changing one fact requires editing 2+ files

### Resolution

When duplication is found:
1. Identify the **authoritative source** (typically the one closer to the mechanism layer)
2. Other locations reference or derive from it
3. Verify: change one place → system behavior is automatically consistent

### Anti-patterns

- ❌ `workflow-routes.yml` defines routing AND Hook hardcodes a mapping table
- ❌ SKILL.md describes session-state field format AND Hook defines the same format
- ❌ Multiple SKILL.md files each describe "downstream handoff" rules

---

## 5. Risk Level Drives Everything

**Rule: Risk classifier is the core component. All downstream decisions (workflow depth, model selection, verification intensity) must reference its output.**

### Criteria

| Decision dimension | Must scale with risk level |
|-------------------|---------------------------|
| Workflow chain length | P0 full chain / P3 direct implementation |
| Model selection | Driven by reasoning density, not risk level alone (see `component-design-patterns.md` §9) |
| Verification depth | P0 multi-round impl-verify / P2 single round |
| Prompt verbosity | Low risk → lighter Prompt |

### Anti-patterns

- ❌ All risk levels get the same verification depth (wasteful or insufficient)
- ❌ Model selection based only on task type, ignoring risk level

---

## 6. State Ownership Inversion

**Rule: State write ownership is singular — program logic (Hooks) owns all writes, Prompts (SKILL.md) are always read-only.**

### Criteria

Which layer does a Prompt instruction belong to?

| Instruction | Belongs to |
|-------------|-----------|
| "Set `current_phase` to `plan-complete`" | Hook (state write) |
| "Compute implementation_strategy and record in session-state" | Skill (business logic artifact) |
| "Based on risk level, decide what to call next" | Hook (routing decision) |

### Responsibility Matrix

| | Skill | Hook |
|---|---|---|
| Produce artifacts | ✓ | — |
| Write session-state fields | ✗ | ✓ |
| Routing decisions | ✗ | ✓ |
| Inject read-only context | — | ✓ |

### Boundaries

- Applies: state co-managed by prompt and program logic
- Does not apply: Skill business logic output (e.g., risk-classifier creating initial session-state is artifact production)
- Gray area: template files retaining format strings is acceptable (defining artifact format ≠ writing state transitions)

### Anti-patterns

See `component-design-patterns.md` §1 anti-patterns, §3 declarative routing.

---

## 7. Document Loading Discipline

**Rule: Context window is a scarce resource. Auto-loaded content must pass three-criteria admission; everything else is loaded on-demand.**

### Admission Criteria (Layer 0 = CLAUDE.md)

Content enters CLAUDE.md only when it **simultaneously** satisfies:

1. **High frequency** — >50% of sessions need it
2. **Behavioral constraint** — it's a rule/constraint, not knowledge/reference/background
3. **Not derivable** — cannot be inferred from reading code or existing files

### Loading Layers

| Layer | Trigger | Content |
|-------|---------|---------|
| 0 | Every session (auto) | CLAUDE.md (hard rules + pointers) |
| 1 | Active workflow exists | session-state summary + instincts |
| 2 | On-demand when implementing | docs/ reference files |
| 3 | Never loaded | essays/, CHANGELOG |

### Anti-patterns

See `component-design-patterns.md` §8.

Implementation details (Memory admission, review mechanism): `component-design-patterns.md` §8.

---

## 8. Minimize File State

**Rule: Minimize file-based communication surface between components. Checkpoint I/O goes through unified API. Every checkpoint file must have a clear producer and consumer.**

### Criteria

- A checkpoint file whose only consumer is within the same Skill → no persistence needed
- A file with 2+ independent writers → needs marker partitioning or writer consolidation
- Before adding a file: who writes? who reads? can an existing file be reused?

### Anti-patterns

- ❌ Repeated "if file missing, log warning and degrade" across codebase (signal of weak contracts)
- ❌ Bypassing `CheckpointStore` / `marker_utils` with direct path manipulation
- ❌ Skill using `Edit` to append to marker section (writes beyond END marker)

---

## Litmus Test Quick-Check

Run through before implementing:

1. **Model upgrade** — Would a 10× smarter model still need this layer?
2. **Amplifier vs crutch** — Orchestrating what models can't do, or compensating what they temporarily struggle with?
3. **Determinism** — Must it happen reliably? Is it a mechanism or a Prompt?
4. **Single source** — Is this fact/rule defined in exactly one place?
5. **Risk proportionality** — Is overhead proportional to risk level?
6. **Write ownership** — Who owns this state change? "Both Prompt and Hook" = coupling.
7. **Loading discipline** — Is this content at the correct Layer?
8. **File state** — Does this checkpoint file need to exist? Who writes, who reads?
