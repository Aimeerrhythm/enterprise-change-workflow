# 域注册表 (Domain Registry)

> **关键词定义在 `CLAUDE.md` 域级知识路由表**（唯一维护点）。本文件仅维护域元数据，供 Agent 提示词生成使用。
> 流程：CLAUDE.md 关键词匹配 -> 域定位 -> 读取本文件元数据 -> Agent 提示词生成。

---

## 域定义

### 1. example-domain -- 示例域

| 属性 | 值 |
|------|-----|
| **Domain ID** | `example-domain` |
| **中文名** | 示例域 |
| **知识根目录** | `.claude/knowledge/example-domain/` |
| **入口文档** | `00-index.md` |
| **业务规则** | `common/business-rules.md` |
| **数据模型** | `common/data-model.md` |
| **代码根目录** | `{your_biz_root}/example-domain/` |
| **关联代码目录** | `{your_biz_root}/example-sub1/`, `{your_biz_root}/example-sub2/` |

**职责:** 一句话描述此域负责的业务范围。例如：负责订单从创建到完成的全生命周期管理，包括下单、支付、履约、取消四条链路。

---

<!-- 
  =============================================
  添加新域指南
  =============================================
  
  复制以下模板，替换占位符后粘贴在此处：

  ### {N}. {domain-id} -- {域中文名}

  | 属性 | 值 |
  |------|-----|
  | **Domain ID** | `{domain-id}` |
  | **中文名** | {域中文名} |
  | **知识根目录** | `.claude/knowledge/{domain-id}/` |
  | **入口文档** | `00-index.md` |
  | **业务规则** | `common/business-rules.md` |
  | **数据模型** | `common/data-model.md` |
  | **代码根目录** | `{your_biz_root}/{domain-id}/` |
  | **关联代码目录** | 列出此域涵盖的其他代码子目录（可选） |

  **职责:** 一句话描述此域的业务范围和核心链路。

  ---

  注意事项：
  1. Domain ID 使用英文小写 + 连字符，如 order-management、user-auth
  2. 知识根目录必须与 .claude/knowledge/ 下实际目录对应
  3. 入口文档 00-index.md 需要包含：链路速查、节点定位、Facade 地图、外部系统交互
  4. 同步在 CLAUDE.md 的域级知识路由表中添加对应关键词
  5. 同步在 ecw-path-mappings.md 中添加代码路径→域映射
  6. 如果域没有独立的业务规则或数据模型文档，可以省略对应行
-->

---

## 关键词匹配规则

Coordinator 从 `CLAUDE.md` 域级知识路由表读取关键词，匹配用户输入后定位到域，再从上方域定义读取元数据。

1. **每个关键词仅归属一个域**，不存在歧义（同一关键词不会出现在两个域中）。
2. 匹配结果决定协作模式：

| 匹配域数量 | 行为 |
|-----------|------|
| **0 个域匹配** | 提示用户补充更多描述信息，无法启动分析 |
| **1 个域匹配** | 提示单域需求建议使用 `requirements-elicitation` |
| **2+ 个域匹配** | 进入多域协作分析 |

---

## 跨域规则数据源

Coordinator 在合成阶段（synthesis）需要读取以下跨域文件，用于识别域间依赖、共享资源和端到端链路：

| 文件路径 | 说明 |
|---------|------|
| `.claude/knowledge/common/cross-domain-calls.md` | 域间直接调用矩阵 |
| `.claude/knowledge/common/mq-topology.md` | MQ Topic 发布/消费关系 |
| `.claude/knowledge/common/shared-resources.md` | 被 2+ 域使用的共享资源 |
| `.claude/knowledge/common/external-systems.md` | 外部系统集成 |
| `.claude/knowledge/common/e2e-paths.md` | 端到端关键链路 |

<!--
  以上跨域文件为可选项。初始化时可以先创建空文件，随着项目知识积累逐步补充：
  - cross-domain-calls.md: 扫描代码中的跨域注入/调用，生成调用矩阵
  - mq-topology.md: 列出所有 MQ Topic 及其生产者/消费者
  - shared-resources.md: 列出被多个域依赖的公共服务/Manager
  - external-systems.md: 列出所有外部系统集成点
  - e2e-paths.md: 描述核心业务的端到端调用链路
-->
