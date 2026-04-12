# {{Domain Name}} Domain Navigation

> last-updated: {{DATE}}

<!--
PURPOSE: This is the entry point for a single business domain. It provides a
complete map of the domain's knowledge documents, process flows, components,
and external interactions. When the AI assistant receives a task related to
this domain, it reads this file first to navigate to the right detail document.

HOW TO POPULATE:
1. List all subdirectories and documents in this domain's knowledge folder.
2. Identify the major process flows (chains/pipelines) this domain supports.
3. Map each component/node to its Facade or Service class and its detail document.
4. List all external system interactions.

NAMING CONVENTION for subdirectories:
- common/     -- shared rules, data models, and cross-cutting nodes
- {{flow1}}/  -- documents specific to the first major flow
- {{flow2}}/  -- documents specific to the second major flow
-->

---

## Directory Structure

```
{{domain-name}}/
+-- 00-index.md              <-- you are here
+-- common/                  # Cross-flow shared resources
|   +-- data-model.md        # DO classes, enums, status machines, ER diagram
|   +-- business-rules.md    # Concurrency, idempotency, transactions, cross-domain rules
|   +-- nodes/
|       +-- {{shared-node}}.md  # Shared processing node (used by multiple flows)
+-- {{flow-1}}/              # First major business flow
|   +-- 00-index.md          # Flow overview + end-to-end diagram
|   +-- {{node-a}}.md        # Processing node A detail
|   +-- {{node-b}}.md        # Processing node B detail
+-- {{flow-2}}/              # Second major business flow
    +-- 00-index.md          # Flow overview
    +-- {{node-c}}.md        # Processing node C detail
```

## Major Flows

<!--
List each distinct business flow this domain supports.
Include the type identifier (enum value), how it is triggered, complexity (node count),
and what makes it different from other flows.
-->

| Flow | Type Identifier | Trigger | Node Count | Key Characteristics |
|------|----------------|---------|------------|---------------------|
| [{{Flow 1 Name}}]({{flow-1}}/00-index.md) | `{{ENUM_VALUE}}` | {{MQ / API / Scheduled}} | {{N}} | {{Brief description of what makes this flow unique}} |
| [{{Flow 2 Name}}]({{flow-2}}/00-index.md) | `{{ENUM_VALUE}}` | {{MQ / API / Scheduled}} | {{N}} | {{Brief description}} |

## Shared Nodes

<!--
Processing nodes that are reused across multiple flows in this domain.
-->

- **[{{Node Name}}](common/nodes/{{node}}.md)** -- {{Brief description of the node, e.g., "Factory+Strategy pattern, N variants, unified entry point"}}

## Shared Rules

- **[Data Model](common/data-model.md)** -- {{List key entities}}, enums, status machines, ER diagram
- **[Business Rules](common/business-rules.md)** -- Concurrency control, idempotency, MQ communication, transactions, cross-domain interaction rules

## External System Interactions

<!--
List all external systems this domain communicates with,
the direction of communication, and the integration method.
-->

| System | Direction | Integration Type | Description |
|--------|-----------|-----------------|-------------|
| {{System A}} | {{System A}} -> This Domain | MQ | {{What data/events come in}} |
| {{System A}} | This Domain -> {{System A}} | RPC | {{What calls go out}} |
| {{System B}} | This Domain -> {{System B}} | MQ | {{What notifications go out}} |

## Component Map

<!--
Map every Facade, Service, or Controller in this domain to its corresponding
knowledge document. Group by functional area.

This table is the primary lookup for "I need to understand {{ClassName}} -- where
do I read about it?"
-->

### {{Functional Area 1}} (e.g., "Main Processing Pipeline")

| Node / Component | Facade / Service Class | Detail Document |
|-----------------|----------------------|-----------------|
| {{Node Name}} | `{{FacadeClass}}` | [{{doc-name}}.md]({{path}}) |
| {{Node Name}} | `{{FacadeClass}}` / `{{ServiceClass}}` | [{{doc-name}}.md]({{path}}) |

### {{Functional Area 2}} (e.g., "Error Handling")

| Node / Component | Facade / Service Class | Detail Document |
|-----------------|----------------------|-----------------|
| {{Node Name}} | `{{FacadeClass}}` | [{{doc-name}}.md]({{path}}) |

### {{Functional Area 3}} (e.g., "Support Services")

| Node / Component | Facade / Service Class | Detail Document |
|-----------------|----------------------|-----------------|
| {{Node Name}} | `{{FacadeClass}}` | [{{doc-name}}.md]({{path}}) |
