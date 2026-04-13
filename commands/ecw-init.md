---
name: ecw-init
description: Initialize Enterprise Change Workflow configuration for your project. Supports three modes — Attach (existing docs), Manual (user-specified paths), Scaffold (new project).
argument-hint: [--skip-scanners]
---

# ECW Init — 项目初始化向导

你正在执行 `/ecw-init` 命令。你的任务是检测项目的现有文档状态，选择合适的初始化模式，然后生成 ECW 配置文件。严格按以下步骤顺序执行，不要跳步。

**重要：** 此 skill 属于 `enterprise-change-workflow` 插件。下文引用的所有模板文件位于该插件的 `templates/` 目录。读取模板时，使用 Read 工具从插件安装路径读取（即包含此 `commands/` 文件夹的上级目录下的 `templates/`）。

---

## Step 0：智能发现 + 模式选择

### 0a：扫描现有文档

扫描 **两个信息源** 以检测已有的知识文档：

**来源 A — `.claude/` 目录结构：**

```bash
# 列出 .claude/ 下所有 .md 文件，排除已知的配置目录
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

# 列出 .claude/ 下的一级目录
find .claude/ -mindepth 1 -maxdepth 1 -type d 2>/dev/null
```

统计候选知识目录数量（包含 ≥ 2 个 `.md` 文件且不在排除集合 `ecw/`、`rules/`、`guides/`、`project/`、`specs/`、`plans/`、`plugins/` 中的目录）。

**来源 B — `CLAUDE.md` 内容：**

如果项目根目录存在 `CLAUDE.md`：
- 用 Read 工具读取内容
- 搜索匹配 `.claude/knowledge/`、`.claude/docs/`、`knowledge/` 等路径引用，以及任何指向文档的 `.claude/{something}/` 引用
- 搜索域路由表（包含域名和路径的 markdown 表格）
- 搜索域关键词或业务领域描述

### 0b：选择模式

根据扫描结果，展示以下场景之一：

**场景 A — 发现知识目录：**

使用 `AskUserQuestion`：

```
检测到 .claude/ 下已有 {N} 个知识目录、{M} 个 .md 文件。

- Attach（推荐）— 基于已有文档生成 ECW 配置，不动已有文件
- Manual — 我自己指定知识目录路径和域信息
- Scaffold — 忽略已有文件，从零创建全部配置 + 知识模板
```

将 "Attach" 标记为推荐选项。

**场景 B — 未发现知识目录：**

使用 `AskUserQuestion`：

```
未检测到已有知识文档结构。

- Scaffold（推荐）— 从零创建全部配置 + 知识模板
- Manual — 我有知识文档但不在 .claude/ 下，手动指定路径
- Attach — 强制扫描（可能漏检了）
```

将 "Scaffold" 标记为推荐选项。

### 0c：路由到对应模式

- **Attach** → 跳转到 "Attach 模式" 章节
- **Manual** → 跳转到 "Manual 模式" 章节
- **Scaffold** → 跳转到 "Scaffold 模式" 章节

---

# Attach 模式

适用于已有文档的项目。扫描发现后由用户确认，仅生成 ECW 配置。

## Attach Step 1：深度扫描与结构发现

构建现有文档结构的完整画像：

```
1. 根据 Step 0 的扫描结果，按父目录对 .md 文件分组。

2. 识别"知识根目录"——包含多个子目录且每个子目录含 .md 文件的目录。
   常见模式：
   - .claude/knowledge/  (包含 inbound/、outbound/、task/ 等)
   - .claude/docs/       (包含 order/、payment/ 等)
   - docs/               (.claude/ 外部)
   
   启发式规则：包含 ≥ 3 个含 .md 文件的子目录的最深公共祖先目录。

3. 在知识根目录下，对每个子目录分类：
   - "域候选"：包含某个业务领域相关的 .md 文件
   - "公共/共享"：名为 common/、shared/，或包含跨域文档
   - "其他"：不属于以上类别

4. 对每个域候选统计：
   - .md 文件总数（递归）
   - 是否存在 00-index.md
   - 是否存在 business-rules.md 或 data-model.md（递归搜索，记录相对路径，如 `common/business-rules.md`、`checkstock/common/business-rules.md`）

5. 同时检查 CLAUDE.md 获取额外线索：
   - 如果 CLAUDE.md 中有域路由表，提取域名和路径
   - 如果 CLAUDE.md 引用的路径在文件系统扫描中未找到，标注出来
```

## Attach Step 2：展示并确认

使用 `AskUserQuestion`（自由文本）展示发现结果并收集域信息：

```
扫描发现以下文档结构：

知识根目录（推测）：{detected_knowledge_root}
{对每个子目录展示:}
  ├── {dirname}/          ({file_count} files) {— 公共知识 if common/shared}
  ...

{如果 CLAUDE.md 中有域路由表:}
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

解析用户回复，提取：
- 确认后的知识根目录路径（可能与检测值不同）
- 域列表，每个域包含：`id`、`display_name`、`description`、`code_root`、`knowledge_path`（知识根目录下的完整路径）
- 排除的目录

## Attach Step 3：检测语言和组件类型

与 Scaffold Step 1 + Step 2c 相同：

1. **检测项目语言**，扫描构建文件：

```bash
ls pom.xml build.gradle build.gradle.kts package.json go.mod pyproject.toml requirements.txt 2>/dev/null
```

| 检测到的文件 | 语言 | 项目类型 |
|-------------|------|---------|
| `pom.xml` | java | java-monolith（多模块则为 java-microservice） |
| `build.gradle` / `build.gradle.kts` | java/kotlin | java-monolith/microservice |
| `package.json` | typescript | node |
| `go.mod` | go | go-monolith |
| `pyproject.toml` / `requirements.txt` | python | python |

对 Java 项目，检查是否多模块：`find . -name "pom.xml" -maxdepth 3 | head -20`

2. **向用户确认**，使用 `AskUserQuestion`：

```
检测到：Language = {language}, Type = {type}
是否正确？如需修改请说明。
组件类型使用默认还是自定义？（输入 "use defaults" 使用默认）
```

3. 如选择 "use defaults"，为检测到的语言生成标准组件类型。

## Attach Step 4：生成 ECW 配置

创建 `.claude/ecw/` 目录：`mkdir -p .claude/ecw`

### 4a：生成 `ecw.yml`

读取 `templates/ecw.yml` 模板。填入：
- `project.name`、`project.type`、`project.language`（来自 Step 3）
- `component_types`（来自 Step 3）
- `scan_patterns`：保留与检测语言匹配的默认值

### 4b：生成 `domain-registry.md`

读取 `templates/domain-registry.md` 模板。为每个确认的域生成一个区块，使用 **实际路径**：

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

与 Scaffold 的关键区别：`Knowledge Root` 使用用户确认的 **实际路径**（如 `.claude/knowledge/inbound/`），而非模板占位符。

`Business Rules` 和 `Data Model` 的确定（使用 Step 1 的扫描结果）：
- 如果域目录中递归找到 `business-rules.md` → 使用相对于域知识根目录的路径（如 `common/business-rules.md`、`checkstock/common/business-rules.md`）
- 如果找到多个 → 全部列出，用逗号分隔并标注子模块名（如 `checkstock/common/business-rules.md`（盘点）, `move/common/business-rules.md`（移库））
- 如果未找到 → 标注"无独立文件"
- `Data Model` 同理

`Entry Document` 的确定：
- 如果域目录中存在 `00-index.md` → 使用它
- 否则 → 使用该目录下第一个 `.md` 文件（按字母排序）
- 如果目录为空 → 使用 `00-index.md (待创建)`

### 4c：复制 `change-risk-classification.md`

读取 `templates/change-risk-classification.md` 模板。原样写入 `.claude/ecw/change-risk-classification.md`。

### 4c2：复制 `calibration-log.md`

读取 `templates/calibration-log.md` 模板。原样写入 `.claude/ecw/calibration-log.md`。此文件用于积累 Phase 3 校准记录。

### 4d：生成 `ecw-path-mappings.md`

读取 `templates/ecw-path-mappings.md` 模板。自动发现项目目录结构：

对 Java 项目：
```bash
find . -type d -name "biz" -path "*/main/java/*" | head -5
ls <detected_biz_root>/ 2>/dev/null
find . -type d \( -name "shared" -o -name "common" -o -name "infra" \) -path "*/main/java/*" | head -10
find . -type d \( -name "interfaces" -o -name "controller" \) -path "*/main/java/*" | head -10
find . -type d -name "mapper" -path "*/resources/*" | head -5
```

将发现的子目录映射到已确认的域。

## Attach Step 5：跳过知识目录创建

**不要创建、修改或覆盖任何已有文档文件。** 这是与 Scaffold 模式的核心区别。用户的现有知识文件原样保留。

## Attach Step 6：生成 CLAUDE.md 代码片段

读取 `templates/CLAUDE.md.snippet` 模板。

使用用户确认的 **实际路径** 填写域路由表：

```markdown
| 关键词 | 域 | 入口文档 |
|--------|-----|---------|
| {keywords} | {display_name} | `{actual_knowledge_path}/{entry_file}` |
```

`{keywords}` 的生成：从域显示名称 + 描述中提取关键词，用 `/` 分隔。

入口文件路径：
- 如果存在 `00-index.md` → 使用它
- 如果不存在 → 使用目录中第一个 `.md` 文件
- 如果目录为空 → 标记 `(待创建)`

通过 `AskUserQuestion` 向用户展示代码片段：
- "追加到 CLAUDE.md" / "保存为 .claude/ecw/CLAUDE.md.snippet" / "跳过"

## Attach Step 7：可选代码扫描器（仅 Java）

如果语言不是 Java 或传入了 `--skip-scanners`，则跳过。

与 Scaffold Step 6 相同：提供运行 `scripts/java/` 下 Java 扫描脚本的选项。

## Attach Step 8：输出总结

输出结构化总结（格式与 Scaffold Step 7 相同），区别如下：
- 标题："ECW 初始化完成（Attach 模式）"
- 知识文件部分显示："已有 — 未修改"（每个域目录）
- 公共知识部分显示：文件存在则 "已有 — 未修改"，不存在则 "未检测到"

---

# Manual 模式

适用于自动扫描未找到文档，或文档在 `.claude/` 外部的情况。

## Manual Step 1：用户指定路径

使用 `AskUserQuestion`（自由文本）：

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

解析用户回复，提取：
- 知识根目录路径（可选——用户可能还没有文档）
- 域列表，每个域包含：`id`、`display_name`、`description`、`code_root`

## Manual Step 2：验证路径

对用户提供的每个路径，验证是否存在：

```bash
ls {knowledge_root}/ 2>/dev/null
ls {knowledge_root}/{domain_dir}/ 2>/dev/null
```

如果有路径不存在，使用 `AskUserQuestion`：

```
以下路径不存在：
{list of missing paths}

- 继续 — 不存在的路径保留在配置中，你可以后续创建目录和文件
- 修改 — 重新输入路径
```

如用户选择 "继续"，按原路径继续。缺失路径的域条目中 `Entry Document = 00-index.md (待创建)`。

## Manual Step 3：检测语言和组件类型

与 Attach Step 3 相同。

## Manual Step 4：生成 ECW 配置

与 Attach Step 4 相同，使用用户指定的路径。

对知识目录不存在的域：
- `domain-registry.md` 中的 `Knowledge Root`：使用用户指定的路径（即使不存在）
- `Entry Document`：`00-index.md (待创建)`

## Manual Step 5：跳过知识目录创建

与 Attach Step 5 相同 — 不要创建知识文件。用户准备好后自行创建。

例外：如果用户在 Step 1 的 AskUserQuestion 中明确要求创建知识目录（如 "也帮我创建知识目录骨架"），则按 Scaffold Step 4 的方式创建目录结构和模板文件。

## Manual Step 6：生成 CLAUDE.md 代码片段

与 Attach Step 6 相同，使用用户指定的路径。

## Manual Step 7-8：扫描器 + 总结

与 Attach Step 7-8 相同。总结标题："ECW 初始化完成（Manual 模式）"。

---

# Scaffold 模式

适用于没有现有文档的全新项目。从零创建所有内容。

**此模式保留了原始 `/ecw-init` 的完整流程。** 唯一区别是通过 Step 0 的模式选择进入，而非作为默认模式。

## Scaffold Step 1：检测项目语言

扫描项目根目录的构建文件以检测语言和项目类型：

| 检测到的文件 | 语言 | 项目类型 |
|-------------|------|---------|
| `pom.xml` | java | java-monolith（子模块下有多个 `pom.xml` 则为 java-microservice） |
| `build.gradle` 或 `build.gradle.kts` | java（或 kotlin） | java-monolith（或 java-microservice） |
| `package.json` | typescript | node |
| `go.mod` | go | go-monolith |
| `pyproject.toml` 或 `requirements.txt` | python | python |

使用 Bash 检查：`ls pom.xml build.gradle build.gradle.kts package.json go.mod pyproject.toml requirements.txt 2>/dev/null`

如检测到多个构建系统，选择主要的（如即使存在 `package.json` 用于前端工具，Java 项目仍以 `pom.xml` 为准）。

对 Java 项目，额外检查是否为多模块项目：
- Bash：`find . -name "pom.xml" -maxdepth 3 | head -20` — 如果子目录中有多个 pom.xml，则很可能是多模块项目。

保存检测到的 `language` 和 `project_type` 供后续使用。

## Scaffold Step 2：通过 AskUserQuestion 收集项目信息

### 2a：确认项目基本信息

使用 `AskUserQuestion` 展示检测信息并收集：

```
检测到以下项目配置：
- 语言：{detected_language}
- 项目类型：{detected_project_type}

请提供：
1. 项目名称（用于 Agent 提示词的上下文）
2. 项目简介（1-2 句）
3. 检测到的语言/类型是否正确？如需修改请说明。
```

解析用户回复，提取项目名称、描述、确认后的语言/类型。

### 2b：收集域列表

使用 `AskUserQuestion`：

```
请列出你的业务域。每个域需要提供：
- 域 ID（英文、小写、连字符，如 "order-management"）
- 中文名称或显示名称
- 一句话描述
- 代码根目录

示例：
1. order | 订单 | 订单从创建到完成的全生命周期管理 | src/main/java/com/example/biz/order/
2. payment | 支付 | 支付、退款、对账 | src/main/java/com/example/biz/payment/

请列出所有域（每行一个）：
```

解析为结构化列表：`id`、`display_name`、`description`、`code_root`。

### 2c：收集组件类型

使用 `AskUserQuestion`：

```
你的项目使用了哪些代码组件类别？

每种组件类型需要提供：
- 名称（如 Service、Repository、Controller、Manager）
- 代码中的 grep 匹配模式（用 {name} 作为占位符）
- 搜索路径

各语言常见默认值：

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

输入 "use defaults" 使用你所用语言的标准组件集：
```

## Scaffold Step 3：生成配置文件

`mkdir -p .claude/ecw`

### 3a：生成 `ecw.yml`

读取 `templates/ecw.yml`。填入项目信息、组件类型、检测语言对应的扫描模式。

### 3b：生成 `domain-registry.md`

读取 `templates/domain-registry.md`。为每个域生成一个区块：

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

保留模板的头部/尾部、"新增域指南" 区块、关键词匹配规则、跨域数据源章节。

### 3c：复制 `change-risk-classification.md`

读取并原样复制 `templates/change-risk-classification.md`。

### 3c2：复制 `calibration-log.md`

读取并原样复制 `templates/calibration-log.md` 到 `.claude/ecw/calibration-log.md`。

### 3d：生成 `ecw-path-mappings.md`

读取 `templates/ecw-path-mappings.md`。扫描项目目录结构，生成映射表。

## Scaffold Step 4：创建知识目录骨架

### 4a：公共知识

```bash
mkdir -p .claude/knowledge/common
```

读取并复制 `templates/knowledge/common/` 下的 6 个模板：
1. `cross-domain-rules.md`
2. `cross-domain-calls.md`
3. `e2e-paths.md`
4. `external-systems.md`
5. `mq-topology.md`
6. `shared-resources.md`

### 4b：域级知识

对每个域：

```bash
mkdir -p .claude/knowledge/{domain-id}/common/nodes
```

读取并复制 `templates/knowledge/domain/` 下的 3 个模板：
1. `00-index.md` → `.claude/knowledge/{domain-id}/00-index.md`
2. `business-rules.md` → `.claude/knowledge/{domain-id}/common/business-rules.md`
3. `data-model.md` → `.claude/knowledge/{domain-id}/common/data-model.md`

将 `{{Domain Name}}` 替换为显示名称，`{{DATE}}` 替换为当天日期。

## Scaffold Step 5：生成 CLAUDE.md 代码片段

读取 `templates/CLAUDE.md.snippet`。填写域路由表：

```markdown
| {keywords} | {display_name} | `.claude/knowledge/{domain-id}/00-index.md` |
```

向用户展示："追加到 CLAUDE.md" / "保存为单独文件" / "跳过"

## Scaffold Step 6：可选代码扫描器（仅 Java）

如果语言不是 Java 或传入了 `--skip-scanners`，则跳过。

询问用户："运行所有扫描器" / "跳过扫描器"

如运行：检查 `scripts/java/` 下的扫描脚本，存在则执行。

## Scaffold Step 7：输出总结

```markdown
## ECW 初始化完成（Scaffold 模式）

### 项目配置
- **项目名称：** {project_name}
- **语言：** {language}
- **类型：** {project_type}
- **域数量：** {count} 个域已注册

### 已创建文件

#### 配置文件（.claude/ecw/）
| 文件 | 状态 |
|------|------|
| `ecw.yml` | 已创建 |
| `domain-registry.md` | 已创建 |
| `change-risk-classification.md` | 已创建 |
| `ecw-path-mappings.md` | 已创建 |
| `calibration-log.md` | 已创建 |

#### 知识文件 — 公共（.claude/knowledge/common/）
| 文件 | 状态 |
|------|------|
| `cross-domain-rules.md` | 已创建 |
| `cross-domain-calls.md` | 已创建 |
| `e2e-paths.md` | 已创建 |
| `external-systems.md` | 已创建 |
| `mq-topology.md` | 已创建 |
| `shared-resources.md` | 已创建 |

#### 知识文件 — 域级
| 目录 | 文件 | 状态 |
|------|------|------|
| `.claude/knowledge/{domain-id}/` | 00-index.md, common/business-rules.md, common/data-model.md | 已创建 |

#### CLAUDE.md 集成
| 操作 | 状态 |
|------|------|
| 域路由代码片段 | {已追加 / 已保存 / 已跳过} |

### 后续步骤

1. **检查 `ecw.yml`**：自定义 `scan_patterns` 和 `component_types`。
2. **检查 `ecw-path-mappings.md`**：验证目录到域的映射。修正所有 `?` 条目。
3. **定制 `change-risk-classification.md`**：替换 `{your_...}` 占位符。
4. **填充域知识文件**：每个域的模板文件包含 `{{...}}` 占位符。
5. **填充公共知识文件**：填入跨域集成数据。
6. **完善 CLAUDE.md 关键词**：添加域专属术语。
7. **验证**：运行 `/ecw-validate-config` 检查配置完整性。
```

---

# 错误处理

- 如果任何 Write 操作失败，报告错误后继续处理剩余文件。
- 如果用户输入有歧义，追问澄清而非猜测。
- 如果无法从插件目录读取模板文件，报告："无法读取模板文件 {path}。插件安装可能不完整。"
