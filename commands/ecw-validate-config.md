---
name: ecw-validate-config
description: Validate ECW configuration files for completeness and correctness. Checks for unfilled placeholders, missing files, and broken references.
---

# ECW Configuration Validation

You are executing the `/ecw-validate-config` command. Your task is to check the project's ECW configuration completeness and correctness, then output a structured report. Follow the steps below strictly in order.

---

## Step 1: Locate Configuration

Check if `.claude/ecw/` directory exists. If not, report:

```
ECW not initialized. Please run /ecw-init first to initialize project configuration.
```

Then stop.

If the directory exists, read `ecw.yml`:

```bash
cat .claude/ecw/ecw.yml
```

Parse the `paths` section to get all configuration paths. If the paths section is missing, fall back to defaults.

---

## Step 2: Check ecw.yml

Read `.claude/ecw/ecw.yml` and check:

### 2a: Unfilled Placeholders

Search for unreplaced template placeholders:
- `project.name` still set to `"Your Project Name"`
- Values containing `{...}` patterns
- `component_types` still commented out (only default `Service` entry)

### 2b: Language Consistency

- `project.language` should match files in project root (pom.xml / build.gradle → java)
- `scan_patterns` values should be appropriate for the declared language

### 2c: Path Validity

For each path in the `paths` section, check whether the referenced file/directory exists:
- `domain_registry`
- `path_mappings`
- `knowledge_root`
- `knowledge_shared`

---

## Step 3: Check domain-registry.md

Read the domain registry file (path from ecw.yml or default `.claude/ecw/routing/domain-registry.md`).

### 3a: Empty Check

If the file contains no domain blocks (only template header), flag:
- "Domain registry is empty — no business domains registered"

### 3b: Per-Domain Validation

For each registered domain, extract:
- Domain ID
- Knowledge root path
- Entry document path
- Code root path

Check:
- **Does knowledge root exist?** — `ls {knowledge_root}/ 2>/dev/null`
- **Does entry document exist?** — Check if file at specified path exists
- **Does code root exist?** — `ls {code_root}/ 2>/dev/null`
- **Any remaining placeholders?** — `{{...}}` or `{your_...}` patterns

---

## Step 4: Check routing/path-mappings.md

Read the path mappings file (path from ecw.yml or default `.claude/ecw/routing/path-mappings.md`). This is routing metadata, not business knowledge.

### 4a: Empty Check

If the file has no mapping rows (header only), flag:
- "Path mapping table is empty — biz-impact-analysis and completion verification hook domain matching will rely on heuristics"

### 4b: Path Existence

For each mapping row (`| path_prefix | domain |`):
- Check if `path_prefix` directory exists in the project
- Check if `domain` is registered in domain-registry.md

Flag mismatches:
- Path does not exist → "Path `{path}` does not exist"
- Domain not registered → "Domain `{domain}` is not registered in domain-registry.md"

---

## Step 5b: Template Structure Sync Check

Check whether project ECW configuration files remain structurally consistent with current plugin templates. Template updates do not auto-upgrade already-integrated project configurations; this step detects structural drift.

**Important:** When reading templates, use the Read tool from the plugin installation path (i.e., `templates/` under the parent directory containing this `commands/` folder).

### 5b-1: domain-registry Field Completeness

Compare each domain definition's field set in the project domain-registry against the Scaffold template's standard field set:

Standard field set (from ecw-init Scaffold Step 3b):
- Domain ID, Display Name, Knowledge Root, Entry Document, Business Rules, Data Model, Code Root

For each registered domain:
- Check if Business Rules field is missing → Flag "missing business rules path"
- Check if Data Model field is missing → Flag "missing data model path"
- If field exists and value is not an annotation indicating no standalone file (see exemptions below), verify the referenced file exists

**Exemptions (do not flag as missing):** Field value contains "no standalone", "无独立文件", "内联", "见 ", "参见 ", or starts with `(` / `（`.

**Important:** Only check fields listed in domain-registry. Do NOT infer "migration needed" from the filesystem — if both a root-level file and a `common/` file exist, as long as domain-registry references an existing file the check passes. Never output migration suggestions.

### 5b-2: Output

For each detected difference, output:
- **Stale terminology** (warn): Project file uses terminology replaced in the template
- **Missing field** (warn): Domain definition missing a standard field
- **Broken reference** (fail): Field references a file that does not exist

---

## Step 6: Check Knowledge File Structure

### 6a: Knowledge Root

Check if knowledge root directory exists. If not, flag:
- "Knowledge root directory `{path}` does not exist"

### 6b: Common Knowledge

Check if `knowledge_shared` directory exists. If it exists, check standard files:
- `cross-domain-rules.md`
- `cross-domain-calls.md`
- `mq-topology.md`
- `shared-resources.md`
- `external-systems.md`
- `e2e-paths.md`

For each file: Check if it exists and whether content is still a template placeholder. A file is a placeholder if: it contains only comment lines (`<!-- ... -->`) and markdown headers (`# ...`), OR contains `{{...}}` tokens in data rows, OR contains `(暂无)` as the only data row. A file with at least one real data row (no placeholder tokens) is valid regardless of size.

### 6c: Domain-Level Knowledge

For each domain in the domain registry, check its knowledge directory:
- Does the directory exist?
- Does `00-index.md` (or configured entry document) exist?
- Are there `.md` files with actual content?

### 6d: Project-local ECW Hooks

Read project `.claude/settings.local.json`.

Validate that the project-local settings file contains ECW runtime hook registrations for these event points:

- `SessionStart` → `session-start.py`
- `Stop` → `stop-persist.py`
- `PreToolUse` → `dispatcher.py`
- `PostToolUse` → `post-edit-check.py`
- `PreCompact` → `pre-compact.py`
- `SessionEnd` → `session-end.py`

Also verify `permissions.allow` contains these three entries:
- `Write(.claude/ecw/**)`
- `Write(.claude/knowledge/**)`
- `Write(.claude/plans/**)`

Validation rules:
- `.claude/settings.local.json` missing → **fail**
- invalid JSON → **fail**
- missing required ECW hook command under any required event → **fail**
- missing required write permission → **warn**

Important:
- Only validate **project-local** `.claude/settings.local.json`.
- Do **not** inspect or depend on global `~/.claude/settings.json`.
- Ignore unrelated non-ECW hooks.

---

## Step 7: Output Report

Output structured validation report:

```markdown
## ECW Configuration Validation Report

### Summary

| Check Item | Status |
|-----------|--------|
| ecw.yml | {pass/warn/fail} |
| domain-registry.md | {pass/warn/fail} |
| path-mappings.md | {pass/warn/fail} |
| Template structure sync | {pass/warn/fail} |
| Knowledge file structure | {pass/warn/fail} |
| Project-local hooks | {pass/warn/fail} |

### Issue List

**Must fix (affects ECW functionality):**

{numbered list, or "None"}

**Suggested fix (improves accuracy):**

{numbered list, or "None"}

### Domain Health

| Domain | Registered | Knowledge Dir | Entry Doc | Business Rules | Data Model | Code Dir | Path Mapping |
|--------|-----------|--------------|----------|---------------|-----------|---------|-------------|
| {domain} | {ok/missing} | {ok/missing} | {ok/missing} | {ok/missing/no standalone file} | {ok/missing/no standalone file} | {ok/missing} | {ok/missing} |

### Recommended Actions

{prioritized list of fix recommendations}
```

Status definitions:
- **pass** — Configuration complete, no issues
- **warn** — Configuration exists but has items to improve (placeholders, empty files)
- **fail** — Configuration missing or severely broken

---

## Error Handling

- If a file cannot be read, record the error then continue checking other files.
- If ecw.yml cannot be parsed, report the parse error and fall back to default paths for remaining checks.
