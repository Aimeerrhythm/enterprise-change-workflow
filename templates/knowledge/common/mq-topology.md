# 消息队列拓扑

> 数据来源：MQ 常量、发布者和消费监听器代码扫描
> 最近扫描时间：{{SCAN_DATE}}

<!--
用途：本文档映射系统中的每一个消息队列 Topic——谁发布、谁消费、
每条消息触发什么业务动作。它对于理解域之间及与外部系统的异步耦合至关重要。

填充方法：
1. 找到代码库中所有 Topic/RoutingKey 常量。
2. 对每个 Topic，识别发布者类和消费监听器类。
3. 将每个 Topic 归类为：内部、外部入站、外部出站。
4. 记录消费触发的业务动作。
-->

## 内部 Topic

<!--
在同一系统内发布和消费的消息。
用于域间的异步解耦。
-->

| Topic | 发布方域 | 发布方类 | 消费方域 | 消费监听器 | 业务动作 | 备注 |
|-------|---------|---------|---------|----------|---------|------|
| `app.internal.order.created` | orders | OrderBizBuilder | fulfillment | OrderCreatedListener | 发起履约流程 | -- |
| `app.internal.payment.confirmed` | payments | PaymentService | orders | PaymentConfirmedListener | 更新订单状态为已支付 | -- |
| `{{topic}}` | {{domain}} | {{class}} | {{domain}} | {{listener}} | {{action}} | {{notes}} |

## 外部入站 Topic（本系统消费，外部发布）

<!--
来自外部系统、由本系统消费的消息。
代表集成入口点。
-->

| Topic | 外部系统 | 消费方域 | 消费监听器 | 业务动作 | 备注 |
|-------|---------|---------|----------|---------|------|
| `ext.erp.product.sync` | ERP | catalog | ProductSyncListener | 同步商品主数据 | -- |
| `ext.payment-gateway.webhook` | 支付服务商 | payments | PaymentWebhookListener | 处理支付结果回调 | -- |
| `{{topic}}` | {{system}} | {{domain}} | {{listener}} | {{action}} | {{notes}} |

## 外部出站 Topic（本系统发布，外部消费）

<!--
本系统发布、供外部系统消费的消息。
代表集成出口点。
-->

| Topic | 发布方域 | 发布方类 | 外部消费方 | 业务动作 | 备注 |
|-------|---------|---------|----------|---------|------|
| `app.to-erp.inventory.change` | inventory | StockChangePublisher | ERP | 通知 ERP 库存变动 | -- |
| `app.to-notification.order.shipped` | shipping | ShippingService | 通知服务 | 触发发货通知给客户 | -- |
| `{{topic}}` | {{domain}} | {{class}} | {{consumer}} | {{action}} | {{notes}} |

## 索引同步 Topic（可选）

<!--
如果系统发布专门用于搜索索引更新、数据同步或分析管道的消息，在此列出。
-->

| Topic | 发布方域 | 发布方类 | 目标系统 | 备注 |
|-------|---------|---------|---------|------|
| `app.to-search.order.index.update` | orders | OrderIndexWriter | Search/OpenSearch | 订单搜索索引同步 |
| `{{topic}}` | {{domain}} | {{class}} | {{target}} | {{notes}} |

## 统计

| 类别 | 数量 |
|------|------|
| 内部 Topic | {{count}} |
| 外部入站 Topic | {{count}} |
| 外部出站 Topic | {{count}} |
| 索引同步 Topic | {{count}} |
| **合计** | **{{total}}** |

## 监听器总览

<!--
所有消费监听器的扁平列表，便于快速查找。
-->

| 监听器类 | 包/目录 | 所属域 | 消费 Topic |
|---------|--------|-------|-----------|
| OrderCreatedListener | listeners/fulfillment | fulfillment | `app.internal.order.created` |
| ProductSyncListener | listeners/catalog | catalog | `ext.erp.product.sync` |
| {{listener}} | {{path}} | {{domain}} | {{topic}} |

---

## 维护指南

1. **新增 Topic**：在上方对应章节添加条目并更新统计表。
2. **变更消息 Schema**：在本文档中找到该 Topic 的所有消费方，协调变更。
3. **废弃 Topic**：移除前先明确标记；确认零消费方后再删除。
4. **MQ Exchange/Broker 配置**：如有需要，在下方子章节中记录与你的 MQ 平台相关的 Exchange 或路由细节（RabbitMQ Exchange、Kafka Partition、RocketMQ Group 等）。
