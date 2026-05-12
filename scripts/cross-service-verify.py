#!/usr/bin/env python3
"""ECW Phase 5 cross-service verification — Dubbo SNAPSHOT version consistency.

For every Provider in the workspace that has published api-ready.json with
modules[], scan every other service (Consumer)'s pom files and verify that
any declared dependency on a published artifactId pins the SNAPSHOT version
from api-ready.json. Mismatch = HARD FAIL (version-pollution bug).

Usage:
  python3 scripts/cross-service-verify.py <workspace_dir> <wf_id>

Exit code:
  0 = all PASS (or no Providers / no cross-service deps to check)
  1 = at least one FAIL
  2 = invocation / parsing error

Output: JSON report on stdout. Designed to be invoked by the workspace
coordinator at Phase 5 — replaces the prompt-level instruction with a
deterministic check.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET


def _strip_ns(tag):
    """Drop XML namespace prefix from tag name: '{...}groupId' -> 'groupId'."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _load_yaml(path):
    """Minimal YAML loader for workspace.yml — falls back to PyYAML if available."""
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Hand-roll the small subset we actually need (services list with id field)
        services = []
        cur = None
        with open(path, encoding="utf-8") as f:
            in_services = False
            for line in f:
                if re.match(r"^services\s*:", line):
                    in_services = True
                    continue
                if in_services:
                    if re.match(r"^\S", line):
                        in_services = False
                        continue
                    m = re.match(r"^\s*-\s*id\s*:\s*(\S+)", line)
                    if m:
                        if cur:
                            services.append(cur)
                        cur = {"id": m.group(1)}
                        continue
                    m = re.match(r"^\s+(\w+)\s*:\s*(.+)$", line)
                    if m and cur is not None:
                        cur[m.group(1)] = m.group(2).strip()
            if cur:
                services.append(cur)
        return {"services": services}


def _read_api_ready(workspace_dir, service_id, wf_id):
    """Return modules list from a service's api-ready.json, or None if absent."""
    path = os.path.join(
        workspace_dir, service_id,
        ".claude", "ecw", "session-data", wf_id, "api-ready.json",
    )
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"_error": f"failed to parse {path}: {e}"}
    modules = data.get("modules")
    if not isinstance(modules, list):
        return {"_error": f"{path}: modules[] missing or not a list"}
    return {"modules": modules, "service": data.get("service", service_id)}


def _find_pom_files(service_root):
    """Walk service_root for pom.xml files, skipping target/ and hidden dirs."""
    poms = []
    for dirpath, dirnames, filenames in os.walk(service_root):
        # In-place prune
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in ("target", "node_modules")
        ]
        if "pom.xml" in filenames:
            poms.append(os.path.join(dirpath, "pom.xml"))
    return poms


def _extract_properties(root):
    """Return dict of <properties> child name -> text from a pom root element."""
    props = {}
    for child in root:
        if _strip_ns(child.tag) == "properties":
            for prop in child:
                name = _strip_ns(prop.tag)
                props[name] = (prop.text or "").strip()
    return props


def _resolve_version(raw, properties):
    """Resolve ${var} placeholders against properties, single level only."""
    if raw is None:
        return None
    raw = raw.strip()
    m = re.fullmatch(r"\$\{([^}]+)\}", raw)
    if m:
        return properties.get(m.group(1))
    return raw


def _scan_pom_dependencies(pom_path):
    """Return list of (artifactId, raw_version, resolved_version) found in <dependency> nodes.

    Looks at <dependencies>/<dependency> AND <dependencyManagement>/<dependencies>/<dependency>.
    """
    try:
        tree = ET.parse(pom_path)
    except ET.ParseError:
        return []
    root = tree.getroot()
    properties = _extract_properties(root)

    deps = []

    def walk(elem, inside_deps=False):
        tag = _strip_ns(elem.tag)
        if tag == "dependencies":
            for child in elem:
                if _strip_ns(child.tag) == "dependency":
                    artifact_id = None
                    version = None
                    for sub in child:
                        st = _strip_ns(sub.tag)
                        if st == "artifactId":
                            artifact_id = (sub.text or "").strip()
                        elif st == "version":
                            version = (sub.text or "").strip()
                    if artifact_id:
                        deps.append((artifact_id, version, _resolve_version(version, properties)))
            return  # don't recurse into dependency children
        for child in elem:
            walk(child)

    walk(root)
    return deps


def verify(workspace_dir, wf_id):
    """Main verification entry — returns report dict.

    Report shape:
      {
        "wf_id": str,
        "providers": [{"service": id, "modules": [...]}],
        "checks": [
          {"consumer", "provider", "module", "expected_version",
           "actual_version", "raw_version", "pom_file", "status"}
        ],
        "warnings": [str],
        "summary": {"pass": n, "fail": n, "skip": n}
      }
    """
    report = {
        "wf_id": wf_id,
        "providers": [],
        "checks": [],
        "warnings": [],
        "summary": {"pass": 0, "fail": 0, "skip": 0},
    }

    ws_yml = os.path.join(workspace_dir, ".claude", "ecw", "workspace.yml")
    if not os.path.isfile(ws_yml):
        report["warnings"].append(f"workspace.yml not found at {ws_yml}")
        return report

    services = _load_yaml(ws_yml).get("services") or []
    service_ids = [s.get("id") for s in services if s.get("id")]

    # Collect Providers (services that wrote api-ready.json with modules[])
    providers = []
    for sid in service_ids:
        info = _read_api_ready(workspace_dir, sid, wf_id)
        if info is None:
            continue
        if "_error" in info:
            report["warnings"].append(info["_error"])
            continue
        providers.append({
            "service": sid,
            "modules": info["modules"],
        })
    report["providers"] = providers

    if not providers:
        return report

    # For every Provider's published module, scan every other service's poms.
    for provider in providers:
        pid = provider["service"]
        # Build artifactId -> expected version map
        expected = {}
        for m in provider["modules"]:
            name = m.get("name")
            ver = m.get("version")
            if not name or not ver:
                report["warnings"].append(
                    f"{pid}/api-ready.json: modules entry missing name or version: {m}"
                )
                continue
            expected[name] = ver

        if not expected:
            continue

        for cid in service_ids:
            if cid == pid:
                continue
            consumer_root = os.path.join(workspace_dir, cid)
            if not os.path.isdir(consumer_root):
                report["warnings"].append(f"consumer dir missing: {consumer_root}")
                continue
            poms = _find_pom_files(consumer_root)
            for pom in poms:
                deps = _scan_pom_dependencies(pom)
                for artifact_id, raw_version, resolved_version in deps:
                    if artifact_id not in expected:
                        continue
                    rel_pom = os.path.relpath(pom, workspace_dir)
                    expected_ver = expected[artifact_id]
                    if resolved_version is None and raw_version and raw_version.startswith("${"):
                        # Property variable couldn't be resolved within this pom
                        report["warnings"].append(
                            f"{rel_pom}: {artifact_id} version uses unresolved property "
                            f"'{raw_version}' — manual check required"
                        )
                        report["checks"].append({
                            "consumer": cid,
                            "provider": pid,
                            "module": artifact_id,
                            "expected_version": expected_ver,
                            "actual_version": None,
                            "raw_version": raw_version,
                            "pom_file": rel_pom,
                            "status": "SKIP",
                        })
                        report["summary"]["skip"] += 1
                        continue

                    actual = resolved_version or raw_version
                    status = "PASS" if actual == expected_ver else "FAIL"
                    report["checks"].append({
                        "consumer": cid,
                        "provider": pid,
                        "module": artifact_id,
                        "expected_version": expected_ver,
                        "actual_version": actual,
                        "raw_version": raw_version,
                        "pom_file": rel_pom,
                        "status": status,
                    })
                    report["summary"][status.lower()] += 1

    return report


def main(argv):
    if len(argv) != 3:
        print("usage: cross-service-verify.py <workspace_dir> <wf_id>", file=sys.stderr)
        return 2
    workspace_dir = os.path.abspath(argv[1])
    wf_id = argv[2]
    if not os.path.isdir(workspace_dir):
        print(f"workspace_dir not a directory: {workspace_dir}", file=sys.stderr)
        return 2

    report = verify(workspace_dir, wf_id)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["summary"]["fail"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
