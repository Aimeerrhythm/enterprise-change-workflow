# Coding Style Rules

## Naming

- `[must-follow]` Classes/types use PascalCase; methods/functions use camelCase (Java/Go/TS) or snake_case (Python)
- `[must-follow]` Constants use UPPER_SNAKE_CASE
- `[recommended]` Boolean variables/methods start with is/has/can/should
- `[recommended]` Avoid abbreviations — `calculateTotal` not `calcTot`

## Method Length

- `[recommended]` Methods should be under 30 lines
- `[must-follow]` Methods must not exceed 60 lines — split into smaller functions

## Class Responsibility

- `[must-follow]` Each class has one clear responsibility (SRP)
- `[must-follow]` A class should not depend on more than 7 other concrete classes
- `[recommended]` Prefer composition over inheritance

## Code Duplication

- `[must-follow]` No duplicated blocks exceeding 50 lines — extract shared logic
- `[recommended]` Three or more similar blocks exceeding 10 lines should be refactored

## File Organization

- `[must-follow]` Imports grouped by: standard library, third-party, project-internal
- `[recommended]` Public API before private implementation within a file
- `[recommended]` Related constants near their usage, not in a global constants file

## Error Handling

- `[must-follow]` Never catch and silently ignore exceptions (empty catch blocks)
- `[must-follow]` Log or propagate — do not swallow errors
- `[recommended]` Use specific exception types, not generic Exception/Error
