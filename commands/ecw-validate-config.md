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

- `project.language` should match files in project root (pom.xml → java, go.mod → go, etc.)
- `scan_patterns` values should be appropriate for the declared language

### 2c: Path Validity

For each path in the `paths` section, check whether the referenced file/directory exists:
- `domain_registry`
- `risk_factors`
- `path_mappings`
- `knowledge_root`
- `knowledge_common`
- `calibration_log` (optional — may not exist yet; not an error)

---

## Step 3: Check domain-registry.md

Read the domain registry file (path from ecw.yml or default `.claude/ecw/domain-registry.md`).

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

## Step 4: Check ecw-path-mappings.md

Read the path mappings file (path from ecw.yml or default `.claude/ecw/ecw-path-mappings.md`).

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

## Step 5: Check change-risk-classification.md

Read the risk classification file.

### 5a: Placeholder Check

Search for unfilled placeholders:
- `{your_...}` patterns
- `{{...}}` patterns
- `TODO` / `TBD` markers

---

## Step 5b: Template Structure Sync Check

Check whether project ECW configuration files remain structurally consistent with current plugin templates. Template updates do not auto-upgrade already-integrated project configurations; this step detects structural drift.

**Important:** When reading templates, use the Read tool from the plugin installation path (i.e., `templates/` under the parent directory containing this `commands/` folder).

### 5b-1: Structural Comparison of As-Is-Copied Files

For the following files (marked as "copy as-is" in ecw-init), compare the project copy against the current template for **structural differences**:

**`change-risk-classification.md`:**
- Read plugin `templates/change-risk-classification.md`
- Read project `.claude/ecw/change-risk-classification.md`
- Compare skill/tool names referenced in the "Risk Level → Workflow Requirements" table:
  - Extract all skill names appearing in both template and project files (e.g., `impl-verify`, `biz-impact-analysis`, `spec-challenge`, `requirements-elicitation`, `writing-plans`)
  - If project file uses terminology no longer present in template (e.g., `code-review` replaced by `impl-verify`), flag as "stale terminology"
- Compare "Three-Dimensional Risk Factors" section: Check if project file still contains unreplaced template placeholders (`{your_...}` patterns)

**`calibration-log.md`:**
- Only check if file header format matches the template (this file is primarily append-only data — no content comparison)

### 5b-2: domain-registry Field Completeness

Compare each domain definition's field set in the project domain-registry against the Scaffold template's standard field set:

Standard field set (from ecw-init Scaffold Step 3b):
- Domain ID, Display Name, Knowledge Root, Entry Document, Business Rules, Data Model, Code Root

For each registered domain:
- Check if Business Rules field is missing → Flag "missing business rules path"
- Check if Data Model field is missing → Flag "missing data model path"
- If field exists and value is not an explicit annotation like "no standalone file", verify the referenced file exists

### 5b-3: Output

For each detected difference, output:
- **Stale terminology** (warn): Project file uses terminology replaced in the template
- **Missing field** (warn): Domain definition missing a standard field
- **Broken reference** (fail): Field references a file that does not exist

---

### 6a: Knowledge Root

Check if knowledge root directory exists. If not, flag:
- "Knowledge root directory `{path}` does not exist"

### 6b: Common Knowledge

Check if `knowledge_common` directory exists. If it exists, check standard files:
- `cross-domain-rules.md`
- `cross-domain-calls.md`
- `mq-topology.md`
- `shared-resources.md`
- `external-systems.md`
- `e2e-paths.md`

For each file: Check if it exists and whether content is still template placeholder (file size < 200 bytes or contains only headers).

### 6c: Domain-Level Knowledge

For each domain in the domain registry, check its knowledge directory:
- Does the directory exist?
- Does `00-index.md` (or configured entry document) exist?
- Are there `.md` files with actual content?

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
| ecw-path-mappings.md | {pass/warn/fail} |
| change-risk-classification.md | {pass/warn/fail} |
| Template structure sync | {pass/warn/fail} |
| Knowledge file structure | {pass/warn/fail} |

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
