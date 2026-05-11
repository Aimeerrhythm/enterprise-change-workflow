---
name: ecw-init
description: Initialize Enterprise Change Workflow configuration for your project. Supports three modes — Attach (existing docs), Manual (user-specified paths), Scaffold (new project).
argument-hint: [--skip-scanners]
---

# ECW Init — Project Initialization Wizard

You are executing the `/ecw-init` command. Your task is to detect the project's existing documentation state, select the appropriate initialization mode, then generate ECW configuration files. Follow the steps below strictly in order — do not skip steps.

**Important:** This skill belongs to the `enterprise-change-workflow` plugin. All template files referenced below are located in the plugin's `templates/` directory. When reading templates, use the Read tool from the plugin installation path (i.e., `templates/` under the parent directory containing this `commands/` folder).

---

## Step 0: Smart Discovery + Mode Selection

### 0a: Scan Existing Documents

Scan **two information sources** to detect existing knowledge documents:

**Source A — `.claude/` directory structure:**

```bash
# List all .md files under .claude/, excluding known config directories
find .claude/ -name "*.md" -type f \
  -not -path ".claude/ecw/*" \
  -not -path ".claude/rules/*" \
  -not -path ".claude/guides/*" \
  -not -path ".claude/project/*" \
  -not -path ".claude/specs/*" \
  -not -path ".claude/plans/*" \
  -not -path ".claude/plugins/*" \
  -not -name "CLAUDE.md" \
  -not -name "index.md" \
  2>/dev/null | sort

# List first-level directories under .claude/
find .claude/ -mindepth 1 -maxdepth 1 -type d 2>/dev/null
```

Count candidate knowledge directories (directories containing ≥ 2 `.md` files that are not in the exclusion set `ecw/`, `rules/`, `guides/`, `project/`, `specs/`, `plans/`, `plugins/`).

**Source B — `CLAUDE.md` content:**

If `CLAUDE.md` exists at project root:
- Read its content with the Read tool
- Search for path references matching `.claude/knowledge/`, `.claude/docs/`, `knowledge/`, and any `.claude/{something}/` references pointing to documentation
- Search for domain routing tables (markdown tables containing domain names and paths)
- Search for domain keywords or business domain descriptions

### 0b: Select Mode

Based on scan results, present one of the following scenarios:

**Scenario A — Knowledge directories found:**

Use `AskUserQuestion`:

```
Detected {N} knowledge directories and {M} .md files under .claude/.

- Attach (Recommended) — Generate ECW configuration based on existing docs, no changes to existing files
- Manual — I will specify knowledge directory paths and domain info myself
- Scaffold — Ignore existing files, create all configuration + knowledge templates from scratch
```

Mark "Attach" as the recommended option.

**Scenario B — No knowledge directories found:**

Use `AskUserQuestion`:

```
No existing knowledge document structure detected.

- Scaffold (Recommended) — Create all configuration + knowledge templates from scratch
- Manual — I have knowledge docs but not under .claude/, will specify paths manually
- Attach — Force scan (may have missed something)
```

Mark "Scaffold" as the recommended option.

### 0c: Route to Corresponding Mode

- **Attach** → Jump to "Attach Mode" section
- **Manual** → Jump to "Manual Mode" section
- **Scaffold** → Jump to "Scaffold Mode" section

---

# Attach Mode

For projects with existing documentation. Scan to discover, user confirms, generate ECW configuration only.

## Attach Step 1: Deep Scan & Structure Discovery

Build a complete picture of the existing documentation structure:

```
1. Based on Step 0 scan results, group .md files by parent directory.

2. Identify the "knowledge root" — a directory containing multiple subdirectories,
   each with .md files.
   Common patterns:
   - .claude/knowledge/  (containing inbound/, outbound/, task/, etc.)
   - .claude/docs/       (containing order/, payment/, etc.)
   - docs/               (outside .claude/)
   
   Heuristic: The deepest common ancestor directory containing ≥ 3 subdirectories
   with .md files.

3. Under the knowledge root, classify each subdirectory:
   - "Domain candidate": Contains .md files related to a specific business domain
   - "Common/shared": Named common/, shared/, or contains cross-domain documentation
   - "Other": Does not fit above categories

4. For each domain candidate, count:
   - Total .md file count (recursive)
   - Whether 00-index.md exists
   - Whether business-rules.md or data-model.md exists (recursive search,
     record relative paths, e.g., `common/business-rules.md`,
     `checkstock/common/business-rules.md`)

5. Also check CLAUDE.md for additional clues:
   - If CLAUDE.md has a domain routing table, extract domain names and paths
   - If CLAUDE.md references paths not found in filesystem scan, flag them
```

## Attach Step 2: Present & Confirm

Use `AskUserQuestion` (free text) to present findings and collect domain info:

```
Scan discovered the following documentation structure:

Knowledge root (inferred): {detected_knowledge_root}
{for each subdirectory:}
  |- {dirname}/          ({file_count} files) {— common knowledge if common/shared}
  ...

{if CLAUDE.md has domain routing table:}
Additionally, CLAUDE.md references the following domain paths:
  - {domain_name} -> {path}
  ...

Please confirm and supplement:
1. Is the knowledge root path correct? If not, provide the actual path
2. Which are business domains? For each domain provide:
   dirname | domain ID | display name | description | code root
3. Which directories to skip? Mark with "-> skip"

Example format:
  inbound | inbound | Inbound | Full inbound chain management | service/biz/inbound/
  common -> skip (common knowledge)
```

Parse user reply, extract:
- Confirmed knowledge root path (may differ from detected value)
- Domain list, each with: `id`, `display_name`, `description`, `code_root`, `knowledge_path` (full path under knowledge root)
- Excluded directories

## Attach Step 3: Detect Language and Component Types

Same as Scaffold Step 1 + Step 2c:

1. **Detect project language** by scanning build files:

```bash
ls pom.xml build.gradle build.gradle.kts 2>/dev/null
```

| Detected File | Language | Project Type |
|--------------|----------|-------------|
| `pom.xml` | java | java-monolith (java-microservice if multi-module) |
| `build.gradle` / `build.gradle.kts` | java | java-monolith/microservice |

For Java projects, check if multi-module: `find . -name "pom.xml" -maxdepth 3 | head -20`

2. **Confirm with user** using `AskUserQuestion`:

```
Detected: Language = {language}, Type = {type}
Is this correct? If not, please specify.
Use default component types or custom? (Enter "use defaults" for defaults)
```

3. If "use defaults" selected, generate standard component types for the detected language.

## Attach Step 4: Generate ECW Configuration

Create `.claude/ecw/` directory: `mkdir -p .claude/ecw`

### 4a: Generate `ecw.yml`

Read `templates/ecw.yml` template. Fill in:
- `project.name`, `project.type`, `project.language` (from Step 3)
- `component_types` (from Step 3)
- `scan_patterns`: Keep defaults matching the detected language

**Version number**: Read `package.json` from the plugin root directory (the parent directory of `commands/`). Extract the `version` field and replace `ecw_version: "ECW_VERSION_PLACEHOLDER"` with the actual version string (e.g., `ecw_version: "1.3.4"`).

### 4b: Generate `domain-registry.md`

Read `templates/domain-registry.md` template. Generate one block per confirmed domain using **actual paths**:

```markdown
### {N}. {domain-id} — {display_name}

| Attribute | Value |
|------|-----|
| **Domain ID** | `{domain-id}` |
| **Display Name** | {display_name} |
| **Knowledge Root** | `{actual_knowledge_path}/` |
| **Entry Document** | `{detected_entry_file}` |
| **Business Rules** | `{detected_business_rules_path}` |
| **Data Model** | `{detected_data_model_path}` |
| **Code Root** | `{code_root}` |

**Responsibilities:** {description}
```

Key difference from Scaffold: `Knowledge Root` uses user-confirmed **actual paths** (e.g., `.claude/knowledge/inbound/`), not template placeholders.

`Business Rules` and `Data Model` determination (using Step 1 scan results):
- If `business-rules.md` found recursively in domain directory → Use path relative to domain knowledge root (e.g., `common/business-rules.md`, `checkstock/common/business-rules.md`)
- If multiple found → List all, comma-separated with submodule names (e.g., `checkstock/common/business-rules.md` (stocktake), `move/common/business-rules.md` (transfer))
- If not found → Note "no standalone file"
- `Data Model` follows same logic

`Entry Document` determination:
- If `00-index.md` exists in domain directory → Use it
- Otherwise → Use the first `.md` file in the directory (alphabetical order)
- If directory is empty → Use `00-index.md (to be created)`

### 4c: Generate `path-mappings.md`

Read `templates/path-mappings.md` template. Auto-discover project directory structure:

For Java projects:
```bash
find . -type d -name "biz" -path "*/main/java/*" | head -5
ls <detected_biz_root>/ 2>/dev/null
find . -type d \( -name "shared" -o -name "common" -o -name "infra" \) -path "*/main/java/*" | head -10
find . -type d \( -name "interfaces" -o -name "controller" \) -path "*/main/java/*" | head -10
find . -type d -name "mapper" -path "*/resources/*" | head -5
```

Map discovered subdirectories to confirmed domains.

After writing the file, verify completeness — same gap check as Scaffold Step 3d: scan all Java source directories discovered in this step's generation scan, verify each one with `.java` files has a mapping row, add missing rows or flag as `（待确认域）`.

### 4e: Create State Files

```bash
mkdir -p .claude/ecw/state
```

## Attach Step 5: Skip Knowledge Directory Creation

**Do not create, modify, or overwrite any existing documentation files.** This is the core difference from Scaffold mode. User's existing knowledge files are preserved as-is.

## Attach Step 6: Generate CLAUDE.md Snippet

Read `templates/CLAUDE.md.snippet` template.

Fill the domain routing table using user-confirmed **actual paths**:

```markdown
| Keywords | Domain | Entry Document |
|----------|--------|---------------|
| {keywords} | {display_name} | `{actual_knowledge_path}/{entry_file}` |
```

`{keywords}` generation: Extract keywords from domain display name + description, separated by `/`.

Entry file path:
- If `00-index.md` exists → Use it
- If not → Use the first `.md` file in the directory
- If directory is empty → Mark `(to be created)`

Present snippet to user via `AskUserQuestion`:
- "Append to CLAUDE.md" / "Save as .claude/ecw/CLAUDE.md.snippet" / "Skip"

## Attach Step 7: Code Scanners (Java only)

Skip if language is not Java or `--skip-scanners` was passed.

Same as Scaffold Step 6 (6a–6g): Run all Java scan scripts automatically. Since Attach mode preserves existing domain knowledge files, only update common knowledge files (`cross-domain-calls.md`, `shared-resources.md`, `mq-topology.md`, `external-systems.md`) if they contain placeholder rows (`{{...}}`). Skip updating a file if it already has real content (i.e., no `{{...}}` placeholders in the data rows).

Step 6g (inline configuration validation) always runs and its results appear in Step 8's output summary.

## Attach Step 8: Output Summary

Output structured summary (same format as Scaffold Step 7), with these differences:
- Title: "ECW Initialization Complete (Attach Mode)"
- Knowledge files section shows: "Existing — not modified" (per domain directory)
- Common knowledge section shows: "Existing — not modified" if files exist, "Not detected" if not
- Include Validation Results section from Step 6g
- Next Steps: Replace "Enrich domain knowledge files" with "Review existing domain knowledge for completeness — add any missing files (business-rules.md, data-model.md) if not yet present"

---

# Manual Mode

For cases where auto-scan did not find docs, or docs are outside `.claude/`.

## Manual Step 1: User Specifies Paths

Use `AskUserQuestion` (free text):

```
Please provide your knowledge documentation info:

1. Knowledge root directory path (can be any location, e.g., .claude/knowledge/, docs/, wiki/)
2. Domain list, one per line:
   dirname | domain ID | display name | description | code root

Example:
  Knowledge root: docs/domains/
  
  order | order | Order | Full order lifecycle | src/main/java/com/biz/order/
  payment | payment | Payment | Payment, refund, reconciliation | src/main/java/com/biz/payment/
  logistics | logistics | Logistics | Delivery and shipping | src/main/java/com/biz/logistics/

If you don't have knowledge docs yet and just want to generate ECW config first,
you can provide only the domain list (no knowledge root) and create docs later.
```

Parse user reply, extract:
- Knowledge root path (optional — user may not have docs yet)
- Domain list, each with: `id`, `display_name`, `description`, `code_root`

## Manual Step 2: Validate Paths

For each user-provided path, validate existence:

```bash
ls {knowledge_root}/ 2>/dev/null
ls {knowledge_root}/{domain_dir}/ 2>/dev/null
```

If any path does not exist, use `AskUserQuestion`:

```
The following paths do not exist:
{list of missing paths}

- Continue — Non-existent paths will be kept in config; you can create directories and files later
- Modify — Re-enter paths
```

If user selects "Continue", proceed with original paths. Missing-path domain entries get `Entry Document = 00-index.md (to be created)`.

## Manual Step 3: Detect Language and Component Types

Same as Attach Step 3.

## Manual Step 4: Generate ECW Configuration

Same as Attach Step 4, using user-specified paths.

For domains with non-existent knowledge directories:
- `domain-registry.md` `Knowledge Root`: Use user-specified path (even if non-existent)
- `Entry Document`: `00-index.md (to be created)`

## Manual Step 5: Skip Knowledge Directory Creation

Same as Attach Step 5 — do not create knowledge files. User creates them when ready.

Exception: If user explicitly requests knowledge directory creation in Step 1's AskUserQuestion (e.g., "also create a knowledge directory skeleton for me"), then create directory structure and template files following Scaffold Step 4's approach.

## Manual Step 6: Generate CLAUDE.md Snippet

Same as Attach Step 6, using user-specified paths.

## Manual Step 7-8: Scanners + Summary

Same as Attach Step 7-8. Summary title: "ECW Initialization Complete (Manual Mode)". Step 6f (inline validation) always runs regardless of mode.

---

# Scaffold Mode

For brand new projects with no existing documentation. Creates everything from scratch.

**This mode preserves the original `/ecw-init` full workflow.** The only difference is entering via Step 0's mode selection rather than as the default mode.

## Scaffold Step 1: Detect Project Language

Scan project root for build files to detect language and project type:

| Detected File | Language | Project Type |
|--------------|----------|-------------|
| `pom.xml` | java | java-monolith (java-microservice if multiple `pom.xml` under subdirectories) |
| `build.gradle` or `build.gradle.kts` | java | java-monolith (or java-microservice) |

Check via Bash: `ls pom.xml build.gradle build.gradle.kts 2>/dev/null`

If multiple build systems detected, select the primary one (e.g., Java project with `pom.xml` takes precedence even if `package.json` exists for frontend tooling).

For Java projects, additionally check if multi-module:
- Bash: `find . -name "pom.xml" -maxdepth 3 | head -20` — If multiple pom.xml files exist under subdirectories, likely a multi-module project.

Save detected `language` and `project_type` for later use.

## Scaffold Step 2: Collect Project Info via AskUserQuestion

### 2a: Confirm Project Basics

Use `AskUserQuestion` to present detected info and collect:

```
Detected project configuration:
- Language: {detected_language}
- Project type: {detected_project_type}

Please provide:
1. Project name (used for context in Agent prompts)
2. Project description (1-2 sentences)
3. Is the detected language/type correct? If not, please specify.
```

Parse user reply, extract project name, description, confirmed language/type.

### 2b: Collect Domain List

Use `AskUserQuestion`:

```
Please list your business domains. For each domain provide:
- Domain ID (lowercase English, hyphenated, e.g., "order-management")
- Display name
- One-sentence description
- Code root directory

Example:
1. order | Order | Full order lifecycle management from creation to completion | src/main/java/com/example/biz/order/
2. payment | Payment | Payment, refund, reconciliation | src/main/java/com/example/biz/payment/

List all domains (one per line):
```

Parse into structured list: `id`, `display_name`, `description`, `code_root`.

### 2c: Collect Component Types

Use `AskUserQuestion`:

```
What code component categories does your project use?

For each component type provide:
- Name (e.g., Service, Repository, Controller, Manager)
- Grep match pattern in code (use {name} as placeholder)
- Search path

Common defaults per language:

Java/Spring (Dubbo 项目):
  BizService      | interface {name} | src/main/java/**/biz/
  BizServiceImpl  | class {name}     | src/main/java/**/biz/impl/
  Manager         | class {name}     | src/main/java/**/manager/
  FacadeInterface | interface {name} | src/main/java/**/interfaces/
  FacadeImpl      | @DubboService    | src/main/java/**/service/impl/
  DO              | class {name}     | src/main/java/**/domain/model/
  Mapper          | interface {name} | src/main/java/**/mapper/

Java/Spring MVC 项目:
  BizService  | interface {name} | src/main/java/**/biz/
  BizServiceImpl | class {name}  | src/main/java/**/biz/impl/
  Manager     | class {name}     | src/main/java/**/manager/
  Controller  | class {name}     | src/main/java/**/controller/
  DO          | class {name}     | src/main/java/**/domain/model/
  Mapper      | interface {name} | src/main/java/**/mapper/

Enter "use defaults" to use the standard component set for your language:
```

## Scaffold Step 3: Generate Configuration Files

`mkdir -p .claude/ecw`

### 3a: Generate `ecw.yml`

Read `templates/ecw.yml`. Fill in project info, component types, scan patterns for detected language.

**Version number**: Read `package.json` from the plugin root directory (the parent directory of `commands/`). Extract the `version` field and replace `ecw_version: "ECW_VERSION_PLACEHOLDER"` with the actual version string (e.g., `ecw_version: "1.3.4"`).

### 3b: Generate `domain-registry.md`

Read `templates/domain-registry.md`. Generate one block per domain:

```markdown
### {N}. {domain-id} — {display_name}

| Attribute | Value |
|------|-----|
| **Domain ID** | `{domain-id}` |
| **Display Name** | {display_name} |
| **Knowledge Root** | `.claude/knowledge/{domain-id}/` |
| **Entry Document** | `00-index.md` |
| **Business Rules** | `common/business-rules.md` |
| **Data Model** | `common/data-model.md` |
| **Code Root** | `{code_root}` |

**Responsibilities:** {description}
```

Preserve template header/footer, "Adding New Domains" block, keyword matching rules, cross-domain data source sections.

### 3c: Generate `path-mappings.md`

Read `templates/path-mappings.md`. Scan project directory structure, generate mapping table.

After writing the file, verify completeness — scan ALL Java source directories already discovered in this step's generation scan (not just `biz/`), and check that each one with `.java` files has a corresponding mapping row. Add any missing rows or flag as `（待确认域）`. Output the gap count in the summary.

### 3e: Create State Files

```bash
mkdir -p .claude/ecw/state
```

## Scaffold Step 4: Create Knowledge Directory Skeleton

### 4a: Common Knowledge

```bash
mkdir -p .claude/knowledge/shared
```

Read and copy the 6 templates under `templates/knowledge/shared/`:
1. `cross-domain-rules.md`
2. `cross-domain-calls.md`
3. `e2e-paths.md`
4. `external-systems.md`
5. `mq-topology.md`
6. `shared-resources.md`

### 4b: Domain-Level Knowledge

For each domain:

```bash
mkdir -p .claude/knowledge/{domain-id}/common/nodes
```

Read and copy the 3 templates under `templates/knowledge/domain/`:
1. `00-index.md` → `.claude/knowledge/{domain-id}/00-index.md`
2. `business-rules.md` → `.claude/knowledge/{domain-id}/common/business-rules.md`
3. `data-model.md` → `.claude/knowledge/{domain-id}/common/data-model.md`

Replace `{{Domain Name}}` with display name, `{{DATE}}` with today's date, `{{COMMIT_HASH}}` with current git commit hash (`git rev-parse HEAD 2>/dev/null || echo "unknown"`).

## Scaffold Step 5: Generate CLAUDE.md Snippet

Read `templates/CLAUDE.md.snippet`. Fill the domain routing table:

```markdown
| {keywords} | {display_name} | `.claude/knowledge/{domain-id}/00-index.md` |
```

Present to user: "Append to CLAUDE.md" / "Save as separate file" / "Skip"

## Scaffold Step 6: Code Scanners (Java only)

Skip if language is not Java or `--skip-scanners` was passed.

Run all Java scan scripts automatically — no user prompt needed. Determine `{plugin_dir}` by reading the parent directory of the `commands/` folder (i.e., where this file is located).

### 6a: Cross-domain calls scan → `cross-domain-calls.md`

```bash
bash {plugin_dir}/scripts/java/scan-cross-domain-calls.sh {project_root} .claude/ecw/routing/path-mappings.md 2>/dev/null
```

Capture output (the markdown table rows). Then update `.claude/knowledge/shared/cross-domain-calls.md`:
- Replace `{{SCAN_DATE}}` with today's date, `{{TOTAL_COUNT}}` with number of result rows.
- Replace the placeholder `{{caller_domain}}` example row in the "调用明细" table with the actual scan rows.
- If the scan returns zero rows (single-domain project with no cross-domain calls): replace the placeholder row with `| (暂无跨域调用) | — | — | — | — | — | — |`

### 6b: Shared resources scan → `shared-resources.md`

```bash
bash {plugin_dir}/scripts/java/scan-shared-resources.sh {project_root} .claude/ecw/routing/path-mappings.md 2>/dev/null
```

Capture output. Then update `.claude/knowledge/shared/shared-resources.md`:
- Replace the placeholder `{{resource_name}}` rows in both tables with actual scan results.
- Classify scanned resources into the "极高风险/高风险/中风险" sections based on consumer domain count.
- If no shared resources found: replace placeholder rows with `| (暂无) | — | — | — | — |`

### 6c: MQ topology scan → `mq-topology.md`

```bash
bash {plugin_dir}/scripts/java/scan-mq-topology.sh {project_root} 2>/dev/null
```

Capture output. Then update `.claude/knowledge/shared/mq-topology.md`:
- Classify each scanned row into "内部 Topic / 外部入站 Topic / 外部出站 Topic" based on whether both publisher and consumer are in this project.
- Replace the placeholder `{{topic}}` row in the appropriate table with actual scan results.
- If no MQ topics found: replace placeholder rows with `| (暂无) | — | — | — | — | — | — |`
- Update the "统计" table counts.

### 6d: External systems scan → `external-systems.md`

Scan for `@DubboReference` (external RPC dependencies) and `@DubboService` (exposed facades):

```bash
grep -rn "@DubboReference" {project_root} --include="*.java" -l 2>/dev/null | head -20
grep -rn "@DubboService" {project_root} --include="*.java" 2>/dev/null | head -20
```

Then update `.claude/knowledge/shared/external-systems.md`:
- For each `@DubboReference` found: extract the interface name and owning file. Add a row to "按系统分类的集成详情" under the appropriate external system section. If the system is unknown, group under a placeholder system name like "待确认外部系统".
- For each `@DubboService` found: extract the facade interface and domain. Add to "对外暴露的服务" table.
- Update the "汇总" count table with actual counts (`RPC 引用（出站）` and `RPC 服务（对外暴露）`).
- For counts that cannot be determined automatically (MQ inbound/outbound), fill with `(待填充)` rather than `0`.

### 6e: Repo Map + doc-tracker

1. **Copy doc-tracker template**: Read `templates/doc-tracker.md` and write to `.claude/ecw/knowledge-ops/doc-tracker.md`.
2. **Generate Repo Map**: Run `bash {plugin_dir}/scripts/java/generate-repo-map.sh {project_root} .claude/ecw/ecw.yml` to auto-generate the code structure index.

### 6f: Project-local hook registration

Write ECW runtime hooks into the project so they are only active in ECW-integrated projects.

1. **Install hook runner**: Copy `templates/hook-runner.sh` from the plugin directory to `.claude/ecw/hook-runner.sh`. Mark it executable (`chmod +x`). This script dynamically resolves the ECW plugin path at runtime, avoiding `${CLAUDE_PLUGIN_ROOT}` which is only available inside plugin-owned hooks.

2. **Merge settings.json**: Run `python3 {plugin_dir}/scripts/merge-settings.py {project_root}`. The script idempotently merges ECW `permissions.allow` entries and `hooks` registrations into `.claude/settings.json`, preserving any unrelated project-local settings. If the file does not exist, it is created from `templates/settings.ecw.json`.

### 6g: Inline configuration validation

After all files are generated, perform key validation checks inline (a subset of `/ecw-validate-config` — covers immediate init gaps but not template sync or domain-registry field completeness) and include results in the output summary. Do not ask the user to run a separate command.

**Check 1 — Domain knowledge directories:**
For each registered domain, verify its knowledge directory and entry document exist. Mark missing items as `✗ fail`.

**Check 2 — Path-mappings reference validity:**
For each mapping row, verify the source directory exists on disk. Mark missing directories as `⚠ warn`.

**Check 3 — ecw.yml path references:**
Verify all `paths.*` entries in ecw.yml point to files/directories that exist. Mark missing required files as `✗ fail`.

Output the validation results as part of the Step 7 summary (see "Validation Results" section in template below). If all checks pass, show a ✓ green summary. If there are fails or warns, list them with fix instructions.

## Scaffold Step 7: Output Summary

```markdown
## ECW Initialization Complete (Scaffold Mode)

### Project Configuration
- **Project Name:** {project_name}
- **Language:** {language}
- **Type:** {project_type}
- **Domain Count:** {count} domains registered

### Created Files

#### Configuration Files (.claude/ecw/)
| File | Status |
|------|--------|
| `.claude/ecw/ecw.yml` | Created |
| `.claude/ecw/routing/domain-registry.md` | Created |
| `change-risk-classification.md` | Removed — risk assessment now uses domain docs |
| `.claude/ecw/routing/path-mappings.md` | Created |
| `.claude/ecw/README.md` | Created |

#### Knowledge Files — Common (.claude/knowledge/shared/)
| File | Status |
|------|--------|
| `cross-domain-rules.md` | Created |
| `cross-domain-calls.md` | Created + auto-filled from scanner |
| `e2e-paths.md` | Created |
| `external-systems.md` | Created + auto-filled from scanner |
| `mq-topology.md` | Created + auto-filled from scanner |
| `shared-resources.md` | Created + auto-filled from scanner |

#### Knowledge Files — Domain-Level
| Directory | Files | Status |
|-----------|-------|--------|
| `.claude/knowledge/{domain-id}/` | 00-index.md, common/business-rules.md, common/data-model.md | Created |

#### Knowledge Maintenance Files
| File | Status |
|------|--------|
| `.claude/ecw/knowledge-ops/doc-tracker.md` | Created |
| `.claude/ecw/knowledge-ops/repo-map.md` | Created (Java projects only) |
| `.claude/ecw/knowledge-ops/README.md` | Created |

#### CLAUDE.md Integration
| Action | Status |
|--------|--------|
| Domain routing snippet | {Appended / Saved / Skipped} |

### Next Steps

1. **Review `.claude/ecw/ecw.yml`**: Customize `scan_patterns` and `component_types` if scanners missed project conventions.
2. **Review `.claude/ecw/routing/path-mappings.md`**: Verify directory-to-domain mappings, especially infra/shared layers.
3. **Review `.claude/ecw/routing/domain-registry.md`**: Confirm domain definitions, knowledge roots, and code directories are accurate.
4. **Review scanner-filled common knowledge**: Confirm external systems, MQ topology, and shared resources are correct.
5. **Enrich domain knowledge files**: Add project-specific business rules and data model details.
6. **Refine `CLAUDE.md` keywords**: Add missing domain-specific terms.
7. **Understand ECW subdirectories**: `routing/` stores routing metadata, `knowledge-ops/` stores repo/doc governance artifacts, `state/` stores runtime files.

```

And append a "Validation Results" section at the end of the summary block:

```markdown
### Validation Results

{output from Step 6g inline checks — pass/warn/fail items, or "All checks passed ✓"}
```

---

# Common Final Step: Permission Configuration

After generating ECW configuration (in any mode), configure write permissions to prevent interactive prompts during workflow execution.

Add to `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Write(.claude/ecw/**)",
      "Write(.claude/knowledge/**)",
      "Write(.claude/plans/**)"
    ]
  }
}
```

If `.claude/settings.local.json` already exists, merge the `allow` entries without overwriting existing permissions.

This enables ECW skills to write session state, plans, reports, and knowledge maintenance files without triggering permission confirmation dialogs.

---

# Error Handling

- If any Write operation fails, report the error then continue processing remaining files.
- If user input is ambiguous, ask for clarification rather than guessing.
- If template files cannot be read from the plugin directory, report: "Cannot read template file {path}. Plugin installation may be incomplete."
