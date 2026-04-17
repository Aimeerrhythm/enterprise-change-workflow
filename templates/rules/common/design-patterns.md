---
name: design-patterns
description: Design pattern guidelines — layering, DTO boundaries, error propagation
scope: common
paths: []
---

# Design Pattern Rules

## 1. Layer Separation

- **Controller/Handler** layer: request parsing, parameter validation, response formatting — no business logic
- **Service** layer: business rules, orchestration, transaction boundaries — no framework-specific annotations in signatures
- **Repository/DAO** layer: data access only — no business decisions
- Do not skip layers (controller calling repository directly) except for trivial CRUD

## 2. DTO Boundaries

- External API request/response types must be separate from internal domain models
- Convert between DTOs and domain models at the service boundary
- Never expose database entities directly in API responses
- Inner-layer changes (DB schema, domain model) must not force outer-layer changes (API contract)

## 3. Error Propagation

- Business errors (validation failure, insufficient stock) → return typed error codes, not generic exceptions
- Infrastructure errors (DB down, timeout) → propagate as exceptions with context
- Do not swallow exceptions silently — at minimum log at WARN level
- Do not use exceptions for control flow (e.g., throwing to exit a loop)

## 4. Dependency Direction

- Higher layers depend on lower layers, never the reverse
- Shared utilities (`util/`, `common/`) must not depend on business logic
- Cross-domain calls should go through defined Facade/API interfaces, not internal service classes

## 5. Configuration Externalization

- All environment-specific values (URLs, credentials, feature flags) must be externalized
- Use configuration files, environment variables, or config services — not hardcoded values
- Default values must be safe (e.g., `feature_enabled: false`, not `true`)

## 6. Idempotency

- Write operations that may be retried (MQ consumers, webhook handlers, API endpoints) must be idempotent
- Use unique business keys or idempotency tokens to detect duplicate requests
- Document which operations are idempotent and which are not
