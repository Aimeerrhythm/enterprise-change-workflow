---
name: ecw-init
description: Initialize Enterprise Change Workflow configuration for your project. Scaffolds ecw.yml, domain registry, knowledge templates, and CLAUDE.md integration.
argument-hint: [--skip-scanners]
---

# ECW Init -- Project Initialization Wizard

You are running the `/ecw-init` command. Your job is to interactively collect project information from the user, then scaffold all ECW configuration files and knowledge directories. Follow every step below in order. Do not skip steps.

**Important:** This skill belongs to the `enterprise-change-workflow` plugin. All template files referenced below live in that plugin's `templates/` directory. When you need to read a template, use the Read tool to read from the plugin's installed location (the same parent directory that contains this `commands/` folder -- go up one level to find `templates/`).

---

## Step 0: Pre-flight Check

1. Check if `.claude/ecw/` already exists in the user's project (use Bash: `ls .claude/ecw/ 2>/dev/null`).
2. If it exists:
   - Use `AskUserQuestion` to ask: "`.claude/ecw/` already exists. How would you like to proceed?"
     - Options: "Overwrite all" / "Skip existing files" / "Cancel"
   - If "Cancel", stop and inform the user that initialization was aborted.
   - Remember the user's choice for later steps ("overwrite" vs "skip-existing").
3. If it does not exist, proceed directly to Step 1.

---

## Step 1: Detect Project Language

Scan the project root for build files to detect the language and project type:

| File Found | Language | Project Type |
|-----------|----------|-------------|
| `pom.xml` | java | java-monolith (or java-microservice if multiple `pom.xml` under submodules) |
| `build.gradle` or `build.gradle.kts` | java (or kotlin) | java-monolith (or java-microservice) |
| `package.json` | typescript | node |
| `go.mod` | go | go-monolith |
| `pyproject.toml` or `requirements.txt` | python | python |

Use Bash to check: `ls pom.xml build.gradle build.gradle.kts package.json go.mod pyproject.toml requirements.txt 2>/dev/null`

If multiple build systems are detected, pick the primary one (e.g., `pom.xml` takes priority for Java projects even if `package.json` exists for frontend tooling).

For Java projects, additionally check if this is a multi-module project:
- Bash: `find . -name "pom.xml" -maxdepth 3 | head -20` -- if there are multiple pom.xml files in subdirectories, it is likely a multi-module project (java-monolith with modules, or java-microservice).

Store the detected `language` and `project_type` for later use.

---

## Step 2: Collect Project Info via AskUserQuestion

### 2a: Confirm project basics

Use `AskUserQuestion` to present the detected information and collect:

```
I detected the following project configuration:
- Language: {detected_language}
- Project type: {detected_project_type}

Please provide:
1. Project name (used in agent prompts for context)
2. Brief project description (1-2 sentences)
3. Is the detected language/type correct? If not, what should it be?
```

This should be a single free-text question. Parse the user's response to extract project name, description, and confirmed language/type.

### 2b: Collect domain list

Use `AskUserQuestion` to ask the user to list their business domains:

```
List your business domains. For each domain, provide:
- Domain ID (english, lowercase, hyphens, e.g., "order-management")
- Chinese name or display name
- One-line description of what this domain is responsible for
- Code root directory (the source directory where this domain's code lives)

Example format:
1. order | 订单 | 订单从创建到完成的全生命周期管理 | src/main/java/com/example/biz/order/
2. payment | 支付 | 支付、退款、对账 | src/main/java/com/example/biz/payment/
3. logistics | 物流 | 物流调度、配送、运费计算 | src/main/java/com/example/biz/logistics/

Please list all your domains (one per line):
```

Parse the user's response into a structured list of domains. Each domain should have: `id`, `display_name`, `description`, `code_root`.

### 2c: Collect component types

Use `AskUserQuestion` to ask about code component types:

```
What categories of code components does your project use?

For each component type, provide:
- Name (e.g., Service, Repository, Controller, Manager)
- Grep pattern to find it in code (use {name} as placeholder for the class name)
- Search path (where to look for these components)

For reference, here are common patterns by language:

Java/Spring:
  BizService  | class {name}     | src/main/java/**/biz/
  Manager     | class {name}     | src/main/java/**/manager/
  Controller  | class {name}     | src/main/java/**/interfaces/
  DO          | class {name}     | src/main/java/**/domain/
  Mapper      | interface {name} | src/main/java/**/mapper/

Go:
  Handler     | func.*{name}     | internal/handler/
  Repository  | type {name} struct | internal/repo/
  Service     | type {name} struct | internal/service/

Node/TypeScript:
  Service     | class {name}     | src/services/
  Controller  | class {name}     | src/controllers/
  Model       | class {name}     | src/models/

Please list your component types (or type "use defaults" for the standard set for your language):
```

If the user says "use defaults", generate sensible defaults based on the detected language. Parse the response into a list of component types, each with: `name`, `grep_pattern`, `search_path`.

---

## Step 3: Scaffold Configuration Files

Create the `.claude/ecw/` directory first:

```bash
mkdir -p .claude/ecw
```

### 3a: Generate `ecw.yml`

Read the template: use Read tool on `templates/ecw.yml` from the plugin directory.

Generate `.claude/ecw/ecw.yml` using the Write tool, filling in:
- `project.name` with the user's project name
- `project.type` with the confirmed project type
- `project.language` with the confirmed language
- `component_types` section with the user's component types (uncomment and populate the appropriate language block, remove examples for other languages)
- `scan_patterns` section: keep the defaults that match the detected language, comment out others. For Java/Spring: keep `@Resource`, `@DubboReference`, `mqMsgManager`, `applicationEventPublisher`, `@NacosValue`. For Go: use `wire.Bind`, `grpc.Dial`, etc. For Node: use `constructor(private`, `axios.create`, etc.
- `paths` section: keep defaults as-is

If the user chose "skip existing" in Step 0 and this file already exists, skip it and note that it was skipped.

### 3b: Generate `domain-registry.md`

Read the template: use Read tool on `templates/domain-registry.md` from the plugin directory.

Generate `.claude/ecw/domain-registry.md` using the Write tool. For each domain the user provided, generate a domain definition block following the template structure:

```markdown
### {N}. {domain-id} -- {display_name}

| Attribute | Value |
|------|-----|
| **Domain ID** | `{domain-id}` |
| **Display Name** | {display_name} |
| **Knowledge Root** | `.claude/knowledge/{domain-id}/` |
| **Entry Document** | `00-index.md` |
| **Business Rules** | `common/business-rules.md` |
| **Data Model** | `common/data-model.md` |
| **Code Root** | `{code_root}` |
| **Related Directories** | _(to be filled)_ |

**Responsibilities:** {description}

---
```

Preserve the template's header, footer, "Add New Domain Guide" comment block, keyword matching rules section, and cross-domain data sources section from the original template.

### 3c: Copy `change-risk-classification.md`

Read the template: use Read tool on `templates/change-risk-classification.md` from the plugin directory.

Write the file to `.claude/ecw/change-risk-classification.md` using the Write tool. Copy the template content as-is -- the user will customize the placeholder fields later.

### 3d: Generate `ecw-path-mappings.md`

Read the template: use Read tool on `templates/ecw-path-mappings.md` from the plugin directory.

Before generating, scan the project source directories to discover the actual directory structure:

For Java projects:
```bash
# Find the main business code root
find . -type d -name "biz" -path "*/main/java/*" | head -5
# List subdirectories under the business root
ls <detected_biz_root>/ 2>/dev/null
# Find shared/common/infra directories
find . -type d \( -name "shared" -o -name "common" -o -name "infra" -o -name "infrastructure" \) -path "*/main/java/*" | head -10
# Find interface/controller directories
find . -type d \( -name "interfaces" -o -name "controller" -o -name "api" \) -path "*/main/java/*" | head -10
# Find SQL/mapper directories
find . -type d -name "mapper" -path "*/resources/*" | head -5
```

For Go projects:
```bash
ls internal/ cmd/ pkg/ 2>/dev/null
```

For Node projects:
```bash
ls src/ 2>/dev/null
```

Generate `.claude/ecw/ecw-path-mappings.md` using the Write tool. Fill in:
- The mapping rules table with actual discovered paths (replace `{biz_root}`, `{shared_root}`, `{infra_root}`, `{common_root}`, `{interface_root}`, `{sql_root}` placeholders)
- The "Business Directory Complete Mapping" table: for each subdirectory found under the business code root, map it to the corresponding domain from the user's domain list. If a subdirectory does not clearly belong to any domain, add it with a `?` marker and a comment asking the user to assign it.

---

## Step 4: Scaffold Knowledge Directories

### 4a: Create common knowledge directory and copy templates

```bash
mkdir -p .claude/knowledge/common
```

Read and copy these 6 template files from `templates/knowledge/common/` in the plugin directory:
1. `cross-domain-rules.md` (索引文件，必须首先创建)
2. `cross-domain-calls.md`
3. `e2e-paths.md`
4. `external-systems.md`
5. `mq-topology.md`
6. `shared-resources.md`

For each file: Read the template with the Read tool, then Write it to `.claude/knowledge/common/{filename}`.

If "skip existing" mode and the file already exists, skip it.

### 4b: Create domain knowledge directories and copy templates

For each domain the user provided:

```bash
mkdir -p .claude/knowledge/{domain-id}/common/nodes
```

Read and copy these 3 template files from `templates/knowledge/domain/` in the plugin directory:
1. `00-index.md` -> `.claude/knowledge/{domain-id}/00-index.md`
2. `business-rules.md` -> `.claude/knowledge/{domain-id}/common/business-rules.md`
3. `data-model.md` -> `.claude/knowledge/{domain-id}/common/data-model.md`

When writing each file, replace the `{{Domain Name}}` placeholder in the template with the domain's display name, and `{{DATE}}` with today's date.

If "skip existing" mode and the file already exists, skip it.

---

## Step 5: Generate CLAUDE.md Snippet

Read the template: use Read tool on `templates/CLAUDE.md.snippet` from the plugin directory.

Fill in the domain routing table from the user's domain list. For each domain, create a row:

```
| {keywords} | {display_name} | `.claude/knowledge/{domain-id}/00-index.md` |
```

For the `{keywords}` column: use the domain's display name plus any obvious related keywords derived from the domain description. Separate keywords with `/`. Ask the user to refine them later.

Also fill in:
- Keep the "cross-domain/global rules" row pointing to `.claude/knowledge/common/cross-domain-rules.md`
- Keep all other sections (doc sync rules, automation rules, impact analysis tool comparison) as-is from the template

Present the generated snippet to the user and use `AskUserQuestion`:

```
Here is the CLAUDE.md snippet for ECW integration:

---
{generated snippet content}
---

Would you like me to append this to your project's CLAUDE.md?
```

Options: "Append to CLAUDE.md" / "Save as separate file (.claude/ecw/CLAUDE.md.snippet)" / "Skip (I'll do it manually)"

- If "Append": Read the existing `CLAUDE.md` with the Read tool, then Write the full content (existing + newline + snippet) back using the Write tool.
- If "Save as separate file": Write to `.claude/ecw/CLAUDE.md.snippet`.
- If "Skip": Do nothing, note it in the summary.

---

## Step 6: Optional Code Scanners (Java Projects Only)

**Skip this step entirely if:**
- The detected language is not Java, OR
- The user passed `--skip-scanners` as an argument

If this is a Java project and scanners were not skipped:

Use `AskUserQuestion`:

```
Would you like to run automatic code scanners to populate knowledge files?

Available scanners (from the enterprise-change-workflow plugin's scripts/java/ directory):
- Cross-domain call scanner: finds @Resource/@DubboReference injections across domain boundaries
- MQ topology scanner: finds MQ topic publishers and consumers
- Shared resource scanner: identifies classes used by multiple domains

Note: Scanners analyze source code and populate the knowledge files created in the previous steps.
This can take a few minutes on large codebases.
```

Options: "Run all scanners" / "Skip scanners"

If the user chooses to run scanners:
1. Check if the scanner scripts exist in the plugin's `scripts/java/` directory using Bash: `ls {plugin_root}/scripts/java/scan-*.sh 2>/dev/null`
2. If scripts exist, run each one via Bash, passing the project root as an argument.
3. If scripts do not exist yet, inform the user: "Scanner scripts are not yet available in this plugin version. Knowledge files have been created with template placeholders -- you can populate them manually or wait for scanner support."

---

## Step 7: Output Summary

After all steps are complete, output a structured summary:

```markdown
## ECW Initialization Complete

### Project Configuration
- **Project:** {project_name}
- **Language:** {language}
- **Type:** {project_type}
- **Domains:** {count} domains registered

### Files Created

#### Configuration (.claude/ecw/)
| File | Status |
|------|--------|
| `ecw.yml` | {Created / Skipped (already exists)} |
| `domain-registry.md` | {Created / Skipped} |
| `change-risk-classification.md` | {Created / Skipped} |
| `ecw-path-mappings.md` | {Created / Skipped} |

#### Knowledge -- Common (.claude/knowledge/common/)
| File | Status |
|------|--------|
| `cross-domain-rules.md` (索引) | {Created / Skipped} |
| `cross-domain-calls.md` | {Created / Skipped} |
| `e2e-paths.md` | {Created / Skipped} |
| `external-systems.md` | {Created / Skipped} |
| `mq-topology.md` | {Created / Skipped} |
| `shared-resources.md` | {Created / Skipped} |

#### Knowledge -- Domains
{For each domain:}
| Directory | Files | Status |
|-----------|-------|--------|
| `.claude/knowledge/{domain-id}/` | 00-index.md, common/business-rules.md, common/data-model.md | {Created / Skipped} |

#### CLAUDE.md Integration
| Action | Status |
|--------|--------|
| Domain routing snippet | {Appended to CLAUDE.md / Saved to .claude/ecw/CLAUDE.md.snippet / Skipped} |

### What to Do Next

1. **Review `ecw.yml`**: Customize `scan_patterns` and `component_types` for your project's specific patterns.
2. **Review `ecw-path-mappings.md`**: Verify the auto-detected directory-to-domain mappings. Fix any `?` entries.
3. **Customize `change-risk-classification.md`**: Replace placeholder entries (`{your_...}`) with your project's actual critical resources, core flows, and sensitivity rules.
4. **Fill domain knowledge files**: Each domain's `00-index.md`, `business-rules.md`, and `data-model.md` contain template placeholders (`{{...}}`). Fill them with actual domain knowledge. {If Java: "Consider running `/ecw-scan` later to auto-populate some of these."}
5. **Populate common knowledge files**: Fill in `cross-domain-calls.md`, `mq-topology.md`, `shared-resources.md`, `external-systems.md`, and `e2e-paths.md` with your system's actual integration data.
6. **Refine CLAUDE.md keywords**: Review the domain routing table keywords and add domain-specific terms your team uses.
```

---

## Error Handling

- If any Write operation fails, report the error and continue with remaining files.
- If the user's input is ambiguous (e.g., domain list format is unclear), ask a clarifying follow-up question rather than guessing.
- If a template file cannot be read from the plugin directory, report the error clearly: "Could not read template file at {path}. The plugin installation may be incomplete."
