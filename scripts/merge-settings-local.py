#!/usr/bin/env python3
"""Merge ECW project-local settings into .claude/settings.local.json.

Usage:
  python3 scripts/merge-settings-local.py <project_root> [<template_path>]

Behavior:
- Creates .claude/settings.local.json from template if missing
- Merges permissions.allow by set union, preserving existing order
- Merges hooks by event + exact command match, preserving unrelated hooks
- Fails with non-zero exit code if existing JSON is invalid
"""

import json
import os
import sys
from copy import deepcopy


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _merge_permissions(target, template):
    perms = target.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    existing = set(allow)
    for item in template.get("permissions", {}).get("allow", []):
        if item not in existing:
            allow.append(item)
            existing.add(item)


def _hook_commands(entry):
    return [h.get("command") for h in entry.get("hooks", []) if h.get("command")]


def _merge_hooks(target, template):
    target_hooks = target.setdefault("hooks", {})
    for event, template_entries in template.get("hooks", {}).items():
        existing_entries = target_hooks.setdefault(event, [])
        existing_commands = set()
        for entry in existing_entries:
            existing_commands.update(_hook_commands(entry))
        for template_entry in template_entries:
            commands = _hook_commands(template_entry)
            if commands and all(cmd in existing_commands for cmd in commands):
                continue
            existing_entries.append(deepcopy(template_entry))
            existing_commands.update(commands)


def main(argv):
    if len(argv) not in (2, 3):
        print("Usage: merge-settings-local.py <project_root> [<template_path>]", file=sys.stderr)
        return 2

    project_root = os.path.abspath(argv[1])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_template = os.path.join(os.path.dirname(script_dir), "templates", "settings.local.ecw.json")
    template_path = os.path.abspath(argv[2]) if len(argv) == 3 else default_template
    target_path = os.path.join(project_root, ".claude", "settings.local.json")

    try:
        template = _load_json(template_path)
    except Exception as exc:
        print(f"ERROR: failed to read template JSON: {template_path}: {exc}", file=sys.stderr)
        return 1

    if not os.path.exists(target_path):
        _dump_json(target_path, deepcopy(template))
        print(json.dumps({"status": "created", "path": target_path}, ensure_ascii=False))
        return 0

    try:
        target = _load_json(target_path)
    except Exception as exc:
        print(f"ERROR: invalid JSON in {target_path}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(target, dict):
        print(f"ERROR: root of {target_path} must be a JSON object", file=sys.stderr)
        return 1

    before = json.dumps(target, ensure_ascii=False, sort_keys=True)
    _merge_permissions(target, template)
    _merge_hooks(target, template)
    after = json.dumps(target, ensure_ascii=False, sort_keys=True)

    if before == after:
        print(json.dumps({"status": "unchanged", "path": target_path}, ensure_ascii=False))
        return 0

    _dump_json(target_path, target)
    print(json.dumps({"status": "updated", "path": target_path}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
