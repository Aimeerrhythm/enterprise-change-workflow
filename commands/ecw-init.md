---
name: ecw-init
description: Initialize Enterprise Change Workflow configuration for your project. Supports three modes — Attach (existing docs), Manual (user-specified paths), Scaffold (new project).
argument-hint: [--skip-scanners]
---

# ECW Init — Project Initialization Wizard

You are running the `/ecw-init` command. Your job is to detect the project's existing documentation state, choose the appropriate initialization mode, then scaffold ECW configuration files. Follow every step below in order. Do not skip steps.

**Important:** This skill belongs to the `enterprise-change-workflow` plugin. All template files referenced below live in that plugin's `templates/` directory. When you need to read a template, use the Read tool to read from the plugin's installed location (the same parent directory that contains this `commands/` folder — go up one level to find `templates/`).

---

## Step 0: Smart Discovery + Mode Selection

### 0a: Scan for existing documentation

Scan **two information sources** to detect existing knowledge documentation:

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

# List top-level directories under .claude/
find .claude/ -mindepth 1 -maxdepth 1 -type d 2>/dev/null
```

Count the candidate knowledge directories (directories containing ≥ 2 `.md` files that are NOT in the excluded config set: `ecw/`, `rules/`, `guides/`, `project/`, `specs/`, `plans/`, `plugins/`).

**Source B — `CLAUDE.md` content:**

If `CLAUDE.md` exists in the project root:
- Read it with the Read tool
- Search for path references matching patterns like `.claude/knowledge/`, `.claude/docs/`, `knowledge/`, or any `.claude/{something}/` references that point to documentation
- Search for domain routing tables (markdown tables with domain names and paths)
- Search for domain keywords or business area descriptions

### 0b: Choose mode

Based on the scan results, present one of these scenarios:

**Scenario A — Knowledge directories found:**

Use `AskUserQuestion`:

```
检测到 .claude/ 下已有 {N} 个知识目录、{M} 个 .md 文件。

- Attach（推荐）— 基于已有文档生成 ECW 配置，不动已有文件
- Manual — 我自己指定知识目录路径和域信息
- Scaffold — 忽略已有文件，从零创建全部配置 + 知识模板
```

Mark "Attach" as recommended.

**Scenario B — No knowledge directories found:**

Use `AskUserQuestion`:

```
未检测到已有知识文档结构。

- Scaffold（推荐）— 从零创建全部配置 + 知识模板
- Manual — 我有知识文档但不在 .claude/ 下，手动指定路径
- Attach — 强制扫描（可能漏检了）
```

Mark "Scaffold" as recommended.

### 0c: Route to mode

- **Attach** → Jump to "Attach Mode" section
- **Manual** → Jump to "Manual Mode" section
- **Scaffold** → Jump to "Scaffold Mode" section

---

# Attach Mode

For projects with existing documentation. Scans and discovers, user confirms, only generates ECW config.

## Attach Step 1: Deep Scan & Structure Discovery

Build a complete picture of the existing documentation structure:

```
1. From the Step 0 scan results, group .md files by their parent directories.

2. Identify the "knowledge root" — the directory that contains multiple
   subdirectories each with .md files. Common patterns:
   - .claude/knowledge/  (contains inbound/, outbound/, task/, etc.)
   - .claude/docs/       (contains order/, payment/, etc.)
   - docs/               (outside .claude/)
   
   Heuristic: the deepest directory that is a common ancestor of ≥ 3 
   directories containing .md files.

3. Under the knowledge root, classify each subdirectory:
   - "Domain candidate": contains .md files about a specific business area
   - "Common/shared": named common/, shared/, or contains cross-cutting docs
   - "Other": doesn't fit either pattern

4. For each domain candidate, count:
   - Total .md files (recursively)
   - Whether 00-index.md exists
   - Whether business-rules.md or data-model.md exist

5. Also check CLAUDE.md for additional hints:
   - If CLAUDE.md has a domain routing table, extract domain names and paths
   - If CLAUDE.md references paths not found in the filesystem scan, note them
```

## Attach Step 2: Present & Confirm

Use `AskUserQuestion` (free-text) to present the discovery and collect domain details:

```
扫描发现以下文档结构：

知识根目录（推测）：{detected_knowledge_root}
{For each subdirectory, show:}
  ├── {dirname}/          ({file_count} files) {— 公共知识 if common/shared}
  ...

{If CLAUDE.md had domain routing table:}
此外，CLAUDE.md 中引用了以下域路径：
  - {domain_name} → {path}
  ...

请确认并补充：
1. 知识根目录路径是否正确？如果不对，请告知实际路径
2. 哪些是业务域？对每个域补充信息：
   目录名 | 域ID | 显示名称 | 描述 | 代码根目录
3. 哪些目录要跳过？标注 "→ 跳过"

示例格式：
  inbound | inbound | 入库 | 入库全链路管理 | service/biz/inbound/
  common → 跳过（公共知识）
```

Parse the user's response to extract:
- Confirmed knowledge root path (may differ from detected)
- List of domains with: `id`, `display_name`, `description`, `code_root`, `knowledge_path` (full path under knowledge root)
- Excluded directories

## Attach Step 3: Detect Language + Component Types

Same as Scaffold Step 1 + Step 2c:

1. **Detect project language** by scanning for build files:

```bash
ls pom.xml build.gradle build.gradle.kts package.json go.mod pyproject.toml requirements.txt 2>/dev/null
```

| File Found | Language | Project Type |
|-----------|----------|-------------|
| `pom.xml` | java | java-monolith (or java-microservice if multiple) |
| `build.gradle` / `build.gradle.kts` | java/kotlin | java-monolith/microservice |
| `package.json` | typescript | node |
| `go.mod` | go | go-monolith |
| `pyproject.toml` / `requirements.txt` | python | python |

For Java, check multi-module: `find . -name "pom.xml" -maxdepth 3 | head -20`

2. **Confirm with user** via `AskUserQuestion`:

```
检测到：Language = {language}, Type = {type}
是否正确？如需修改请说明。
组件类型使用默认还是自定义？（输入 "use defaults" 使用默认）
```

3. If "use defaults", generate standard component types for the detected language.

## Attach Step 4: Generate ECW Configuration

Create `.claude/ecw/` directory: `mkdir -p .claude/ecw`

### 4a: Generate `ecw.yml`

Read template from `templates/ecw.yml`. Fill in:
- `project.name`, `project.type`, `project.language` from Step 3
- `component_types` from Step 3
- `scan_patterns`: keep defaults matching detected language

### 4b: Generate `domain-registry.md`

Read template from `templates/domain-registry.md`. For each confirmed domain, generate a block with **actual paths**:

```markdown
### {N}. {domain-id} — {display_name}

| Attribute | Value |
|------|-----|
| **Domain ID** | `{domain-id}` |
| **Display Name** | {display_name} |
| **Knowledge Root** | `{actual_knowledge_path}/` |
| **Entry Document** | `{detected_entry_file}` |
| **Code Root** | `{code_root}` |

**Responsibilities:** {description}
```

Key difference from Scaffold: `Knowledge Root` uses the **actual path** from user confirmation (e.g., `.claude/knowledge/inbound/`), not a template placeholder.

For `Entry Document`:
- If `00-index.md` exists in the domain directory → use it
- Otherwise → use the first `.md` file (alphabetically) in that directory
- If directory is empty → use `00-index.md (待创建)`

### 4c: Copy `change-risk-classification.md`

Read template from `templates/change-risk-classification.md`. Write as-is to `.claude/ecw/change-risk-classification.md`.

### 4c2: Copy `calibration-log.md`

Read template from `templates/calibration-log.md`. Write as-is to `.claude/ecw/calibration-log.md`. This file accumulates Phase 3 calibration records over time.

### 4d: Generate `ecw-path-mappings.md`

Read template from `templates/ecw-path-mappings.md`. Auto-discover project directory structure:

For Java projects:
```bash
find . -type d -name "biz" -path "*/main/java/*" | head -5
ls <detected_biz_root>/ 2>/dev/null
find . -type d \( -name "shared" -o -name "common" -o -name "infra" \) -path "*/main/java/*" | head -10
find . -type d \( -name "interfaces" -o -name "controller" \) -path "*/main/java/*" | head -10
find . -type d -name "mapper" -path "*/resources/*" | head -5
```

Map discovered subdirectories to confirmed domains.

## Attach Step 5: Skip Knowledge Directory Creation

**Do NOT create, modify, or overwrite any existing documentation files.** This is the core difference from Scaffold mode. The user's existing knowledge files are preserved exactly as-is.

## Attach Step 6: Generate CLAUDE.md Snippet

Read template from `templates/CLAUDE.md.snippet`.

Fill the domain routing table using **actual paths** from user confirmation:

```markdown
| 关键词 | 域 | 入口文档 |
|--------|-----|---------|
| {keywords} | {display_name} | `{actual_knowledge_path}/{entry_file}` |
```

For `{keywords}`: derive from domain display_name + description keywords. Separate with `/`.

For entry file path:
- If `00-index.md` exists → use it
- If not → use first `.md` file in directory
- If empty → mark `(待创建)`

Present snippet to user via `AskUserQuestion`:
- "Append to CLAUDE.md" / "Save as .claude/ecw/CLAUDE.md.snippet" / "Skip"

## Attach Step 7: Optional Code Scanners (Java Only)

Skip if language ≠ Java or `--skip-scanners` was passed.

Same as Scaffold Step 6: offer to run Java scanner scripts from `scripts/java/`.

## Attach Step 8: Output Summary

Output structured summary (same format as Scaffold Step 7), with these differences:
- Header: "ECW Initialization Complete (Attach Mode)"
- Knowledge section shows: "已有 — 未修改" for each domain directory
- Common knowledge section shows: "已有 — 未修改" if files exist, or "未检测到" if not

---

# Manual Mode

For when auto-scan doesn't find docs, or docs are outside `.claude/`.

## Manual Step 1: User Specifies Paths

Use `AskUserQuestion` (free-text):

```
请提供你的知识文档信息：

1. 知识根目录路径（可以是任何位置，例如 .claude/knowledge/、docs/、wiki/ 等）
2. 域列表，每行一个：
   目录名 | 域ID | 显示名称 | 描述 | 代码根目录

示例：
  知识根目录：docs/domains/
  
  order | order | 订单 | 订单全生命周期 | src/main/java/com/biz/order/
  payment | payment | 支付 | 支付退款对账 | src/main/java/com/biz/payment/
  logistics | logistics | 物流 | 配送运费 | src/main/java/com/biz/logistics/

如果还没有知识文档，只想先生成 ECW 配置，可以只提供域列表（不含知识根目录），后续再创建文档。
```

Parse the user's response to extract:
- Knowledge root path (optional — user may not have docs yet)
- List of domains with: `id`, `display_name`, `description`, `code_root`

## Manual Step 2: Validate Paths

For each path the user provided, verify it exists:

```bash
ls {knowledge_root}/ 2>/dev/null
ls {knowledge_root}/{domain_dir}/ 2>/dev/null
```

If any paths don't exist, use `AskUserQuestion`:

```
以下路径不存在：
{list of missing paths}

- 继续 — 不存在的路径保留在配置中，你可以后续创建目录和文件
- 修改 — 重新输入路径
```

If user chooses "继续", proceed with the paths as-is. Domain entries for missing paths will have `Entry Document = 00-index.md (待创建)`.

## Manual Step 3: Detect Language + Component Types

Same as Attach Step 3.

## Manual Step 4: Generate ECW Configuration

Same as Attach Step 4, using user-specified paths.

For domains where the knowledge directory doesn't exist:
- `Knowledge Root` in domain-registry.md: use the user-specified path (even if it doesn't exist yet)
- `Entry Document`: `00-index.md (待创建)`

## Manual Step 5: Skip Knowledge Directory Creation

Same as Attach Step 5 — do NOT create knowledge files. The user will create them when ready.

Exception: if the user explicitly asked for knowledge directories to be created during the AskUserQuestion in Step 1 (e.g., "也帮我创建知识目录骨架"), then create the directory structure and template files as in Scaffold Step 4.

## Manual Step 6: Generate CLAUDE.md Snippet

Same as Attach Step 6, using user-specified paths.

## Manual Step 7-8: Scanners + Summary

Same as Attach Step 7-8. Summary header: "ECW Initialization Complete (Manual Mode)".

---

# Scaffold Mode

For brand-new projects without existing documentation. Creates everything from scratch.

**This is the original `/ecw-init` flow, preserved unchanged.** The only difference is it's entered from Step 0's mode selection instead of being the default.

## Scaffold Step 1: Detect Project Language

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
- Bash: `find . -name "pom.xml" -maxdepth 3 | head -20` — if there are multiple pom.xml files in subdirectories, it is likely a multi-module project.

Store the detected `language` and `project_type` for later use.

## Scaffold Step 2: Collect Project Info via AskUserQuestion

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

Parse the user's response to extract project name, description, and confirmed language/type.

### 2b: Collect domain list

Use `AskUserQuestion`:

```
List your business domains. For each domain, provide:
- Domain ID (english, lowercase, hyphens, e.g., "order-management")
- Chinese name or display name
- One-line description
- Code root directory

Example:
1. order | 订单 | 订单从创建到完成的全生命周期管理 | src/main/java/com/example/biz/order/
2. payment | 支付 | 支付、退款、对账 | src/main/java/com/example/biz/payment/

Please list all your domains (one per line):
```

Parse into structured list: `id`, `display_name`, `description`, `code_root`.

### 2c: Collect component types

Use `AskUserQuestion`:

```
What categories of code components does your project use?

For each component type, provide:
- Name (e.g., Service, Repository, Controller, Manager)
- Grep pattern to find it in code (use {name} as placeholder)
- Search path

Common defaults by language:

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

Type "use defaults" for the standard set for your language:
```

## Scaffold Step 3: Scaffold Configuration Files

`mkdir -p .claude/ecw`

### 3a: Generate `ecw.yml`

Read `templates/ecw.yml`. Fill project info, component types, scan patterns for detected language.

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

Preserve template header/footer, "Add New Domain Guide" block, keyword matching rules, cross-domain data sources section.

### 3c: Copy `change-risk-classification.md`

Read and copy `templates/change-risk-classification.md` as-is.

### 3c2: Copy `calibration-log.md`

Read and copy `templates/calibration-log.md` as-is to `.claude/ecw/calibration-log.md`.

### 3d: Generate `ecw-path-mappings.md`

Read `templates/ecw-path-mappings.md`. Scan project for directory structure, generate mapping tables.

## Scaffold Step 4: Scaffold Knowledge Directories

### 4a: Common knowledge

```bash
mkdir -p .claude/knowledge/common
```

Read and copy 6 templates from `templates/knowledge/common/`:
1. `cross-domain-rules.md`
2. `cross-domain-calls.md`
3. `e2e-paths.md`
4. `external-systems.md`
5. `mq-topology.md`
6. `shared-resources.md`

### 4b: Per-domain knowledge

For each domain:

```bash
mkdir -p .claude/knowledge/{domain-id}/common/nodes
```

Read and copy 3 templates from `templates/knowledge/domain/`:
1. `00-index.md` → `.claude/knowledge/{domain-id}/00-index.md`
2. `business-rules.md` → `.claude/knowledge/{domain-id}/common/business-rules.md`
3. `data-model.md` → `.claude/knowledge/{domain-id}/common/data-model.md`

Replace `{{Domain Name}}` with display name and `{{DATE}}` with today's date.

## Scaffold Step 5: Generate CLAUDE.md Snippet

Read `templates/CLAUDE.md.snippet`. Fill domain routing table:

```markdown
| {keywords} | {display_name} | `.claude/knowledge/{domain-id}/00-index.md` |
```

Present to user: "Append to CLAUDE.md" / "Save as separate file" / "Skip"

## Scaffold Step 6: Optional Code Scanners (Java Only)

Skip if language ≠ Java or `--skip-scanners`.

Ask user: "Run all scanners" / "Skip scanners"

If run: check `scripts/java/` for scanner scripts, execute them if they exist.

## Scaffold Step 7: Output Summary

```markdown
## ECW Initialization Complete (Scaffold Mode)

### Project Configuration
- **Project:** {project_name}
- **Language:** {language}
- **Type:** {project_type}
- **Domains:** {count} domains registered

### Files Created

#### Configuration (.claude/ecw/)
| File | Status |
|------|--------|
| `ecw.yml` | Created |
| `domain-registry.md` | Created |
| `change-risk-classification.md` | Created |
| `ecw-path-mappings.md` | Created |
| `calibration-log.md` | Created |

#### Knowledge — Common (.claude/knowledge/common/)
| File | Status |
|------|--------|
| `cross-domain-rules.md` | Created |
| `cross-domain-calls.md` | Created |
| `e2e-paths.md` | Created |
| `external-systems.md` | Created |
| `mq-topology.md` | Created |
| `shared-resources.md` | Created |

#### Knowledge — Domains
| Directory | Files | Status |
|-----------|-------|--------|
| `.claude/knowledge/{domain-id}/` | 00-index.md, common/business-rules.md, common/data-model.md | Created |

#### CLAUDE.md Integration
| Action | Status |
|--------|--------|
| Domain routing snippet | {Appended / Saved / Skipped} |

### What to Do Next

1. **Review `ecw.yml`**: Customize `scan_patterns` and `component_types`.
2. **Review `ecw-path-mappings.md`**: Verify directory-to-domain mappings. Fix any `?` entries.
3. **Customize `change-risk-classification.md`**: Replace `{your_...}` placeholders.
4. **Fill domain knowledge files**: Each domain's template files contain `{{...}}` placeholders.
5. **Populate common knowledge files**: Fill cross-domain integration data.
6. **Refine CLAUDE.md keywords**: Add domain-specific terms.
7. **Validate**: Run `/ecw-validate-config` to check configuration completeness.
```

---

# Error Handling

- If any Write operation fails, report the error and continue with remaining files.
- If the user's input is ambiguous, ask a clarifying follow-up question rather than guessing.
- If a template file cannot be read from the plugin directory, report: "Could not read template file at {path}. The plugin installation may be incomplete."
