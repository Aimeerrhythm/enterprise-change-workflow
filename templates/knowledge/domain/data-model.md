# {{Domain Name}} Data Model

> extracted-from-commit: {{COMMIT_HASH}}
> last-verified: {{DATE}}

<!--
PURPOSE: This document describes the data model for a single domain -- all
database tables (DO classes), their columns, relationships, and status enums.
The AI assistant reads this to understand the persistence layer before making
changes that involve queries, schema, or status transitions.

HOW TO POPULATE:
1. For each DO class / database table in the domain, list all columns with
   their Java field names, JDBC types, and descriptions.
2. Document all enum types used by these tables.
3. Draw the entity relationships (which tables reference which).
4. Include status enum definitions with their integer codes and meanings.
-->

---

## Entity Overview

<!--
Quick reference of all entities (tables) in this domain.
-->

| Entity (DO Class) | Table Name | Description | Key Business Identifier |
|-------------------|-----------|-------------|------------------------|
| {{EntityDO}} | `{{table_name}}` | {{Brief description}} | {{e.g., orderSn, entityId}} |
| {{AnotherEntityDO}} | `{{table_name}}` | {{Brief description}} | {{business_key}} |

---

## Entity Details

### {{EntityDO}} -- {{Human-readable name}}

**Table name**: `{{schema.table_name}}`

<!--
List all columns. Include:
- Database column name (snake_case)
- Java field name (camelCase)
- JDBC type
- Description (include enum references where applicable)
-->

| Column | Java Field | JDBC Type | Description |
|--------|-----------|-----------|-------------|
| id | id | BIGINT | Primary key |
| {{column_name}} | {{javaField}} | VARCHAR | {{Human-readable description}} |
| type | type | INTEGER | Entity type. See `{{TypeEnum}}`: {{value1}}-{{meaning1}}, {{value2}}-{{meaning2}} |
| status | status | INTEGER | Entity status. See `{{StatusEnum}}` below |
| version | version | INTEGER | Optimistic lock version |
| gmt_created | gmtCreated | TIMESTAMP | Creation timestamp |
| gmt_modified | gmtModified | TIMESTAMP | Last modification timestamp |
| feature | feature | TEXT | Extension JSON (flexible attributes) |

---

### {{AnotherEntityDO}} -- {{Human-readable name}}

**Table name**: `{{schema.table_name}}`

| Column | Java Field | JDBC Type | Description |
|--------|-----------|-----------|-------------|
| id | id | BIGINT | Primary key |
| {{parent_entity}}_id | {{parentEntity}}Id | BIGINT | Foreign key to {{parent table}} |
| {{column}} | {{field}} | {{type}} | {{description}} |

---

## Status Enums

<!--
For each status enum, list all possible values with their codes and meanings.
Include transition rules if not documented in business-rules.md.
-->

### {{StatusEnum}}

| Code | Name | Description |
|------|------|-------------|
| 1 | `CREATED` | Entity has been created but not yet processed |
| 2 | `IN_PROGRESS` | Entity is currently being processed |
| 3 | `COMPLETED` | Entity processing is finished |
| 4 | `CANCELLED` | Entity was cancelled before completion |
| {{code}} | `{{NAME}}` | {{description}} |

### {{TypeEnum}}

| Code | Name | Description |
|------|------|-------------|
| 1 | `{{TYPE_A}}` | {{Description of type A}} |
| 2 | `{{TYPE_B}}` | {{Description of type B}} |

---

## Other Enums

<!--
List any additional enums used in this domain's tables (e.g., priority levels,
category types, flag enums).
-->

### {{OtherEnum}}

| Code | Name | Description |
|------|------|-------------|
| {{code}} | `{{NAME}}` | {{description}} |

---

## Entity Relationships

<!--
Describe how entities relate to each other. Use a text-based ER diagram
or a relationship table. Include cardinality (1:1, 1:N, M:N).
-->

```
{{ParentEntity}} 1 ---< N {{ChildEntity}}     (one parent has many children)
{{EntityA}} 1 ---< N {{EntityB}} ---< N {{EntityC}}
{{EntityX}} >--- 1 {{SharedEntity}}            (many X reference one shared entity)
```

### Relationship Details

| Parent Entity | Child Entity | Relationship | Join Key | Description |
|--------------|-------------|-------------|----------|-------------|
| {{ParentDO}} | {{ChildDO}} | 1:N | {{parent_sn}} | {{Description, e.g., "One order has many line items"}} |
| {{EntityA}} | {{EntityB}} | M:N | {{join_table}} | {{Description}} |

---

## Indexes (key business indexes)

<!--
Optional: list important database indexes that affect query patterns or
performance considerations developers should know about.
-->

| Table | Index Name | Columns | Type | Purpose |
|-------|-----------|---------|------|---------|
| {{table}} | {{idx_name}} | {{col1, col2}} | UNIQUE / BTREE | {{Why this index exists}} |

---

## Maintenance Guidelines

1. **Adding a new column**: Update both this document and the corresponding MyBatis XML mapper.
2. **Adding a new enum value**: Update the enum class, this document, and any switch/if-else logic that uses the enum.
3. **Changing relationships**: Evaluate impact on all queries that join these tables; update this ER section.
4. **Status enum changes**: Coordinate with the business-rules.md state machine section.
