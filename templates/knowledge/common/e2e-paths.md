# End-to-End Critical Paths

> Data source: Cross-domain dependency graph + business knowledge + code tracing
> Last updated: {{DATE}}

<!--
PURPOSE: This document describes the most important end-to-end business flows
through the system. Each path traces a complete business operation from trigger
to completion, across all domains and external systems involved.

This is the primary document for impact analysis: when a class or method changes,
search here to find which end-to-end paths are affected.

HOW TO POPULATE:
1. Identify the key business operations (e.g., "customer places order", "return processed").
2. Trace each operation step by step through domains, noting the class/method at each step.
3. Document the external systems involved at entry and exit points.
4. List exception/error branches -- these are often where bugs hide.
5. Mark shared resources that appear in multiple paths.
-->

## Path Index

<!--
Summary table of all end-to-end paths. Keep this updated as paths are added.
-->

| # | Path Name | Domains Involved | Steps |
|---|-----------|-----------------|-------|
| 1 | Order Fulfillment | Orders -> Inventory -> Fulfillment -> Shipping -> External(Carrier) | 8 |
| 2 | Return Processing | External(Customer) -> Returns -> Inventory -> Payments -> External(Customer) | 7 |
| 3 | {{path_name}} | {{domain_chain}} | {{step_count}} |

---

## Path Details

<!--
Repeat this section for each end-to-end path.

For each step, specify:
- Which domain or external system owns the step (in brackets)
- The concrete class and method involved
- What happens at this step

Also document:
- Exception branches (what happens when things go wrong)
- Impact markers (which steps, if changed, cascade to other steps)
-->

---

### 1. {{Path Name}}

**Keywords**: {{comma-separated keywords for searchability}}
**Domains involved**: {{External(System)}} -> {{DomainA}} -> {{DomainB}} -> ... -> {{External(System)}}

1. [External/{{System}}] Trigger event arrives -- `{{topic or endpoint}}`
2. [{{DomainA}}] Consume event and create entity -- `{{ListenerClass}}` -> `{{ServiceClass.method()}}`
3. [{{DomainA}} -> {{DomainB}}] Cross-domain call -- `{{SharedService.method()}}` (shared resource, {{N}} domain consumers)
4. [{{DomainB}}] Process and persist -- `{{ServiceClass.method()}}`
5. [{{DomainB}} -> {{DomainC}}] Async handoff via MQ -- `{{topic_name}}`
6. [{{DomainC}}] Final processing -- `{{ServiceClass.method()}}`
7. [{{DomainC}} -> External/{{System}}] Notify external system -- MQ `{{topic_name}}`

**Exception branches**:
- {{Describe what happens when step N fails}} -> `{{ExceptionHandler.method()}}` -> {{downstream impact}}
- {{Another failure scenario}} -> {{recovery mechanism}} -- Impact: {{affected domains/steps}}

**Impact markers**: Changing step {{N}} affects steps {{N+1}} through end of path; changing `{{SharedResource}}` at step {{M}} affects all paths that use it.

---

### 2. {{Another Path Name}}

**Keywords**: {{keywords}}
**Domains involved**: {{chain}}

1. [{{domain}}] {{description}} -- `{{class.method()}}`
2. ...

**Exception branches**:
- ...

**Impact markers**: ...

---

## Shared Resource Impact Quick Reference

<!--
List shared resources that appear across multiple paths.
When modifying these, ALL listed paths need regression testing.
-->

| Shared Resource | Appears in Paths | Risk Level |
|----------------|-----------------|------------|
| StockService | 1, 2, 3, 5 (all stock-related) | **Critical** |
| OrderRepository | 1, 2, 4 | **High** |
| TransactionHelper | 1, 2, 3, 4, 5 (all) | **Critical** |
| {{resource}} | {{path_numbers}} | **{{level}}** |

## Path Dependencies

<!--
Some paths share steps or branch into each other. Document those relationships here.
Use a simple text diagram or a list.
-->

```
{{Path 1}} --error branch--> {{Path 4 (error handling)}}
{{Path 2}} --triggers--> {{Path 3 (downstream)}}
{{Path 5}} --reuses step from--> {{Path 1 step 6}}
```

---

## Usage Guidelines

1. **Locating impact scope**: Before modifying a class or method, search this document for the class name to find all affected paths.
2. **Evaluating exception branches**: Pay special attention to exception branches when modifying error handling logic.
3. **Shared resource changes**: Consult the quick reference table above; changes to listed resources require notifying owners of all affected paths.
4. **MQ topic schema changes**: Search for the topic name across all path steps to identify affected flows.
5. **Adding a new path**: Follow the template format above, including exception branches and impact markers.
