---
name: ecw-upgrade
description: Upgrade ECW configuration in your project. Scans all migrations, applies pending ones via idempotent checks, with user confirmation.
---

# ECW Upgrade — Project Configuration Upgrade

You are executing the `/ecw-upgrade` command. Your task is to scan all available migrations, determine which are already applied and which are pending via idempotent checks, then apply pending changes step by step. Follow the steps below strictly in order — do not skip steps.

**Important:** This command belongs to the `enterprise-change-workflow` plugin. All templates and migration files referenced below are in the plugin's `templates/` directory. Read them using the Read tool from the plugin installation path (i.e., `templates/` under the parent directory containing this `commands/` folder).

---

## Step 0: Prerequisite Check

Check if `.claude/ecw/ecw.yml` exists. If not:

```
ECW not initialized. Please run /ecw-init first to initialize project configuration.
```

Then stop.

---

## Step 1: Scan Migrations & Detect Pending Items

### 1a: List All Migrations

Scan plugin `templates/upgrades/` directory, list all subdirectory names (each subdirectory name is a version number). Sort by version ascending.

```bash
ls templates/upgrades/
```

### 1b: Per-Version Idempotent Detection

For each migration version (ascending), read `templates/upgrades/{version}/migration.md`, extract the **idempotent check** logic for each migration step and execute:

- Idempotent check passes (condition already met) → Tag as "already applied"
- Idempotent check fails (condition not met) → Tag as "pending"
- Step has unmet prerequisites → Tag as "not applicable"

### 1c: Summarize Results

Tally status of all migration steps.

**All "already applied" or "not applicable"** → Output:

```
ECW configuration is up to date. All migrations already applied. No action needed.
```

Then stop.

**Has "pending" steps** → Use `AskUserQuestion` to present:

```
ECW Configuration Upgrade — Pending migrations detected:

{version_1}:
  {overview content}
  Pending steps: {list pending step summaries}
  Skipped steps: {list already-applied steps}

{version_2} (if any):
  ...

Options:
  1. "Run upgrade (Recommended)" — Execute pending migration steps one by one
  2. "View details only" — Show detailed migration content without executing
  3. "Skip" — Do not run upgrade
```

If user selects "View details only": Read and display each migration's full `migration.md` content, then ask again whether to execute.

If user selects "Skip": Stop.

---

## Step 2: Execute Migrations Per Version

For each pending version (ascending), execute the following:

### 2a: Read Migration Definition

Read `templates/upgrades/{version}/migration.md`, extract each migration step from the `## Migration Steps` section.

### 2b: Collect User Input

Before executing any migration steps, collect all placeholder values first. Read all snippet files in the migration definition for placeholder (`{{...}}`) patterns, deduplicate, then collect via a single AskUserQuestion:

```
Configuration upgrade needs the following info:

1. Test base class name (Java default "BaseUnitTest", Go default "TestSuite")
2. Test module name (e.g., "wms-service", "app", "src")

Please provide (or press enter for defaults):
```

### 2c: Execute Steps Sequentially

Follow the order defined in the migration (A → B → C ...) for each step:

1. **Idempotent check**: Verify per the migration definition's check method. If already executed, output skip reason and continue to next step
2. **Condition check**: If the step has conditions (e.g., "Java only"), verify. If unmet, skip
3. **Read target file**: Use the Read tool to read the project's target file
4. **Read snippet template**: Read from plugin `templates/upgrades/{version}/`
5. **Replace placeholders**: Replace `{{...}}` with values collected in Step 2b
6. **Locate insertion point**: Follow the migration definition's guidance. Use Edit tool's old_string to match insertion location
7. **Apply change**: Use Edit or Write tool to apply the change
8. **Output result**:

```markdown
✓ Migration {step_id}: {description}
  - File: {file_path}
  - Operation: {insert/replace/append}
  - Change: {brief description}
```

**Error handling**:

- Target file does not exist → Output warning, skip step
- Edit tool's old_string match fails → Output "Cannot locate insertion point. Please manually add the following content to {file_path}:", then output snippet content
- Any step errors → Do not block subsequent steps; record error in final report

---

## Step 3: Verify & Summarize

### 3a: Run Configuration Validation

Prompt user that they can run `/ecw-validate-config` to verify post-upgrade configuration completeness.

### 3b: Output Upgrade Summary

```markdown
## ECW Configuration Upgrade Complete

### Executed Migrations

| Version | Step | Status | Details |
|---------|------|--------|---------|
| {version} | Migration A: {description} | {success/skipped (already applied)/skipped (not applicable)/failed} | {details} |
| {version} | Migration B: {description} | {success/skipped (already applied)/skipped (not applicable)/failed} | {details} |
| ... | ... | ... | ... |

### Changed Files

{list all modified file paths}

### Next Steps

1. **Review changes** — Browse the above files to confirm injected content meets expectations
2. **Customize configuration** — Adjust tdd config in ecw.yml per project needs (e.g., enable check_test_files)
3. **Replace placeholders** — Check if any `{{...}}` placeholders remain in injected content
4. **Run validation** — Execute `/ecw-validate-config` to confirm configuration completeness
```

---

## Error Handling

- If ecw.yml cannot be parsed, report error and stop (do not execute any migrations)
- If a migration step fails, record error then continue executing subsequent steps
- If a snippet template cannot be read, report "Cannot read migration template {path}. Plugin installation may be incomplete." and skip that step
