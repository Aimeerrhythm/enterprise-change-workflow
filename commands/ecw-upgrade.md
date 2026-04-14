---
name: ecw-upgrade
description: Upgrade ECW configuration in your project to the latest plugin version. Detects version gap, lists pending migrations, and applies changes with user confirmation.
---

# ECW Upgrade — 项目配置升级

你正在执行 `/ecw-upgrade` 命令。你的任务是检测当前项目的 ECW 配置版本与插件版本之间的差异，列出待执行的迁移，逐步应用变更。严格按以下步骤顺序执行，不要跳步。

**重要：** 此命令属于 `enterprise-change-workflow` 插件。下文引用的所有模板和迁移文件位于该插件的 `templates/` 目录。读取时使用 Read 工具从插件安装路径读取（即包含此 `commands/` 文件夹的上级目录下的 `templates/`）。

---

## Step 0：版本检测

### 0a：读取项目 ECW 版本

读取 `.claude/ecw/ecw.yml`。如果文件不存在：

```
ECW 未初始化。请先运行 /ecw-init 初始化项目配置。
```

然后停止。

从 ecw.yml 提取 `ecw_version` 字段。如果字段不存在，视为 `0.1.0`（首版不含版本字段）。

记录为 `current_version`。

### 0b：读取插件版本

读取插件目录下的 `package.json`，提取 `version` 字段。

记录为 `plugin_version`。

### 0c：版本比较

如果 `current_version` == `plugin_version`：

```markdown
## ECW 配置已是最新版本

当前版本：{current_version}
插件版本：{plugin_version}

无需升级。
```

然后停止。

如果 `current_version` > `plugin_version`：

```markdown
## 版本异常

项目 ECW 版本（{current_version}）高于插件版本（{plugin_version}）。
请检查是否安装了正确的插件版本。
```

然后停止。

---

## Step 1：扫描待执行的迁移

### 1a：列出可用迁移

扫描插件 `templates/upgrades/` 目录，列出所有子目录名（每个子目录名即版本号）。

```bash
ls templates/upgrades/
```

筛选出版本号 > `current_version` 且 <= `plugin_version` 的迁移。按版本号升序排列。

如果无待执行迁移（不应发生，因为 Step 0c 已检查）：

```
未找到待执行的迁移文件。插件版本已更新但无配置变更。
```

然后停止。

### 1b：读取迁移摘要

对每个待执行的迁移版本，读取 `templates/upgrades/{version}/migration.md`，提取 `## 概述` 章节内容。

### 1c：展示迁移列表并确认

使用 `AskUserQuestion` 向用户展示：

```
ECW 配置升级：{current_version} → {plugin_version}

待执行的迁移：

{version_1}:
  {概述内容}

{version_2}（如有）:
  {概述内容}

选项：
  1. "执行升级（推荐）" — 逐步执行所有迁移，每步确认
  2. "仅查看详情" — 显示详细迁移内容但不执行
  3. "跳过" — 不执行升级
```

如用户选择 "仅查看详情"：读取并展示每个迁移的完整 `migration.md` 内容，然后再次提问是否执行。

如用户选择 "跳过"：停止。

---

## Step 2：逐版本执行迁移

对每个待执行的版本（按升序），执行以下流程：

### 2a：读取迁移定义

读取 `templates/upgrades/{version}/migration.md`，提取 `## 迁移步骤` 章节中的每个迁移步骤。

### 2b：收集用户输入

在执行任何迁移步骤之前，先收集所有占位符的值。读取迁移定义中所有 snippet 文件的占位符（`{{...}}` 模式），去重后通过 AskUserQuestion 一次性收集：

```
配置升级需要以下信息：

1. 测试基类名称（Java 默认 "BaseUnitTest"，Go 默认 "TestSuite"）
2. 测试模块名称（如 "wms-service"、"app"、"src"）

请提供（或按回车接受默认值）：
```

### 2c：逐步执行迁移

按迁移定义中的顺序（A → B → C ...）执行每个步骤。每个步骤：

1. **幂等检查**：按迁移定义中的检查方式验证。如果已执行过，输出跳过原因并继续下一步
2. **条件检查**：如果步骤有条件（如"仅 Java"），验证条件。不满足则跳过
3. **读取目标文件**：使用 Read 工具读取项目中的目标文件
4. **读取 snippet 模板**：从插件 `templates/upgrades/{version}/` 读取
5. **替换占位符**：用 Step 2b 收集的值替换 `{{...}}`
6. **定位插入点**：按迁移定义中的指引定位。使用 Edit 工具的 old_string 匹配插入位置
7. **执行变更**：使用 Edit 或 Write 工具应用变更
8. **输出结果**：

```markdown
✓ 迁移 {step_id}: {描述}
  - 文件: {file_path}
  - 操作: {insert/replace/append}
  - 变更: {简述}
```

**错误处理**：

- 如果目标文件不存在 → 输出警告，跳过该步骤
- 如果 Edit 工具的 old_string 匹配失败 → 输出 "无法定位插入点，请手动添加以下内容到 {file_path}："，然后输出 snippet 内容
- 如果任何步骤出错 → 不阻塞后续步骤，记录错误到最终报告

---

## Step 3：更新版本号

**前置条件**：Step 2 中所有迁移步骤的最终状态均为"成功"或"跳过"（幂等命中）。如果有任何步骤状态为"失败"，**不更新版本号**，输出：

```markdown
## 部分迁移失败

以下步骤执行失败：
{失败步骤列表}

版本号未更新（仍为 {current_version}）。修复问题后重新运行 `/ecw-upgrade`。
已成功的步骤有幂等保护，重跑时会自动跳过。
```

然后跳转到 Step 4b 输出总结（不执行版本号更新）。

**全部成功或跳过时**，更新 `.claude/ecw/ecw.yml` 中的 `ecw_version` 字段：

- 如果已有 `ecw_version` 字段 → 用 Edit 工具替换为新版本
- 如果没有 `ecw_version` 字段 → 在 `project:` 节的最后一行之后插入：
  ```yaml
  ecw_version: "{plugin_version}"
  ```

---

## Step 4：验证与总结

### 4a：运行配置验证

提示用户可运行 `/ecw-validate-config` 验证升级后的配置完整性。

### 4b：输出升级总结

```markdown
## ECW 配置升级完成

**版本变更：** {current_version} → {plugin_version}

### 已执行的迁移

| 版本 | 步骤 | 状态 | 说明 |
|------|------|------|------|
| {version} | 迁移 A: {描述} | {成功/跳过(已存在)/跳过(条件不满足)/失败} | {详情} |
| {version} | 迁移 B: {描述} | {成功/跳过(已存在)/跳过(条件不满足)/失败} | {详情} |
| ... | ... | ... | ... |

### 已变更的文件

{列出所有被修改的文件路径}

### 后续操作

1. **检查变更内容** — 浏览上述文件，确认注入的内容符合预期
2. **自定义配置** — 根据项目情况调整 ecw.yml 中的 tdd 配置（如启用 check_test_files）
3. **替换占位符** — 检查注入内容中是否残留 `{{...}}` 占位符
4. **运行验证** — 执行 `/ecw-validate-config` 确认配置完整性
```

---

## 错误处理

- 如果 ecw.yml 无法解析，报告错误并停止（不执行任何迁移）
- 如果某个迁移步骤失败，记录错误后继续执行后续步骤
- 如果所有步骤都被跳过（全部幂等检查命中），仅更新版本号并输出 "配置已是最新，仅更新了版本号"
- 如果 snippet 模板无法读取，报告 "无法读取迁移模板 {path}。插件安装可能不完整。" 并跳过该步骤
