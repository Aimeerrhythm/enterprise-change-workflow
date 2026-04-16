# ECW v0.2.0 迁移 — TDD 流程集成

## 概述

本版本在 ECW 工作流中集成 TDD（测试先行）流程。主要变更：

1. **risk-classifier 路由嵌入 TDD:RED 步骤**（插件侧已完成，无需项目操作）
2. **impl-verify Round 3 测试验证增强**（插件侧已完成，无需项目操作）
3. **verify-completion hook 新增 TDD 测试覆盖提醒**（插件侧已完成，需项目配置开启）
4. **项目配置更新**（以下迁移步骤）

## 迁移步骤

### 迁移 A: ecw.yml 加入 tdd 配置

- **目标文件**: `.claude/ecw/ecw.yml`
- **操作**: 在 `verification:` 节之后、`paths:` 节之前（如果 paths 不存在则追加到文件末尾），插入 tdd 配置块
- **snippet 文件**: `ecw-yml.snippet.yml`
- **占位符处理**:
  - `{{base_test_class}}` — 通过 AskUserQuestion 收集。Java 默认建议 "BaseUnitTest"，Go 建议 "TestSuite"，其他留空
- **幂等检查**: 读取 ecw.yml，搜索 `tdd:` 顶级键。如果已存在，跳过并输出："ecw.yml 已包含 tdd 配置，跳过迁移 A"
- **额外操作**: 在 `project:` 节后追加 `ecw_version: "0.2.0"` 字段（如果不存在）

### 迁移 B: CLAUDE.md 核心约定更新

- **目标文件**: 项目根目录 `CLAUDE.md`
- **前置条件**: `CLAUDE.md` 必须存在，否则跳过并警告
- **操作（替换）**: 搜索核心约定中包含 `mvn test` 且包含"验证"或"用例"或"通过"的行。如果找到，替换为：
  ```
  - **测试先行（TDD）**：新功能/Bug 修复必须先写失败测试，再写实现代码。编译通过不代表逻辑正确，测试通过才算完成
  ```
  如果未找到匹配行，不做替换操作（用户可能已自定义）
- **不再注入 TDD 章节** — TDD 规则已由 ECW 插件（risk-classifier 路由 + ecw:tdd skill）和 patterns.md（迁移 C）覆盖，无需在项目 CLAUDE.md 中重复
- **snippet 文件**: 无（替换内容直接在本文件中定义）
- **幂等检查**: 搜索核心约定区域中的"测试先行"或"TDD"关键词。如果已存在，跳过并输出："CLAUDE.md 核心约定已包含 TDD 引用，跳过迁移 B"

### 迁移 C: patterns.md 加入 TDD 编码模式（仅 Java）

- **条件**: 
  1. `ecw.yml` 中 `project.language` 为 `"java"`
  2. 项目中存在 `.claude/guides/patterns.md`
  两个条件都满足才执行，否则跳过
- **目标文件**: `.claude/guides/patterns.md`
- **操作 1（SOP 更新）**: 搜索"新增方法 SOP"章节中的步骤列表。在 "BizServiceImpl 实现" 步骤之前插入 TDD 步骤：
  ```
  N. **TDD:RED — 先写 BizService 层失败测试**（参见下方 TDD 编码模式）
  ```
  并将后续步骤序号 +1。如果搜索不到 SOP 步骤列表，跳过此操作
- **操作 2（追加章节）**: 读取 `patterns-tdd-java.snippet.md`，替换占位符后追加到文件末尾（在最后一个 `---` 分隔线之后，或直接追加）
- **snippet 文件**: `patterns-tdd-java.snippet.md`
- **占位符处理**: 复用迁移 A/B 的值
- **幂等检查**: 搜索 `## TDD 编码模式` 标题。如果已存在，跳过并输出："patterns.md 已包含 TDD 编码模式，跳过迁移 C"
- **非 Java 项目**: 输出 "当前仅支持 Java 项目的 TDD 模式模板，后续版本将支持 Go/Node/Python"
