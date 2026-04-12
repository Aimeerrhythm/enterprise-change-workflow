# Message Queue Topology

> Data source: Code scan of MQ constants, publishers, and consumer listeners
> Last scanned: {{SCAN_DATE}}

<!--
PURPOSE: This document maps every message queue topic in the system -- who publishes,
who consumes, and what business action each message triggers. It is essential for
understanding async coupling between domains and with external systems.

HOW TO POPULATE:
1. Find all topic/routing-key constants in your codebase.
2. For each topic, identify the publisher class(es) and the consumer listener class(es).
3. Categorize each topic as Internal, External-Inbound, or External-Outbound.
4. Record the business action triggered by consumption.
-->

## Internal Topics

<!--
Messages published and consumed within the same system.
Used for async decoupling between domains.
-->

| Topic | Publisher Domain | Publisher Class | Consumer Domain | Consumer Listener | Business Action | Notes |
|-------|-----------------|----------------|-----------------|-------------------|-----------------|-------|
| `app.internal.order.created` | orders | OrderBizBuilder | fulfillment | OrderCreatedListener | Initiate fulfillment workflow | -- |
| `app.internal.payment.confirmed` | payments | PaymentService | orders | PaymentConfirmedListener | Update order status to PAID | -- |
| `{{topic}}` | {{domain}} | {{class}} | {{domain}} | {{listener}} | {{action}} | {{notes}} |

## External Inbound Topics (consumed by this system, published externally)

<!--
Messages from external systems that this system consumes.
These represent integration entry points.
-->

| Topic | External System | Consumer Domain | Consumer Listener | Business Action | Notes |
|-------|----------------|-----------------|-------------------|-----------------|-------|
| `ext.erp.product.sync` | ERP | catalog | ProductSyncListener | Sync product master data | -- |
| `ext.payment-gateway.webhook` | Payment Provider | payments | PaymentWebhookListener | Process payment result callback | -- |
| `{{topic}}` | {{system}} | {{domain}} | {{listener}} | {{action}} | {{notes}} |

## External Outbound Topics (published by this system, consumed externally)

<!--
Messages this system publishes for external systems to consume.
These represent integration exit points.
-->

| Topic | Publisher Domain | Publisher Class | External Consumer | Business Action | Notes |
|-------|-----------------|----------------|-------------------|-----------------|-------|
| `app.to-erp.inventory.change` | inventory | StockChangePublisher | ERP | Notify ERP of stock level changes | -- |
| `app.to-notification.order.shipped` | shipping | ShippingService | Notification Service | Trigger shipment notification to customer | -- |
| `{{topic}}` | {{domain}} | {{class}} | {{consumer}} | {{action}} | {{notes}} |

## Index Sync Topics (optional)

<!--
If your system publishes messages specifically for search index updates,
data synchronization, or analytics pipelines, list them here.
-->

| Topic | Publisher Domain | Publisher Class | Target System | Notes |
|-------|-----------------|----------------|---------------|-------|
| `app.to-search.order.index.update` | orders | OrderIndexWriter | Search/OpenSearch | Order search index sync |
| `{{topic}}` | {{domain}} | {{class}} | {{target}} | {{notes}} |

## Statistics

| Category | Count |
|----------|-------|
| Internal topics | {{count}} |
| External inbound topics | {{count}} |
| External outbound topics | {{count}} |
| Index sync topics | {{count}} |
| **Total** | **{{total}}** |

## Listener Overview

<!--
A flat list of all consumer listeners for quick lookup.
-->

| Listener Class | Package/Directory | Domain | Consumed Topic |
|----------------|-------------------|--------|---------------|
| OrderCreatedListener | listeners/fulfillment | fulfillment | `app.internal.order.created` |
| ProductSyncListener | listeners/catalog | catalog | `ext.erp.product.sync` |
| {{listener}} | {{path}} | {{domain}} | {{topic}} |

---

## Maintenance Guidelines

1. **Adding a new topic**: Add an entry in the appropriate section above and update the statistics.
2. **Changing message schema**: Identify all consumers of the topic in this document and coordinate changes.
3. **Deprecating a topic**: Mark it clearly before removing; verify zero consumers remain.
4. **MQ exchange/broker configuration**: Document any exchange or routing details relevant to your MQ platform (RabbitMQ exchanges, Kafka partitions, RocketMQ groups, etc.) in a subsection below if needed.
