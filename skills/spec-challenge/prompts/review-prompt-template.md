# Review Agent Prompt Template

When dispatching the spec-challenge agent, Coordinator first determines `{affected_domains}`:
- **Auto-trigger**: Get domain list from current session's domain-collab report or risk-classifier output
- **Manual trigger**: Extract domain keywords from document content, match against project CLAUDE.md domain routing table; if undeterminable, set to "please infer involved domains from document content"

**Model selection**: `model: opus` (default from `models.defaults.analysis`; configurable via ecw.yml). Reason: adversarial review demands the strongest reasoning to find blind spots, logical gaps, and missed edge cases in plan design.

Use the following prompt structure:

```
Please review a technical plan document.

## Document to Review

File path: {document file path}

Please read the file yourself to get the full content.

## Project Context

Read `.claude/ecw/ecw.yml` to get project.name, read ecw.yml `paths.domain_registry` to get domain list.
Project knowledge documents are in the directory specified by ecw.yml `paths.knowledge_root`.
Cross-domain call relationships are recorded in `cross-domain-rules.md` under ecw.yml `paths.knowledge_common`.

Domains involved in the plan: {affected_domains}
Read relevant knowledge files for the above domains as needed to verify plan accuracy. Do not read all knowledge files at once.

## Source Code Reading Limits (CRITICAL — prevent timeout)

Read at most **10 source files** total. For each file, prefer Grep with limited context (`-A 5`) over full Read. Only Read full files for core interfaces or classes that directly participate in the change. Do NOT read complete implementations of large service classes — read class signatures and method signatures only. Knowledge files do not count toward this limit.

## Review Requirements

Review each dimension (accuracy, information quality, boundaries & blind spots, robustness) one by one.
Strictly follow the prescribed output format for the review report.

Please output the review report in Chinese.
```

**Timeout**: 300s (adversarial review reads plan + multiple knowledge files). If Agent has not returned, terminate and offer retry (see Error Handling in SKILL.md).
