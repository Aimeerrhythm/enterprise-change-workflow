---
name: security
description: Pre-commit security checklist — applies to all code changes
scope: common
paths: []
---

# Security Rules

These rules apply to **every** code change, regardless of risk level.

## 1. No Hardcoded Secrets

- Never commit passwords, API keys, tokens, or connection strings in source code
- Use environment variables, secret managers, or configuration services
- Patterns to reject: `password=`, `secret=`, `api_key=`, `token=`, `AKIA`, `-----BEGIN.*PRIVATE KEY-----`
- Exception: test fixtures using obviously fake values (e.g., `test-password-123`)

## 2. Input Validation at System Boundaries

- Validate all user input before processing (HTTP parameters, request bodies, file uploads)
- Validate all external API responses before trusting their data
- Internal service-to-service calls within a trusted boundary do not require re-validation

## 3. SQL Injection Prevention

- Use parameterized queries or ORM methods — never concatenate user input into SQL
- MyBatis: use `#{}` (parameterized), never `${}` (string interpolation) for user-controlled values
- Exception: `${}` is acceptable for column/table names from a hardcoded allowlist

## 4. XSS Prevention

- Escape all user-generated content before rendering in HTML
- Use framework-provided escaping (React JSX auto-escapes, Thymeleaf `th:text`)
- Never use `innerHTML`, `dangerouslySetInnerHTML`, or `v-html` with user data

## 5. Authentication & Authorization

- Every externally-facing endpoint must enforce authentication
- Authorization checks must happen at the service layer, not only at the controller
- Do not rely solely on frontend visibility to protect sensitive operations

## 6. Sensitive Data Logging

- Never log passwords, tokens, credit card numbers, or PII
- Mask sensitive fields in log output: show only last 4 characters
- Audit log entries must not contain raw request/response bodies with sensitive data

## 7. Dependency Awareness

- When adding a new dependency, verify it is actively maintained and has no known critical CVEs
- Pin dependency versions — do not use floating ranges for production dependencies
- Prefer well-known libraries over ad-hoc implementations for crypto, auth, and serialization

## 8. File Operation Safety

- Validate file paths to prevent path traversal (`../`)
- Restrict upload file types and sizes
- Do not execute or eval user-uploaded content
