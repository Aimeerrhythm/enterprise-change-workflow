---
name: performance
description: Performance guardrails — query patterns, resource management, caching
scope: common
paths: []
---

# Performance Rules

## 1. N+1 Query Prevention

- Never execute a query inside a loop that iterates over a collection
- Use batch queries (`WHERE id IN (...)`) or join fetches instead
- ORM lazy loading is acceptable only when the collection is small and bounded

## 2. Pagination

- All list queries that may return unbounded results must support pagination
- Default page size should be reasonable (20-100), never unbounded
- API endpoints returning lists must accept `page`/`size` or `offset`/`limit` parameters

## 3. Resource Cleanup

- Close database connections, file handles, HTTP clients, and streams after use
- Use try-with-resources (Java), defer (Go), context managers (Python), or finally blocks
- Connection pools must have both max-size and idle-timeout configured

## 4. Batch Operations

- Batch inserts/updates instead of single-row operations when handling collections
- Use database-native batch APIs (JDBC batch, MongoDB bulkWrite, etc.)
- Set batch size limits (typically 500-1000 rows) to avoid oversized transactions

## 5. Caching Discipline

- Cache only data that is read-heavy and write-light
- Every cache entry must have an explicit TTL — no infinite caching
- Invalidation strategy must be defined before implementing cache (write-through, write-behind, or event-driven)
- Document which cache keys are used and what invalidates them

## 6. Timeout Configuration

- All external calls (HTTP, RPC, database) must have explicit timeouts
- Default timeout should be set at the client level, with per-operation overrides for known slow paths
- Timeouts must cascade: caller timeout < callee timeout to prevent orphaned operations

## 7. Log Volume

- Do not log at INFO or DEBUG level inside hot loops
- Error logs must include context (request ID, key parameters) but not full request/response bodies
- Use structured logging (JSON) in production for machine-parseable output
