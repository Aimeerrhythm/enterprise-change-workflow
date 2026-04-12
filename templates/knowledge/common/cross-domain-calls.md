# Cross-Domain Call Matrix

> Data source: Code scan of dependency injection annotations (e.g., `@Resource`, `@Inject`, `@Autowired`, `@DubboReference`)
> Last scanned: {{SCAN_DATE}}
> Scan scope: {{SOURCE_ROOT_PATH}}
> Total cross-domain calls: {{TOTAL_COUNT}}

<!--
PURPOSE: This document tracks all direct method calls between domains within
your system. It is the primary input for impact analysis -- when a class or
method changes, this matrix tells you which other domains are affected.

HOW TO POPULATE:
1. Identify all domain boundaries in your codebase (packages, modules, bounded contexts).
2. Scan for dependency injection across those boundaries.
3. Record every case where a class in Domain A injects and calls a class in Domain B.

You can generate this automatically with a script that scans your DI annotations,
or maintain it manually during code reviews.
-->

## Summary Statistics

<!--
Aggregate the detail rows below into a caller-callee pair count.
One row per unique (caller domain, callee domain) pair.
-->

| Caller Domain | Callee Domain | Call Count |
|---------------|---------------|-----------|
| orders | inventory | 12 |
| orders | payments | 5 |
| shipping | orders | 8 |
| {{caller_domain}} | {{callee_domain}} | {{count}} |

## Call Details

<!--
One row per injection point. Fill in every cross-domain dependency you find.

Column definitions:
- Caller Domain: The domain that owns the calling class.
- Callee Domain: The domain that owns the injected interface/class.
- Caller Class: The concrete class that holds the injected reference.
- Callee Interface: The interface or class being injected.
- Call Type: How the dependency is wired (e.g., "Direct injection", "Strategy callback",
  "RPC reference", "Event listener").
- Business Scenario: A short description of why this call exists.
- Data Source: How this entry was discovered (e.g., "code-scan", "manual-review").
-->

| Caller Domain | Callee Domain | Caller Class | Callee Interface | Call Type | Business Scenario | Data Source |
|---------------|---------------|--------------|------------------|-----------|-------------------|------------|
| orders | inventory | OrderServiceImpl | StockService | Direct injection | Deduct stock on order confirmation | code-scan |
| orders | payments | OrderServiceImpl | PaymentGateway | Direct injection | Process payment on checkout | code-scan |
| shipping | orders | ShippingServiceImpl | OrderQueryService | Direct injection | Look up order details for label generation | code-scan |
| {{caller}} | {{callee}} | {{caller_class}} | {{callee_interface}} | {{call_type}} | {{scenario}} | {{source}} |

---

## Maintenance Guidelines

1. **Before modifying a shared interface**: Search this document for all callers to assess impact scope.
2. **Method signature changes**: Must be synchronized across all caller domains listed here.
3. **New methods**: Lower risk, but verify they do not violate interface contracts.
4. **Behavioral changes (same signature, different logic)**: Highest risk -- requires regression testing across all callers.
5. **Keep this document current**: Update it whenever a new cross-domain dependency is introduced or removed.
