---
name: ecw-validate-config
description: Validate ECW configuration files for completeness and correctness. Checks for unfilled placeholders, missing files, and broken references.
---

# ECW 配置验证

你正在执行 `/ecw-validate-config` 命令。你的任务是检查项目的 ECW 配置完整性和正确性，然后输出结构化报告。严格按以下步骤顺序执行。

---

## Step 1：定位配置

检查 `.claude/ecw/` 目录是否存在。如不存在，报告：

```
ECW 未初始化。请先运行 /ecw-init 初始化项目配置。
```

然后停止。

如果目录存在，读取 `ecw.yml`：

```bash
cat .claude/ecw/ecw.yml
```

解析 `paths` 部分获取所有配置路径。如 paths 部分缺失，回退到默认值。

---

## Step 2：检查 ecw.yml

读取 `.claude/ecw/ecw.yml` 并检查：

### 2a：未填充的占位符

搜索未替换的模板占位符：
- `project.name` 中仍为 `"Your Project Name"`
- 值中包含 `{...}` 模式
- `component_types` 仍被注释（只有默认的 `Service` 条目）

### 2b：语言一致性

- `project.language` 应与项目根目录的文件匹配（pom.xml → java、go.mod → go 等）
- `scan_patterns` 的值应适配声明的语言

### 2c：路径有效性

对 `paths` 部分的每个路径，检查引用的文件/目录是否存在：
- `domain_registry`
- `risk_factors`
- `path_mappings`
- `knowledge_root`
- `knowledge_common`
- `calibration_log`（可选，可能尚不存在——不算错误）

---

## Step 3：检查 domain-registry.md

读取域注册表文件（路径来自 ecw.yml 或默认 `.claude/ecw/domain-registry.md`）。

### 3a：空白检查

如果文件中没有域区块（只有模板头部），标记：
- "域注册表为空，尚未注册任何业务域"

### 3b：逐域验证

对每个注册的域，提取：
- 域 ID
- 知识根目录路径
- 入口文档路径
- 代码根目录路径

检查：
- **知识根目录是否存在？** — `ls {knowledge_root}/ 2>/dev/null`
- **入口文档是否存在？** — 检查指定路径的文件是否存在
- **代码根目录是否存在？** — `ls {code_root}/ 2>/dev/null`
- **是否残留占位符？** — 是否有 `{{...}}` 或 `{your_...}` 模式

---

## Step 4：检查 ecw-path-mappings.md

读取路径映射文件（路径来自 ecw.yml 或默认 `.claude/ecw/ecw-path-mappings.md`）。

### 4a：空白检查

如果文件中没有映射行（只有头部），标记：
- "路径映射表为空，biz-impact-analysis 和完成验证 hook 的域匹配将依赖启发式规则"

### 4b：路径存在性

对每个映射行（`| path_prefix | domain |`）：
- 检查 `path_prefix` 目录是否存在于项目中
- 检查 `domain` 是否已在 domain-registry.md 中注册

标记不匹配项：
- 路径不存在 → "路径 `{path}` 不存在"
- 域未注册 → "域 `{domain}` 未在 domain-registry.md 中注册"

---

## Step 5：检查 change-risk-classification.md

读取风险分级文件。

### 5a：占位符检查

搜索未填充的占位符：
- `{your_...}` 模式
- `{{...}}` 模式
- `TODO` / `TBD` 标记

---

## Step 6：检查知识文件结构

### 6a：知识根目录

检查知识根目录是否存在。如不存在，标记：
- "知识根目录 `{path}` 不存在"

### 6b：公共知识

检查 `knowledge_common` 目录是否存在。如存在，检查标准文件：
- `cross-domain-rules.md`
- `cross-domain-calls.md`
- `mq-topology.md`
- `shared-resources.md`
- `external-systems.md`
- `e2e-paths.md`

对每个文件：检查是否存在，以及内容是否仍为模板占位符（文件大小 < 200 字节或仅包含标题）。

### 6c：域级知识

对域注册表中的每个域，检查其知识目录：
- 目录是否存在？
- `00-index.md`（或配置的入口文档）是否存在？
- 是否有包含实际内容的 `.md` 文件？

---

## Step 7：输出报告

输出结构化验证报告：

```markdown
## ECW 配置验证报告

### 总览

| 检查项 | 状态 |
|--------|------|
| ecw.yml | {pass/warn/fail} |
| domain-registry.md | {pass/warn/fail} |
| ecw-path-mappings.md | {pass/warn/fail} |
| change-risk-classification.md | {pass/warn/fail} |
| 知识文件结构 | {pass/warn/fail} |

### 问题清单

**必须修复（影响 ECW 功能）：**

{编号列表，或 "无"}

**建议修复（提升准确性）：**

{编号列表，或 "无"}

### 域健康度

| 域 | 注册 | 知识目录 | 入口文档 | 代码目录 | 路径映射 |
|----|------|---------|---------|---------|---------|
| {domain} | {ok/missing} | {ok/missing} | {ok/missing} | {ok/missing} | {ok/missing} |

### 建议操作

{按优先级排列的修复建议}
```

状态定义：
- **pass** — 配置完整，无问题
- **warn** — 配置存在但有待完善项（占位符、空文件）
- **fail** — 配置缺失或严重错误

---

## 错误处理

- 如果某个文件无法读取，记录错误后继续检查其他文件。
- 如果 ecw.yml 无法解析，报告解析错误并回退到默认路径继续剩余检查。
