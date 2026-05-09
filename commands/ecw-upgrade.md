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

1. **Missing sections** — If template has a top-level key (e.g., `tdd:`, `paths:`, `auto_flow:`) that project file lacks, inject the section from template with default values.
2. **Missing fields within sections** — If template has fields inside a section (e.g., `paths.knowledge_root`, `tdd.enabled`) that project file lacks, add them with template defaults.
3. **Unknown fields** (info only) — If project file has top-level keys NOT in the template, report them but do NOT remove. User may have intentional custom extensions.
4. **Preserve user values** — Never overwrite fields that exist in both template and project; only add missing ones.

For each fix, use Edit tool to surgically add/remove. Do not rewrite the entire file.

### Check C: TDD Enabled for Java Projects

**Check:** Run `ls pom.xml 2>/dev/null` in project root to detect Java project.

- `pom.xml` not found → **skip** (non-Java project, TDD auto-enable not applicable)
- `pom.xml` found → Read project `.claude/ecw/ecw.yml`, check `tdd.enabled`:
  - `true` → **ok**
  - `false` or field missing → **needs-fix**: Set `tdd.enabled: true` using Edit tool

### Check D: Domain Routing Table

**Check:** Verify that the project `CLAUDE.md` has a domain routing table (a markdown table with columns matching keyword/domain/entry-doc pattern).

- Has routing table → **ok**
- No routing table → **needs-fix**: Read plugin `templates/CLAUDE.md.snippet`, output the template content and instruct the user to fill in their project's domains. (Cannot auto-fix — requires project-specific domain knowledge.)

### Check E: output_language Field

**Check:** Read project `.claude/ecw/ecw.yml`, look for `project.output_language` field.

- Field exists → **ok**
- Field missing → **needs-fix**: Add `output_language: "zh-CN"` under the `project:` section (after `language:` field). Use Edit tool to insert the line.

### Check G: hooks Configuration

**Check:** Read project `.claude/ecw/ecw.yml`, look for `hooks:` top-level section.

- Section exists → **ok**
- Section missing → **needs-fix**: Add the `hooks:` section from plugin `templates/ecw.yml` to the end of the project file.

### Check H: knowledge_maintenance Configuration

**Check:** Read project `.claude/ecw/ecw.yml`, look for `knowledge_maintenance:` top-level section.

- Section exists → **ok**
- Section missing → **needs-fix**: Read the `knowledge_maintenance:` section from plugin `templates/ecw.yml` and insert it after the `paths:` section in the project file. Preserve all default values.

### Check I: State & Knowledge-Ops Files

**Check:** Verify that runtime state files and knowledge-ops files created by ecw-init exist.

```bash
ls .claude/ecw/knowledge-ops/doc-tracker.md 2>/dev/null
```

For each missing file:
- `.claude/ecw/knowledge-ops/doc-tracker.md` → **needs-fix**: `mkdir -p .claude/ecw/knowledge-ops` then copy from plugin `templates/doc-tracker.md`.

### Check J: Write Permissions in settings.local.json

**Check:** Read `.claude/settings.local.json`. Verify `permissions.allow` array contains all three ECW write entries:
- `Write(.claude/ecw/**)`
- `Write(.claude/knowledge/**)`
- `Write(.claude/plans/**)`

Any missing entry → **needs-fix**: Merge into `permissions.allow` (create the file / array if it doesn't exist, never overwrite existing entries).

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

Tip: Changes are applied via Edit tool. If you want to revert, run `git checkout -- .claude/` after upgrade.

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

After all fixes (or if all checks passed), **update the `ecw_version` field** in project `.claude/ecw/ecw.yml` to match the current plugin version (read from plugin `package.json`). If the field doesn't exist, add it after the file header comments. Do this before validation so `session-start.py` version check passes on next session.

Then **automatically execute `/ecw-validate-config`** to verify the full configuration health. Do not ask the user — just run it.

Output the validation report directly as the final output of the upgrade command.
