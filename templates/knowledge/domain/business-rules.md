# {{Domain Name}} Business Rules

> extracted-from-commit: {{COMMIT_HASH}}
> last-verified: {{DATE}}

<!--
PURPOSE: This document captures all business rules for a single domain, organized
by category. The AI assistant reads this when it needs to understand constraints,
validation logic, concurrency controls, or behavioral rules before making changes.

HOW TO POPULATE:
1. Extract rules from code (lock patterns, validation checks, status transitions).
2. Extract rules from product specs and domain expert interviews.
3. Organize by the categories below -- add or remove sections as needed.
4. For each rule, cite the concrete class/method where it is enforced.
-->

---

## 1. Concurrency Control

### Distributed Locks

<!--
List every distributed lock used in this domain.
Include the lock key pattern, which node/operation uses it, the granularity,
timeout settings, and the race condition it prevents.
-->

| Lock Key Pattern | Node / Operation | Granularity | Wait / Timeout | Purpose |
|-----------------|-----------------|-------------|---------------|---------|
| `{{DOMAIN}}_LOCK:{{entity_id}}` | {{Operation name}} | {{entity-level}} | {{wait}}s / {{timeout}}s | Prevent concurrent {{operation}} on the same {{entity}} |
| `{{ANOTHER_KEY}}:{{field}}` | {{Operation name}} | {{field-level}} | {{wait}}s / {{timeout}}s | {{Purpose}} |

### Optimistic Locking (version fields)

<!--
List every table/entity that uses optimistic locking (version column).
-->

| Table / Entity | Scenarios | Description |
|---------------|-----------|-------------|
| {{EntityDO}} | {{When version is checked}} | `WHERE version = #{version}` + `SET version = version + 1` |

### Task / Resource Exclusion

<!--
Document any mutual-exclusion patterns beyond locks (e.g., task ownership,
workstation binding, operator assignment).
-->

- {{Description of exclusion rule, e.g., "A task can only be claimed by one operator at a time via obtainTask()"}}

---

## 2. Idempotency Rules

### Entity Creation Idempotency

<!--
For each entity creation operation, describe how duplicates are prevented.
-->

| Operation | Idempotency Mechanism | Description |
|-----------|----------------------|-------------|
| {{Entity}} creation (MQ) | `findBySourceId(sourceType, sourceId)` | If entity with same source already exists, skip creation |
| {{Entity}} creation (API) | Transaction-scoped double-check | Second query inside transaction prevents race condition |

### Message Consumption Idempotency

<!--
For each MQ consumer, describe how redelivered messages are handled.
-->

| Operation / Listener | Idempotency Mechanism | Description |
|---------------------|----------------------|-------------|
| {{ListenerClass}} | Status check before processing | If entity already in target status, return early |
| {{ListenerClass}} | Deduplication by message ID | Store processed message IDs; skip duplicates |

### Other Idempotency Patterns

| Scenario | Mechanism | Description |
|----------|-----------|-------------|
| {{Scenario}} | {{Mechanism}} | {{Details}} |

---

## 3. MQ Communication (this domain's topics)

### Inbound (messages consumed by this domain)

| Topic | Source System/Domain | Node | Description |
|-------|---------------------|------|-------------|
| {{topic_name}} | {{source}} | {{processing_node}} | {{What this message triggers}} |

### Outbound (messages published by this domain)

| Topic | Target System/Domain | Node | Description |
|-------|---------------------|------|-------------|
| {{topic_name}} | {{target}} | {{publishing_node}} | {{What event triggers this message}} |

---

## 4. Validation Rules

<!--
Document business validation rules enforced in this domain.
Group by the entity or operation they apply to.
-->

### {{Entity Name}} Validation

| Rule | Enforced In | Description |
|------|------------|-------------|
| {{Rule name}} | `{{Class.method()}}` | {{What is validated and what happens on failure}} |

### {{Operation Name}} Validation

| Rule | Enforced In | Description |
|------|------------|-------------|
| {{Rule name}} | `{{Class.method()}}` | {{Details}} |

---

## 5. State Machines

<!--
For each entity with status transitions, document the allowed transitions.
Include the trigger (what causes the transition) and the side effects.
-->

### {{Entity Name}} Status Transitions

| From Status | To Status | Trigger | Side Effects |
|------------|-----------|---------|--------------|
| `CREATED` | `IN_PROGRESS` | {{trigger_event}} | {{side_effects}} |
| `IN_PROGRESS` | `COMPLETED` | {{trigger_event}} | {{side_effects}} |
| `IN_PROGRESS` | `FAILED` | {{trigger_event}} | {{side_effects}} |
| `COMPLETED` | -- (terminal) | -- | -- |

---

## 6. Configuration (dynamic / feature flags)

<!--
List any configuration keys that control business behavior in this domain.
Include the config source (e.g., Nacos, application.yml, database).
-->

| Config Key | Source | Default | Description |
|-----------|--------|---------|-------------|
| `{{config.key.name}}` | {{Nacos / application.yml / DB}} | {{default_value}} | {{What it controls}} |

---

## 7. Cross-Domain Interaction Rules

<!--
Document rules about how this domain interacts with other domains.
Focus on contracts, expectations, and constraints.
-->

| Interaction | Rule | Description |
|------------|------|-------------|
| {{This domain}} -> {{Other domain}} | {{Rule}} | {{Details, e.g., "Must call within same transaction" or "Fire-and-forget via MQ"}} |

---

## 8. Edge Cases and Special Scenarios

<!--
Document known edge cases, special business scenarios, or non-obvious behaviors
that developers should be aware of.
-->

| Scenario | Behavior | Relevant Code |
|----------|----------|--------------|
| {{Edge case description}} | {{What happens}} | `{{Class.method()}}` |
