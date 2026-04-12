# External System Integrations

> Data source: Code scan + architecture documentation
> Last scanned: {{SCAN_DATE}}
> Scan scope: MQ constants, RPC references, HTTP clients, SDK clients

<!--
PURPOSE: This document catalogs every external system your application integrates
with, organized by system. For each system, it lists all integration points --
MQ topics, RPC/gRPC calls, HTTP endpoints, and SDK usages -- with direction,
owning domain, and business context.

HOW TO POPULATE:
1. Scan for all external RPC references (e.g., @DubboReference, gRPC stubs, Feign clients).
2. Scan for all MQ topics that cross system boundaries.
3. Scan for all HTTP client calls to external URLs.
4. Group results by external system.
-->

## Summary

| Dimension | Count |
|-----------|-------|
| External systems | {{count}} |
| MQ topics (inbound) | {{count}} |
| MQ topics (outbound) | {{count}} |
| MQ topics (internal) | {{count}} |
| RPC references (outbound) | {{count}} |
| RPC services (exposed) | {{count}} |
| HTTP integrations | {{count}} |

---

## Integration Details by System

<!--
Repeat this section for each external system. Include:
- System name and description
- Integration layer (wrapper classes, SDK clients, etc.)
- A table of all integration points

Direction values: Inbound (external -> this system), Outbound (this system -> external), Bidirectional
Type values: MQ, RPC/Dubbo, gRPC, HTTP, SDK, WebSocket, etc.
-->

### {{System Name}} ({{Brief Description}})

Integration layer: `{{path-to-wrapper-or-client-code}}`
RPC references: `{{list of remote interfaces}}`

| Direction | Type | Topic / Interface / Endpoint | Domain | Business Scenario | Impact Description |
|-----------|------|------------------------------|--------|-------------------|-------------------|
| Inbound | MQ | `ext.system.order.create` | orders | Receive new orders from external system | Order creation entry point; schema changes require coordination |
| Outbound | MQ | `app.to-system.order.status` | orders | Notify external system of order status changes | Status sync; message format changes require downstream coordination |
| Outbound | RPC | `ExternalFacade.queryProduct()` | catalog | Query product details from external system | Read-only; interface version changes may break calls |
| Outbound | HTTP | `POST /api/v1/webhook` | notifications | Push event notifications | Requires authentication; endpoint changes need config update |
| {{direction}} | {{type}} | {{topic_or_interface}} | {{domain}} | {{scenario}} | {{impact}} |

---

### {{Another System Name}} ({{Brief Description}})

Integration layer: `{{path}}`

| Direction | Type | Topic / Interface / Endpoint | Domain | Business Scenario | Impact Description |
|-----------|------|------------------------------|--------|-------------------|-------------------|
| {{direction}} | {{type}} | {{topic_or_interface}} | {{domain}} | {{scenario}} | {{impact}} |

---

## Services Exposed to External Systems

<!--
If your application exposes APIs (RPC, REST, gRPC) that external systems call,
list them here. This helps understand the "inbound surface area" of your system.
-->

| Exposed Interface | Domain | Description |
|-------------------|--------|-------------|
| OrderFacade | orders | Order CRUD operations |
| StockQueryFacade | inventory | Stock level queries |
| {{facade_class}} | {{domain}} | {{description}} |

## Internal Async Topics (self-produced, self-consumed)

<!--
These topics do not involve external systems. They exist for internal async
decoupling. Changes only need to consider internal consumers.
-->

| Topic | Constant Name | Domain | Business Scenario |
|-------|--------------|--------|-------------------|
| `app.internal.order.index.update` | ORDER_INDEX_ROUTING_KEY | orders | Order search index rebuild |
| `{{topic}}` | {{constant}} | {{domain}} | {{scenario}} |

---

## Key Code Locations

<!--
Quick reference for where integration code lives in the codebase.
-->

| Category | Path |
|----------|------|
| MQ constants | `{{path-to-mq-constants}}` |
| RPC configuration | `{{path-to-rpc-config}}` |
| External call wrappers | `{{path-to-wrapper-layer}}/` |
| MQ listeners | `{{path-to-listeners}}/` |
| Exposed RPC services | `{{path-to-facade-impls}}/` |

---

## Maintenance Guidelines

1. **Adding a new external system**: Create a new section following the template above.
2. **Changing message schemas**: Coordinate with the external system team; identify all topics in this document that reference that system.
3. **Upgrading RPC interface versions**: Check all references listed here and update wrapper code accordingly.
4. **Monitoring**: Set up alerts for external call failures; this document helps identify which business flows are affected.
