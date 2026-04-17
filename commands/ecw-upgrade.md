---
name: ecw-upgrade
description: Upgrade ECW configuration in your project. Runs idempotent checks and applies missing configuration items.
---

# ECW Upgrade — Project Configuration Sync

You are executing the `/ecw-upgrade` command. Your task is to compare the project's ECW configuration against current plugin templates, fix everything you can, and auto-validate the result.

**Important:** This command belongs to the `enterprise-change-workflow` plugin. All templates are in the plugin's `templates/` directory. Read them using the Read tool from the plugin installation path (i.e., `templates/` under the parent directory containing this `commands/` folder).

---

## Step 0: Prerequisite Check

Check if `.claude/ecw/ecw.yml` exists. If not:

```
ECW not initialized. Please run /ecw-init first.
```

Then stop.

---

## Step 1: Run All Idempotent Checks

Read each project config file and compare against the current plugin template. For each check, determine status: **ok** (matches template structure) or **needs-fix** (outdated/missing/malformed).

### Check A: CLAUDE.md ECW Workflow Entry Point

**Why:** The plugin CLAUDE.md has a BLOCKING RULE instruction, but models prioritize project-level CLAUDE.md instructions (e.g., "read docs first") over plugin instructions. A project-level trigger is required to ensure `ecw:risk-classifier` fires automatically.

**Check:** Search project root `CLAUDE.md` for `ecw:risk-classifier`.

- Found → **ok**
- Not found → **needs-fix**: Insert before the domain routing section (before `## 域级知识路由` or similar). If no routing section, append to end.

```markdown
## ECW 工作流入口

收到变更需求、功能需求或 Bug 报告时，必须先执行 `ecw:risk-classifier` 进行风险分级，再开始任何分析或编码。
```

### Check B: ecw.yml Structure Sync

**Check:** Read project `.claude/ecw/ecw.yml` and plugin `templates/ecw.yml`. Compare:

1. **Missing sections** — If template has a top-level key (e.g., `tdd:`, `paths:`) that project file lacks, inject the section from template with default values.
2. **Missing fields within sections** — If template has fields inside a section (e.g., `paths.calibration_history`, `paths.instincts`) that project file lacks, add them with template defaults.
3. **Stale fields** — If project file has fields NOT in the template (e.g., `ecw_version:`), remove them.
4. **Preserve user values** — Never overwrite fields that exist in both template and project; only add missing ones.

For each fix, use Edit tool to surgically add/remove. Do not rewrite the entire file.

### Check C: CLAUDE.md TDD Reference

**Check:** Search project `CLAUDE.md` for "测试先行" or "TDD".

- Found → **ok**
- Not found → **needs-fix**: Search for a line containing `mvn test` (or language-equivalent test command). If found, replace with:

```
- **测试先行（TDD）**：新功能/Bug 修复必须先写失败测试，再写实现代码。编译通过不代表逻辑正确，测试通过才算完成
```

If no matching line found, skip.

### Check D: change-risk-classification.md Terminology

**Check:** Read project `.claude/ecw/change-risk-classification.md` and compare skill/tool names against the current plugin template.

- Search for stale names: `code-review` (should be `impl-verify`), `subagent-driven-development` (should be `impl-orchestration`), `executing-plans` (should be `impl-orchestration`).
- Found stale names → **needs-fix**: Replace with current names.
- No stale names → **ok**

### Check E: Domain Routing Table

**Check:** Verify that the project `CLAUDE.md` has a domain routing table (a markdown table with columns matching keyword/domain/entry-doc pattern).

- Has routing table → **ok**
- No routing table → **needs-fix**: Read plugin `templates/CLAUDE.md.snippet`, output the template content and instruct the user to fill in their project's domains. (Cannot auto-fix — requires project-specific domain knowledge.)

---

## Step 2: Present & Confirm

Tally results.

**All "ok"** →

```
ECW configuration is up to date. All checks passed.
```

Then jump to Step 4 (auto-validate).

**Has "needs-fix" items** → Use `AskUserQuestion`:

```
ECW Configuration Upgrade:

Auto-fixable:
{list each needs-fix check that can be auto-fixed, with brief description}

Manual action needed:
{list checks that need user input, e.g., Check E domain routing}

Skipped (already up to date):
{list ok checks}

Options:
  1. "Run upgrade (Recommended)" — Apply all auto-fixable items
  2. "Skip" — Do not run upgrade
```

---

## Step 3: Apply Fixes

Execute each needs-fix check's action in order. For each:

1. **Re-run idempotent check** (guard against concurrent changes)
2. **Read target file** with Read tool
3. **Apply change** with Edit tool
4. **Output result:**

```
✓ Check {ID}: {description}
  File: {file_path}
  Change: {brief description}
```

Error handling:
- Target file does not exist → Skip with warning
- Edit match fails → Output exact content for user to manually add
- Any error → Record, continue to next check

---

## Step 4: Auto-Validate

After all fixes (or if all checks passed), **automatically execute `/ecw-validate-config`** to verify the full configuration health. Do not ask the user — just run it.

Output the validation report directly as the final output of the upgrade command.
