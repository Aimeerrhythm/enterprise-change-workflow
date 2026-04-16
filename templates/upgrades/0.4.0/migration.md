# ECW v0.4.0 Migration

## 概述

v0.4.0 移除了对 `superpowers` 插件的依赖。ECW 现在自包含所有 Skill，无需安装其他插件。

**Breaking Change**: 所有 `superpowers:*` 引用已替换为 `ecw:*` 对应项。

## 迁移清单

### 迁移 A: 更新项目 CLAUDE.md 中的 superpowers 引用

- **条件**: 所有使用 ECW 的项目
- **操作**: 在项目 CLAUDE.md 中搜索并替换以下引用：

| 旧引用 | 新引用 |
|--------|--------|
| `superpowers:writing-plans` | `ecw:writing-plans` |
| `superpowers:test-driven-development` | `ecw:tdd` |
| `superpowers:systematic-debugging` | `ecw:systematic-debugging` |
| `superpowers:subagent-driven-development` | `ecw:impl-orchestration` |
| `superpowers:executing-plans` | `ecw:impl-orchestration`（直接实现模式） |

- **幂等检查**: 搜索 `superpowers:` 关键词。如果不存在，跳过并输出："CLAUDE.md 中无 superpowers 引用，跳过迁移 A"

### 迁移 B: 更新 CLAUDE.md.snippet 中的引用

- **条件**: 项目使用了 CLAUDE.md.snippet 模板
- **操作**: 如果项目 CLAUDE.md 中包含从旧版 CLAUDE.md.snippet 复制的内容，检查并替换其中的 superpowers 引用
- **幂等检查**: 同迁移 A

### 迁移 C: 移除 superpowers 依赖声明（可选）

- **条件**: 如果项目安装了 superpowers 且仅为 ECW 服务
- **操作**: 提示用户可以卸载 superpowers 插件（如无其他用途）
- **注意**: 这是建议而非强制。superpowers 可能被其他项目使用

## 版本更新

```yaml
# ecw.yml
ecw_version: "0.4.0"
```

## 验证

迁移完成后运行 `/ecw-validate-config` 确认配置正确。
