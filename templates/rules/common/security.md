# Security Rules

## Input Validation

- `[must-follow]` All external inputs (HTTP params, MQ messages, file uploads) must be validated before processing
- `[must-follow]` Validate both type and range — not just null checks
- `[recommended]` Use allowlist validation over denylist where possible

## Injection Prevention

- `[must-follow]` Use parameterized queries for all database operations — never concatenate user input into SQL
- `[must-follow]` Escape user-provided content before rendering in HTML/templates (XSS prevention)
- `[must-follow]` Validate and sanitize file paths to prevent path traversal

## Sensitive Data

- `[must-follow]` Never hardcode secrets, API keys, passwords, or tokens in source code
- `[must-follow]` Never log sensitive data (passwords, tokens, PII, credit card numbers)
- `[recommended]` Use environment variables or secret management for credentials

## Authentication & Authorization

- `[must-follow]` Every API endpoint must have explicit authorization checks
- `[must-follow]` Use constant-time comparison for token/password verification
- `[recommended]` Apply principle of least privilege for service accounts

## Resource Management

- `[must-follow]` Close all resources (connections, streams, file handles) in finally blocks or use try-with-resources
- `[must-follow]` Set timeouts on all external calls (HTTP, database, RPC)
- `[recommended]` Implement circuit breakers for external service dependencies
