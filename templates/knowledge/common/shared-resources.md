# Shared Resources

> Data source: Code scan of dependency injection across domain boundaries
> Last scanned: {{SCAN_DATE}}

<!--
PURPOSE: This document lists every service, component, or manager class that is
injected by 2 or more domains. These are the highest-risk change targets in the
codebase -- modifying them can silently break multiple domains.

HOW TO POPULATE:
1. From your cross-domain call matrix, group callee interfaces by the number of
   distinct caller domains.
2. Include any class that has 2+ domain consumers.
3. List key methods, the consuming domains, and an impact description.
-->

## Core Services (shared across domains)

<!--
These are domain-level service interfaces used across multiple bounded contexts.
They are the most critical shared resources.

Column definitions:
- Shared Resource: The class or interface name.
- Type: The architectural layer (e.g., CoreService, Manager, Repository, Utility).
- Consumer Domains (count): List of domains that inject this resource, with total count.
- Key Methods: The most-used methods from this interface.
- Impact Description: What breaks or degrades if this resource changes.
-->

| Shared Resource | Type | Consumer Domains (count) | Key Methods | Impact Description |
|----------------|------|--------------------------|-------------|-------------------|
| StockService | CoreService | orders, fulfillment, returns, inventory (4) | `reserve()`, `deduct()`, `release()`, `query()` | Stock operations affect all order/fulfillment flows; method signature changes require synchronized updates across all consumers |
| UserQueryService | CoreService | orders, fulfillment, admin, reporting (4) | `getById()`, `queryByIds()`, `search()` | User lookup is a foundational dependency; interface changes affect all domains |
| NotificationService | CoreService | orders, shipping, payments (3) | `send()`, `sendBatch()` | Notification delivery; behavioral changes affect all customer-facing flows |
| {{resource_name}} | {{type}} | {{domain_list}} ({{count}}) | {{methods}} | {{impact}} |

## Managers / Data Access (shared across domains)

<!--
Lower-level data access classes shared across domains.
-->

| Shared Resource | Type | Consumer Domains (count) | Key Methods | Impact Description |
|----------------|------|--------------------------|-------------|-------------------|
| TransactionHelper | Utility | orders, inventory, fulfillment, payments (4) | `withTransaction()`, `afterTransaction()` | Transaction behavior changes affect data consistency across all domains |
| OrderRepository | Manager | orders, shipping, returns (3) | `findByOrderId()`, `updateStatus()` | Order data queries; schema or query changes affect multiple domains |
| {{resource_name}} | {{type}} | {{domain_list}} ({{count}}) | {{methods}} | {{impact}} |

## Risk Classification

<!--
Group shared resources by the number of consuming domains.
The more domains depend on a resource, the higher the risk.
-->

### Critical Risk (6+ domain consumers)
- **{{ResourceName}}** -- {{count}} domains, {{brief_description}}

### High Risk (4-5 domain consumers)
- **{{ResourceName}}** -- {{count}} domains, {{brief_description}}

### Medium Risk (2-3 domain consumers)
- **{{ResourceName}}** -- {{count}} domains, {{brief_description}}

---

## Usage Guidelines

1. **Before modifying a shared resource**: Grep all injection points to confirm the full impact scope. Do not rely solely on this document.
2. **Method signature changes**: Must be synchronized across all consuming domains simultaneously.
3. **Adding new methods**: Lower risk, but ensure they do not break interface contracts or introduce unexpected side effects.
4. **Behavioral changes (same signature, different logic)**: Highest risk -- requires full regression testing across all consuming domains.
