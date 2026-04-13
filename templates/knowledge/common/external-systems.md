# 外部系统集成

> 数据来源：代码扫描 + 架构文档
> 最近扫描时间：{{SCAN_DATE}}
> 扫描范围：MQ 常量、RPC 引用、HTTP 客户端、SDK 客户端

<!--
用途：本文档按外部系统分类，记录应用与之集成的每一个外部系统。
对每个系统，列出所有集成点——MQ Topic、RPC/gRPC 调用、HTTP 端点和 SDK 用法，
包含方向、所属域和业务上下文。

填充方法：
1. 扫描所有外部 RPC 引用（如 @DubboReference、gRPC stub、Feign client）。
2. 扫描所有跨系统边界的 MQ Topic。
3. 扫描所有调用外部 URL 的 HTTP 客户端。
4. 按外部系统分组整理结果。
-->

## 汇总

| 维度 | 数量 |
|------|------|
| 外部系统 | {{count}} |
| MQ Topic（入站） | {{count}} |
| MQ Topic（出站） | {{count}} |
| MQ Topic（内部） | {{count}} |
| RPC 引用（出站） | {{count}} |
| RPC 服务（对外暴露） | {{count}} |
| HTTP 集成 | {{count}} |

---

## 按系统分类的集成详情

<!--
对每个外部系统重复此章节。包含：
- 系统名称和描述
- 集成层（封装类、SDK 客户端等）
- 所有集成点的表格

方向取值：入站（外部 -> 本系统）、出站（本系统 -> 外部）、双向
类型取值：MQ、RPC/Dubbo、gRPC、HTTP、SDK、WebSocket 等
-->

### {{System Name}}（{{简要描述}}）

集成层：`{{path-to-wrapper-or-client-code}}`
RPC 引用：`{{list of remote interfaces}}`

| 方向 | 类型 | Topic / 接口 / 端点 | 所属域 | 业务场景 | 影响描述 |
|------|------|-------------------|-------|---------|---------|
| 入站 | MQ | `ext.system.order.create` | orders | 接收来自外部系统的新订单 | 订单创建入口；Schema 变更需与对方协调 |
| 出站 | MQ | `app.to-system.order.status` | orders | 通知外部系统订单状态变更 | 状态同步；消息格式变更需与下游协调 |
| 出站 | RPC | `ExternalFacade.queryProduct()` | catalog | 从外部系统查询商品详情 | 只读；接口版本变更可能导致调用失败 |
| 出站 | HTTP | `POST /api/v1/webhook` | notifications | 推送事件通知 | 需认证；端点变更需更新配置 |
| {{direction}} | {{type}} | {{topic_or_interface}} | {{domain}} | {{scenario}} | {{impact}} |

---

### {{Another System Name}}（{{简要描述}}）

集成层：`{{path}}`

| 方向 | 类型 | Topic / 接口 / 端点 | 所属域 | 业务场景 | 影响描述 |
|------|------|-------------------|-------|---------|---------|
| {{direction}} | {{type}} | {{topic_or_interface}} | {{domain}} | {{scenario}} | {{impact}} |

---

## 对外暴露的服务

<!--
如果应用对外暴露了 API（RPC、REST、gRPC）供外部系统调用，
在此列出。这有助于理解系统的"入站接口面"。
-->

| 暴露接口 | 所属域 | 描述 |
|---------|-------|------|
| OrderFacade | orders | 订单 CRUD 操作 |
| StockQueryFacade | inventory | 库存查询 |
| {{facade_class}} | {{domain}} | {{description}} |

## 内部异步 Topic（自产自消）

<!--
这些 Topic 不涉及外部系统。它们用于内部异步解耦。
变更时只需考虑内部消费方。
-->

| Topic | 常量名 | 所属域 | 业务场景 |
|-------|-------|-------|---------|
| `app.internal.order.index.update` | ORDER_INDEX_ROUTING_KEY | orders | 订单搜索索引重建 |
| `{{topic}}` | {{constant}} | {{domain}} | {{scenario}} |

---

## 关键代码位置

<!--
集成代码在代码库中的快速索引。
-->

| 类别 | 路径 |
|------|------|
| MQ 常量 | `{{path-to-mq-constants}}` |
| RPC 配置 | `{{path-to-rpc-config}}` |
| 外部调用封装层 | `{{path-to-wrapper-layer}}/` |
| MQ 监听器 | `{{path-to-listeners}}/` |
| 对外暴露的 RPC 服务 | `{{path-to-facade-impls}}/` |

---

## 维护指南

1. **新增外部系统**：按上方模板格式新建一个章节。
2. **变更消息 Schema**：与外部系统团队协调；在本文档中找出引用该系统的所有 Topic。
3. **升级 RPC 接口版本**：检查本文档中列出的所有引用，并相应更新封装代码。
4. **监控**：为外部调用失败设置告警；本文档有助于识别受影响的业务流程。
