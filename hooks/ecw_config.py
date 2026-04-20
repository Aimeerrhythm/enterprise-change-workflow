#!/usr/bin/env python3
"""ECW shared configuration reader.

Provides a single implementation of ecw.yml reading for all hooks.
"""

import os


def read_ecw_config(cwd):
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


def read_plugin_version():
    """Read the plugin's own version from package.json."""
    import json as _json
    pkg = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "package.json",
    )
    try:
        with open(pkg, encoding="utf-8") as f:
            return _json.load(f).get("version", "")
    except Exception:
        return ""
