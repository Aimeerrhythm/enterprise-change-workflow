"""Cross-step assertion engine for chain eval.

Uses a structured dict mini-DSL instead of eval() to avoid injection risk.

Check format:
    {
        "field": "step-name.field_name",   # resolves artifacts['step-name']['field:field_name']
        "op": "==" | "!=" | "in" | "contains" | ">=" | "<=" | ">" | "<",
        "value": <comparison value>
    }

Numeric operators (>=, <=, >, <) coerce the artifact value to int/float.
"""
from __future__ import annotations

_NUMERIC_OPS = {">=", "<=", ">", "<"}
_STRING_OPS = {"==", "!=", "in", "contains"}
_ALL_OPS = _NUMERIC_OPS | _STRING_OPS


def run_assertions(
    assertion_defs: list[dict],
    all_artifacts: dict[str, dict[str, str]],
) -> list[dict]:
    """Run chain-level assertions and return per-assertion results."""
    results = []
    for adef in assertion_defs:
        name = adef["name"]
        check_spec = adef["check"]
        try:
            passed = _evaluate_check(check_spec, all_artifacts)
            results.append({"name": name, "passed": passed, "error": None})
        except Exception as exc:
            results.append({"name": name, "passed": False, "error": str(exc)})
    return results


def validate_assertion_refs(
    assertion_defs: list[dict],
    all_artifacts: dict[str, dict[str, str]],
) -> None:
    """Verify that every assertion's field reference exists in the collected artifacts.

    Raises ValueError with a descriptive message on the first missing reference.
    Call this before run_assertions to get early, clear errors on authoring mistakes.
    """
    for adef in assertion_defs:
        check_spec = adef["check"]
        step_name, field_name = _parse_field_ref(check_spec["field"])
        if step_name not in all_artifacts:
            raise ValueError(
                f"Assertion '{adef['name']}' references step '{step_name}' "
                f"which has no collected artifacts. "
                f"Available steps: {list(all_artifacts.keys())}"
            )
        field_key = f"field:{field_name}"
        if field_key not in all_artifacts[step_name]:
            available = [k for k in all_artifacts[step_name] if k.startswith("field:")]
            raise ValueError(
                f"Assertion '{adef['name']}' references field '{field_name}' "
                f"from step '{step_name}', but that field was not captured. "
                f"Available fields: {[k[6:] for k in available]}"
            )


def _evaluate_check(
    check_spec: dict,
    artifacts: dict[str, dict[str, str]],
) -> bool:
    """Evaluate a single structured check against collected artifacts."""
    op = check_spec["op"]
    if op not in _ALL_OPS:
        raise ValueError(
            f"Unsupported operator '{op}'. Supported: {sorted(_ALL_OPS)}"
        )

    step_name, field_name = _parse_field_ref(check_spec["field"])
    step_artifacts = artifacts.get(step_name)
    if step_artifacts is None:
        raise KeyError(f"Step '{step_name}' not found in artifacts")

    raw_value = step_artifacts.get(f"field:{field_name}")
    if raw_value is None:
        raise KeyError(
            f"Field '{field_name}' not found in step '{step_name}'. "
            f"Available: {[k[6:] for k in step_artifacts if k.startswith('field:')]}"
        )

    expected = check_spec["value"]

    if op in _NUMERIC_OPS:
        actual = _coerce_numeric(raw_value, field_name)
        return _apply_numeric_op(actual, op, float(expected))

    # String operators
    if op == "==":
        return raw_value == str(expected)
    if op == "!=":
        return raw_value != str(expected)
    if op in ("in", "contains"):
        return str(expected) in raw_value

    raise ValueError(f"Unsupported operator '{op}'")  # unreachable


def _parse_field_ref(ref: str) -> tuple[str, str]:
    """Parse 'step-name.field_name' into (step_name, field_name).

    Uses the last '.' as the separator to support step names with hyphens.
    """
    idx = ref.rfind(".")
    if idx == -1:
        raise ValueError(f"Invalid field reference '{ref}': expected 'step-name.field_name'")
    return ref[:idx], ref[idx + 1:]


def _coerce_numeric(raw: str, field_name: str) -> float:
    """Coerce a string artifact value to float for numeric comparison."""
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise ValueError(
            f"Field '{field_name}' value '{raw}' cannot be coerced to a number "
            "for numeric comparison"
        )


def _apply_numeric_op(actual: float, op: str, expected: float) -> bool:
    if op == ">=":
        return actual >= expected
    if op == "<=":
        return actual <= expected
    if op == ">":
        return actual > expected
    if op == "<":
        return actual < expected
    raise ValueError(f"Unknown numeric op '{op}'")
