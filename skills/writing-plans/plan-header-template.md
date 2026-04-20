# Plan Header Template

**Save plans to:** `.claude/plans/<feature-name>.md`

Every plan MUST start with this header:

```markdown
# [Feature Name] Implementation Plan

> **Risk Level:** P{N} | **Domains:** {domain list} | **Implementation Strategy:** {direct | subagent-driven}

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

**Implementation Strategy** is read from `session-state.md` `実装策略` field. If TBD or unavailable, determine by risk-classifier's "Implementation Strategy Selection" rules: Tasks ≤ 3 + files ≤ 5 = direct; Tasks 4-8 P0/P1 or Tasks > 8 = subagent-driven.
