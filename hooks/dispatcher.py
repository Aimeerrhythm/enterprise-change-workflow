#!/usr/bin/env python3
"""ECW PreToolUse Dispatcher — unified entry point for all pre-tool-use checks.

Multiplexes multiple sub-hook modules through a single hooks.json entry.
Each sub-hook declares which risk profiles it applies to and a matcher
function that determines whether it should run for a given tool invocation.

Sub-hook interface:
    check(input_data, config) -> (action, message)
        action: "block" or "continue"
        message: text for systemMessage (may be empty)

Profile mapping (from risk level):
    P0 -> strict   (all checks)
    P1 -> standard (most checks)
    P2 -> standard
    P3 -> minimal  (only essential checks)
    default -> standard
"""

import importlib.util
import json
import os
import re
import sys


# ── Risk level → profile mapping ──

RISK_PROFILE_MAP = {
    "P0": "strict",
    "P1": "standard",
    "P2": "standard",
    "P3": "minimal",
}

DEFAULT_PROFILE = "standard"


# ── Matcher functions ──

def _is_task_complete(input_data):
    """Match TaskUpdate(status=completed) events."""
    return (input_data.get("tool_name") == "TaskUpdate"
            and input_data.get("tool_input", {}).get("status") == "completed")


def _is_edit_or_write(input_data):
    """Match Edit or Write tool events."""
    return input_data.get("tool_name") in ("Edit", "Write")


def _is_bash(input_data):
    """Match Bash tool events."""
    return input_data.get("tool_name") == "Bash"


def _always(input_data):
    """Match any tool event."""
    return True


# ── Sub-hook registry ──
# Format: (module_filename, applicable_profiles, matcher_function)
# Modules are loaded from the same directory as this dispatcher.

SUB_HOOKS = [
    ("verify-completion", ["minimal", "standard", "strict"], _is_task_complete),
    ("compact-suggest",   ["minimal", "standard", "strict"], _always),
    # Future sub-hooks (Wave 2+):
    # ("config-protect", ["minimal", "standard", "strict"], _is_edit_or_write),
    # ("secret-scan",    ["standard", "strict"],            _is_edit_or_write),
    # ("bash-preflight", ["standard", "strict"],            _is_bash),
]


# ── Profile resolution ──

def get_profile(cwd):
    """Determine current risk profile from environment or session-state.

    Priority:
    1. ECW_RISK_LEVEL environment variable (e.g. "P0", "P1")
    2. risk_level field in .claude/ecw/state/session-state.md
    3. Default: "standard"
    """
    # 1. Environment variable
    env_level = os.environ.get("ECW_RISK_LEVEL", "").strip().upper()
    if env_level in RISK_PROFILE_MAP:
        return RISK_PROFILE_MAP[env_level]

    # 2. session-state.md
    if cwd:
        state_file = os.path.join(cwd, ".claude", "ecw", "state", "session-state.md")
        try:
            if os.path.exists(state_file):
                with open(state_file, encoding="utf-8", errors="ignore") as f:
                    content = f.read(4096)  # Read only the header
                m = re.search(r'risk_level:\s*(P[0-3])', content, re.IGNORECASE)
                if m:
                    return RISK_PROFILE_MAP.get(m.group(1).upper(), DEFAULT_PROFILE)
        except Exception:
            pass

    # 3. Default
    return DEFAULT_PROFILE


# ── Module loading ──

def _load_subhook(module_filename):
    """Load a sub-hook module from the hooks directory by filename.

    Args:
        module_filename: Filename without .py extension (e.g. "verify-completion")

    Returns:
        Loaded module with a check(input_data, config) function, or None.
    """
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    module_path = os.path.join(hooks_dir, f"{module_filename}.py")
    if not os.path.exists(module_path):
        sys.stderr.write(f"ECW dispatcher: sub-hook file not found: {module_path}\n")
        return None

    # Use a sanitized module name for importlib (replace hyphens with underscores)
    module_name = f"ecw_hook_{module_filename.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_ecw_config(cwd):
    """Read .claude/ecw/ecw.yml configuration. Returns dict (empty on failure)."""
    try:
        import yaml as _yaml
    except ImportError:
        return {}
    ecw_yml = os.path.join(cwd, ".claude", "ecw", "ecw.yml")
    if not os.path.exists(ecw_yml):
        return {}
    try:
        with open(ecw_yml, encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}
    except Exception:
        return {}


# ── Main dispatcher ──

def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", "")
    profile = get_profile(cwd)
    config = _read_ecw_config(cwd) if cwd else {}
    config["_runtime_profile"] = profile

    system_messages = []

    for module_filename, profiles, matcher in SUB_HOOKS:
        if profile not in profiles:
            continue
        if not matcher(input_data):
            continue

        try:
            mod = _load_subhook(module_filename)
            if mod is None:
                continue

            action, message = mod.check(input_data, config)

            if action == "block":
                # First blocker wins — output deny and exit
                result = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny"
                    },
                    "systemMessage": message
                }
                print(json.dumps(result, ensure_ascii=False))
                sys.exit(2)

            if message:
                system_messages.append(message)

        except Exception as e:
            sys.stderr.write(f"ECW dispatcher: sub-hook '{module_filename}' error: {e}\n")

    # All sub-hooks passed
    if system_messages:
        print(json.dumps({"systemMessage": "\n\n".join(system_messages)}, ensure_ascii=False))
    else:
        print(json.dumps({"result": "continue"}))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Dispatcher errors must not block normal workflow
        print(json.dumps({"systemMessage": f"ECW dispatcher error: {e}"}))
        sys.exit(0)
