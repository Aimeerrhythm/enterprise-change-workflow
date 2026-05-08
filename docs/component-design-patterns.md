# ECW Component Design Patterns & Engineering Constraints

Read relevant sections only (not the full document):

| What you're doing | Read |
|-------------------|------|
| Adding/modifying a Skill | §1 Hook Lifecycle, §3 Declarative Routing, §9 Skill Constraints |
| Modifying Hook logic | §1 Hook Lifecycle, §2 Markers, §7 Error Handling |
| Modifying state management | §2 Markers, §4 Read-Only Injection, §6 Checkpoint Store |
| Modifying calibration/Instincts | §5 Instincts |
| Managing documentation | §8 Document Loading Implementation |

---

## 1. Hook Lifecycle Model

ECW uses Claude Code's PreToolUse / PostToolUse hook mechanism for deterministic flow control.

### Sequence

```
User request → LLM decides to call Skill
            ↓
     ┌─── PreToolUse ───┐
     │ 1. Write in-progress state        │
     │ 2. Compute next skill             │
     │ 3. Inject read-only context       │
     │ 4. Inject instincts (if any)      │
     └──────────────────────────────────┘
            ↓
     Skill executes (LLM reads SKILL.md + performs business logic)
            ↓
     ┌─── PostToolUse ──┐
     │ 1. Write completed state          │
     │ 2. Compute remaining route        │
     │ 3. Inject auto-continue directive │
     └──────────────────────────────────┘
            ↓
     LLM sees systemMessage → immediately calls next Skill
```

### Design Constraints

| Constraint | Reason |
|-----------|--------|
| Hook never returns `{"result": "block"}` | Blocking a skill call breaks UX and is unrecoverable |
| Hook exceptions must be silently swallowed | `except: pass` — stale state is better than blocked workflow |
| PreToolUse does not inject "do not ask" | Some Skills (spec-challenge) have mandatory user confirmation |
| PostToolUse is the sole routing decision point | Skills themselves never decide "where to go next" |

### Anti-patterns

- ❌ Skill writes `current_phase` / `next` / `working_mode` (State Ownership Inversion)
- ❌ Hook hardcodes skill mapping table (should dynamically load from routes.yml)
- ❌ PreToolUse and PostToolUse both write the same field (race condition → inconsistent state)

---

## 2. Marker-Based Idempotent Section Updates

`marker_utils.py` core design: HTML comment markers partition a file into independently addressable sections.

### Format

```markdown
<!-- ECW:STATUS:START -->
risk_level: P0
auto_continue: true
routing: [writing-plans, spec-challenge, impl-verify]
<!-- ECW:STATUS:END -->
```

### Why Not Whole-File Overwrite

session-state.md is managed by multiple Hooks writing different sections (STATUS, MODE, LEDGER, TIMELINE, STOP). Whole-file overwrite = multi-writer race = data loss. Markers let each writer modify only its section.

### API

```python
# Read: precise extraction
parse_status(content) → dict
read_marker_section(content, name) → str

# Write: atomic replacement
update_status_fields(content, {"current_phase": "plan-loaded"}) → content
update_yaml_section(content, "LEDGER", data) → content

# Create/Append
append_ledger_entry(content, entry) → content   # inserts before END marker
append_timeline_entry(content, phase) → content  # auto-backfills previous duration
```

### Design Constraints

| Constraint | Reason |
|-----------|--------|
| YAML format (not Markdown) | LLM generates valid YAML easily; programs parse precisely |
| New sections auto-append to file end | Forward compatibility — old files without new section get it created |
| `append_ledger_entry` is the only entry point | Prevents LLM `Edit` from appending beyond END marker |

### Historical Failures

- Issue #36: LLM wrote Ledger after `<!-- ECW:LEDGER:END -->` → all hook parsers missed it
- Issue #33: LLM wrote `phase1-complete` vs Hook wrote `phase1-loaded` → same-field dual-write conflict
- Issue #40: Markdown→YAML migration required syncing 10+ SKILL.md format descriptions

**Root fix**: State Ownership Inversion — Skill never writes state, single writer only.

---

## 3. Declarative Routing Configuration

`workflow-routes.yml` is the Single Source of Truth for ECW's routing system.

### Design Philosophy

Routing rules are **governance artifacts** (organization decides what process P0 changes must follow), not technical implementation details. They should exist in a declarative, non-technical-reader-friendly format — not scattered across Python if-else branches.

### File Structure

```yaml
routes:           # Routing matrix (level × mode × type → chain)
skill_metadata:   # Per-skill metadata (mode, phase_name, aliases)
off_chain_skills: # Manual tool whitelist
impl_strategy:    # Implementation strategy decision rules
post_impl_tasks:  # Post-implementation task creation rules
```

### Dynamic Loading

```python
# Parse routes.yml at startup → generate 5 mapping tables
_mappings = _load_routes_from_file()
_SKILL_COMPLETED_PHASE = _mappings["completed_phase"]
_SKILL_MODE = _mappings["mode"]
_SKILL_ROUTING_ALIASES = _mappings["routing_aliases"]
_ROUTING_STEP_TO_SKILL = _mappings["step_to_skill"]
_OFF_CHAIN_ALLOWED = _mappings["off_chain"]
```

### Validation

- `test_data_contracts.py`: validates all route chain skills have corresponding directories
- `test_workflow_simulator.py`: simulates full traces, verifies must_include / must_exclude
- `test_dynamic_routes.py`: validates dynamic loading correctness

### Adding a New Skill

1. Create `skills/{name}/SKILL.md`
2. Add mode + phase_name to `skill_metadata` in `workflow-routes.yml`
3. If routing aliases exist (e.g., TDD:RED → ecw:tdd), add `routing_aliases`
4. Add to appropriate chain in `routes`
5. **No Python code changes needed**

---

## 4. Read-Only Context Injection

Skills need workflow state awareness (for decisions) but must not modify state (to avoid dual-write).

### Solution

PreToolUse hook injects a `systemMessage` when a Skill loads:

```
[ECW STATE — read-only] risk=P0, mode=planning, next=ecw:tdd, remaining=TDD:RED → impl-verify
```

The Skill reads this and knows the current context, but receives no "please write X" instructions.

### Design Points

| Point | Rationale |
|-------|-----------|
| Prefix `[ECW STATE — read-only]` | Explicitly tells LLM this is read-only info, not executable instructions |
| Compact format (one line) | Minimize token cost — injected on every Skill call |
| Merged with instincts | Same systemMessage contains state + historical calibration, reducing injection count |
| No injection when stateless | First risk-classifier call in new session has no session-state → nothing injected |

---

## 5. Instincts (Learned Rules) Design

Phase 3 Calibration produces heuristic rules stored in `instincts.md`, injected via PreToolUse to corresponding Skills.

### Architecture Position

```
Phase 3 output → instincts.md → parse_instincts() → PreToolUse injection → influences Skill decisions
```

### Design Constraints

| Constraint | Reason |
|-----------|--------|
| Partitioned by skill section | Different Skills' calibration data should not interfere |
| session-start injects only high confidence (≥ 0.7) | Low-confidence instincts may mislead |
| auto-continue injects all (no confidence filter) | Per-skill injection already provides precise routing |
| Unified parser `parse_instincts()` | Avoids two implementations drifting (Issue #62 fix) |

### Format

```markdown
## risk-classifier

<!-- INSTINCT -->
- **Pattern**: State machine changes get underestimated
- **Action**: +1 level when state transition keywords present
- **Confidence**: 0.85
- **Source**: 20260501-a3f1 calibration
```

---

## 6. Checkpoint Store Design

`CheckpointStore` class provides unified CRUD for session-data checkpoint files.

### Why Abstraction Is Needed

ECW has 15+ checkpoint file types. Each Hook/Skill needs to: find current workflow directory, check file existence, read/write files. Without abstraction = repeated path construction + error handling everywhere.

### API

```python
store = CheckpointStore.from_latest_workflow(cwd)  # find latest workflow
store.write("phase2-assessment", content)           # create dirs + write
content = store.read("knowledge-summary")           # None if missing
store.exists("impl-verify-findings")                # bool
store.list()                                        # ["session-state", ...]
```

### Design Points

- **workflow-id isolation**: each workflow has independent subdirectory (`{YYYYMMDD}-{xxxx}`)
- **from_latest_workflow()**: auto-finds latest directory, Hooks don't need specific workflow-id
- **Create dirs on write**: `write()` internally calls `os.makedirs(exist_ok=True)`

---

## 7. Error Handling Strategy

Core principle: **Hook failures never block the workflow.**

### Layered Strategy

| Layer | Error handling | Reason |
|-------|--------------|--------|
| Hook top-level | `except: pass` + `{"result": "continue"}` | User operations must not fail due to hook bugs |
| State writes | `try/except` wrapped, failure = stale state but flow continues | Stale state costs less than blocked workflow |
| Config reads | Fallback defaults (e.g., missing risk_level → default P0) | Fail to safe side |
| File parsing | YAML parse failure → return None → caller decides | Don't propagate exceptions upstream |

### Anti-patterns

- ❌ `raise` in Hook causing Claude Code error
- ❌ `sys.exit(1)` terminating process
- ❌ Retry loops (Hooks have implicit time limits, retries may timeout)

### Logging, Not Assertions

Use `log_trace()` to record anomalies for post-hoc diagnosis. Never use `assert` for runtime interruption. `trace.jsonl` is a retrospective tool, not real-time monitoring.

---

## 8. Document Loading Implementation

> Principle definition: `design-principles.md` §7. This section covers admission criteria and review mechanisms.

### CLAUDE.md Admission Criteria

| Belongs in CLAUDE.md | Does NOT belong |
|---------------------|-----------------|
| "Skills never write state" | Per-skill descriptions (code has frontmatter) |
| "impl-verify runs before marking complete" | Full artifact path table (low-frequency lookup) |
| "workflow-routes.yml is sole routing source" | Per-skill trigger conditions (hook handles automatically) |

### Memory Admission Criteria

A memory entry must satisfy:

1. **Future action value** — not "what was done" but "what to follow next time"
2. **Not derivable from code/docs** — if `design-principles.md` already states it, memory is redundant
3. **Won't naturally expire** — project-type memories have shelf life, clean up when done

### Anti-patterns

| Anti-pattern | Consequence | Fix |
|-------------|-------------|-----|
| Full tables in CLAUDE.md | +1000 tokens/session, 99% unused | Externalize to docs/, one-line link in CLAUDE.md |
| Memory records "what was done" | Grows into history log, no action value | Only record "what to do next time", clean up completed |
| CLAUDE.md restates SKILL.md content | Dual maintenance, inevitable drift | CLAUDE.md says "rule exists", doesn't repeat content |
| All docs flat in CLAUDE.md | Can't distinguish "must follow" vs "reference" | Strict layering: Layer 0 = hard rules only |
| "Just in case" extra lines | Accumulates, CLAUDE.md bloats to 5000+ tokens in 6 months | Periodic review: "would removing this cause errors?" If no → remove |

### Periodic Review

Every 5 versions (or monthly):

1. `wc -c CLAUDE.md` — over 8000 chars (~2000 tokens) → needs trimming
2. Per Memory entry: "If deleted, would next session make mistakes?"
3. Per CLAUDE.md section: "How many of the last 10 sessions used this?" Below 30% → externalize
4. Check docs/ for orphan files not referenced by CLAUDE.md

---

## 9. Skill Engineering Constraints

Constraints for Skill authors: token budgets, model selection, and subagent boundaries.

### Token Budget

| Skill type | Target | Examples |
|-----------|--------|----------|
| Simple single-step | ~2,500 tokens | cross-review |
| Standard multi-step | ~4,000 tokens | requirements-elicitation, tdd, biz-impact-analysis |
| Complex orchestrator | ~5,000 tokens | risk-classifier, impl-orchestration |

Run `python3 tests/static/lint_skills.py` to check actual values (warning threshold: 20,000 tokens).

Over-budget root causes are usually SKILL.md containing content it shouldn't (routing logic, format descriptions, repeated anti-pattern lists). Audit against `design-principles.md` first, then consider "write shorter."

### Model Selection

| Model | Use case |
|-------|----------|
| opus | Deep reasoning: adversarial review, cross-domain analysis, Phase 2 precise grading |
| sonnet | Implementation execution: implementer, TDD cycle, spec-reviewer |
| haiku | Lightweight mechanical tasks (currently unused) |

**Principle**: Selection determined by reasoning density, not task "importance." Simple but critical config change = sonnet; complex P3 analysis = opus.

Defaults in `ecw.yml` `models.defaults.*`.

### Subagent Boundary Declaration

Every agent prompt must include:
1. Identity declaration ("You are a single-task agent")
2. Prohibitions ("Do not call/load/derive other skills")
3. Scope limits ("Your only job is...")

Missing declarations → agent attempts out-of-scope operations (historical: spec-challenge agent tried to self-invoke tdd).

### Context Management

- Recommend splitting to new session when context exceeds ~100K tokens
- `session-state.md` is the only cross-session state recovery mechanism
- PreCompact hook auto-saves checkpoints — Skills don't need manual checkpoint logic
