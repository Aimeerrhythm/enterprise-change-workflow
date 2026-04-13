# 共享资源

> 数据来源：跨域边界的依赖注入代码扫描
> 最近扫描时间：{{SCAN_DATE}}

<!--
用途：本文档列出被 2 个或更多域注入使用的每个 Service、组件或 Manager 类。
这些是代码库中变更风险最高的目标——修改它们可能悄无声息地影响多个域。

填充方法：
1. 从跨域调用矩阵中，按被调用接口的调用方域数量进行分组。
2. 纳入所有被 2 个以上域消费的类。
3. 列出关键方法、消费域和影响描述。
-->

## 核心 Service（跨域共享）

<!--
跨多个限界上下文使用的域级 Service 接口。
这些是最关键的共享资源。

列定义：
- 共享资源：类或接口名称。
- 类型：架构层级（如 CoreService、Manager、Repository、Utility）。
- 消费方域（数量）：注入此资源的域列表及总数。
- 关键方法：此接口中使用最多的方法。
- 影响描述：此资源变更时会导致什么问题或降级。
-->

| 共享资源 | 类型 | 消费方域（数量） | 关键方法 | 影响描述 |
|---------|------|----------------|---------|---------|
| StockService | CoreService | orders, fulfillment, returns, inventory (4) | `reserve()`, `deduct()`, `release()`, `query()` | 库存操作影响所有订单/履约流程；方法签名变更需同步更新所有消费方 |
| UserQueryService | CoreService | orders, fulfillment, admin, reporting (4) | `getById()`, `queryByIds()`, `search()` | 用户查询是基础依赖；接口变更影响所有域 |
| NotificationService | CoreService | orders, shipping, payments (3) | `send()`, `sendBatch()` | 通知发送；行为变更影响所有面向客户的流程 |
| {{resource_name}} | {{type}} | {{domain_list}} ({{count}}) | {{methods}} | {{impact}} |

## Manager / 数据访问（跨域共享）

<!--
跨域共享的底层数据访问类。
-->

| 共享资源 | 类型 | 消费方域（数量） | 关键方法 | 影响描述 |
|---------|------|----------------|---------|---------|
| TransactionHelper | Utility | orders, inventory, fulfillment, payments (4) | `withTransaction()`, `afterTransaction()` | 事务行为变更影响所有域的数据一致性 |
| OrderRepository | Manager | orders, shipping, returns (3) | `findByOrderId()`, `updateStatus()` | 订单数据查询；Schema 或查询变更影响多个域 |
| {{resource_name}} | {{type}} | {{domain_list}} ({{count}}) | {{methods}} | {{impact}} |

## 风险分级

<!--
按消费方域数量对共享资源分组。
依赖某资源的域越多，变更风险越高。
-->

### 极高风险（6+ 域消费）
- **{{ResourceName}}** -- {{count}} 个域，{{brief_description}}

### 高风险（4-5 域消费）
- **{{ResourceName}}** -- {{count}} 个域，{{brief_description}}

### 中风险（2-3 域消费）
- **{{ResourceName}}** -- {{count}} 个域，{{brief_description}}

---

## 使用指南

1. **修改共享资源前**：grep 所有注入点以确认完整影响范围。不要仅依赖本文档。
2. **方法签名变更**：必须同步更新所有消费方域。
3. **新增方法**：风险较低，但需确保不破坏接口契约或引入意外副作用。
4. **行为变更（签名不变，逻辑改变）**：风险最高——需在所有消费方域进行完整回归测试。
