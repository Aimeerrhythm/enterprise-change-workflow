---
name: go-coding-style
description: Go-specific coding style rules — extends common/coding-style
scope: go
paths: ["*.go"]
extends: common/coding-style
---

# Go Coding Style Rules

> Extends `common/coding-style.md`. All common rules apply unless overridden below.

## 1. Formatting

- All code must pass `gofmt` — no exceptions, no custom formatting
- Use `goimports` to manage import grouping (stdlib, external, internal)
- Import groups separated by blank lines: stdlib | third-party | internal

## 2. Error Handling

- **Always check errors**: Ignoring an `error` return value requires a `//nolint` comment with justification
- **Wrap errors**: Use `fmt.Errorf("context: %w", err)` to add context while preserving the error chain
- **Error types**: Define sentinel errors (`var ErrNotFound = errors.New(...)`) for errors that callers need to match on
- **No panic in libraries**: `panic` is only acceptable in `main()` or test setup — libraries must return errors
- Do not use `log.Fatal` in library code — it calls `os.Exit` and prevents cleanup

## 3. Interface Design

- **Accept interfaces, return structs**: Function parameters should use the narrowest interface; return types should be concrete
- **Small interfaces**: Prefer 1-2 method interfaces — `io.Reader`, `io.Writer` are the gold standard
- **Define interfaces at the consumer**: The package that uses the interface should define it, not the package that implements it
- Do not create interfaces preemptively — wait until you need polymorphism or testing seams

## 4. Goroutine Safety

- **Ownership**: Document which goroutine owns which data — concurrent access requires synchronization
- **Channel direction**: Annotate channel parameters as `<-chan T` (receive-only) or `chan<- T` (send-only)
- **Context propagation**: Pass `context.Context` as the first parameter to all functions that do I/O or may block
- **Goroutine lifecycle**: Every `go func()` must have a clear shutdown path — use `context.WithCancel` or `sync.WaitGroup`
- Never start a goroutine without a way to stop it

## 5. Struct Design

- Use value receivers for small immutable types; pointer receivers for large structs or when methods mutate state
- Embed interfaces only when the outer type needs to satisfy the interface
- Use functional options pattern (`WithTimeout(d)`) for constructors with many optional parameters

## 6. Naming — Go Specific

- **Packages**: Short, lowercase, single-word (`order`, `payment`) — not `orderservice` or `order_mgmt`
- **Exported names**: Include the package name context (`http.Client`, not `http.HTTPClient`)
- **Getters**: No `Get` prefix — `order.ID()`, not `order.GetID()`
- **Acronyms**: All-caps for well-known acronyms (`ID`, `HTTP`, `URL`) — not `Id`, `Http`
- **Error variables**: `Err` prefix (`ErrNotFound`, `ErrTimeout`)

## 7. Testing — Go Specific

- Use table-driven tests for functions with multiple input/output cases
- Use `t.Helper()` in test helper functions for correct line reporting
- Use `testify/assert` or stdlib `t.Errorf` consistently — do not mix assertion libraries
- Place test files in the same package for white-box tests, `_test` package for black-box tests
