"""Unit tests for scripts/cross-service-verify.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "cross-service-verify.py"


@pytest.fixture
def verify_module():
    spec = importlib.util.spec_from_file_location("cross_service_verify", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cross_service_verify"] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_workspace(tmp_path, services, api_readys, poms):
    """Create a fake workspace tree.

    services: list of service ids
    api_readys: dict of {service_id: api_ready_dict}; missing = no api-ready.json
    poms: dict of {(service_id, relative_pom_path): pom_xml_string}
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    ecw_dir = ws / ".claude" / "ecw"
    ecw_dir.mkdir(parents=True)
    services_yaml = "services:\n"
    for sid in services:
        services_yaml += f"  - id: {sid}\n    base_branch: master\n"
    (ecw_dir / "workspace.yml").write_text(services_yaml)

    wf_id = "wf-test"
    for sid in services:
        (ws / sid).mkdir()
        if sid in api_readys:
            sd = ws / sid / ".claude" / "ecw" / "session-data" / wf_id
            sd.mkdir(parents=True)
            (sd / "api-ready.json").write_text(json.dumps(api_readys[sid]))
    for (sid, rel), content in poms.items():
        target = ws / sid / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return ws, wf_id


_POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <artifactId>consumer-app</artifactId>
  <version>1.0.0</version>
  <properties>
    <wms.api.version>{prop_version}</wms.api.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>{artifact}</artifactId>
      <version>{version}</version>
    </dependency>
  </dependencies>
</project>
"""


class TestVerify:
    def test_no_providers_returns_empty_report(self, tmp_path, verify_module):
        ws, wf = _make_workspace(tmp_path, ["a", "b"], {}, {})
        report = verify_module.verify(str(ws), wf)
        assert report["providers"] == []
        assert report["checks"] == []
        assert report["summary"] == {"pass": 0, "fail": 0, "skip": 0}

    def test_single_module_match_passes(self, tmp_path, verify_module):
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-wf-test-SNAPSHOT"}],
                "published_at": "2026-05-12T16:00:00+08:00",
            }},
            {("mf-wms", "pom.xml"): _POM_TEMPLATE.format(
                artifact="wms-interfaces",
                version="1.0.72-wf-test-SNAPSHOT",
                prop_version="unused",
            )},
        )
        report = verify_module.verify(str(ws), wf)
        assert len(report["providers"]) == 1
        assert len(report["checks"]) == 1
        check = report["checks"][0]
        assert check["status"] == "PASS"
        assert check["consumer"] == "mf-wms"
        assert check["provider"] == "wms"
        assert check["module"] == "wms-interfaces"
        assert report["summary"]["pass"] == 1

    def test_version_mismatch_fails(self, tmp_path, verify_module):
        """Reproduces the actual bug: Consumer pom still references release version."""
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-wf-test-SNAPSHOT"}],
                "published_at": "2026-05-12T16:00:00+08:00",
            }},
            {("mf-wms", "pom.xml"): _POM_TEMPLATE.format(
                artifact="wms-interfaces",
                version="1.0.71-0511",
                prop_version="unused",
            )},
        )
        report = verify_module.verify(str(ws), wf)
        assert report["summary"]["fail"] == 1
        check = report["checks"][0]
        assert check["status"] == "FAIL"
        assert check["actual_version"] == "1.0.71-0511"
        assert check["expected_version"] == "1.0.72-wf-test-SNAPSHOT"

    def test_unrelated_dependency_ignored(self, tmp_path, verify_module):
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-SNAPSHOT"}],
                "published_at": "2026-05-12T16:00:00+08:00",
            }},
            {("mf-wms", "pom.xml"): _POM_TEMPLATE.format(
                artifact="some-other-lib",
                version="9.9.9",
                prop_version="unused",
            )},
        )
        report = verify_module.verify(str(ws), wf)
        assert report["checks"] == []

    def test_property_placeholder_skipped_with_warning(self, tmp_path, verify_module):
        # Version that can't be resolved (property name doesn't match)
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties>
    <wms.api.version>1.0.0</wms.api.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>wms-interfaces</artifactId>
      <version>${unknown.version}</version>
    </dependency>
  </dependencies>
</project>
"""
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-SNAPSHOT"}],
                "published_at": "2026-05-12",
            }},
            {("mf-wms", "pom.xml"): pom},
        )
        report = verify_module.verify(str(ws), wf)
        assert report["summary"]["skip"] == 1
        assert any("unresolved property" in w for w in report["warnings"])

    def test_property_placeholder_resolved(self, tmp_path, verify_module):
        pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <properties>
    <wms.api.version>1.0.72-wf-test-SNAPSHOT</wms.api.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>com.example</groupId>
      <artifactId>wms-interfaces</artifactId>
      <version>${wms.api.version}</version>
    </dependency>
  </dependencies>
</project>
"""
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-wf-test-SNAPSHOT"}],
                "published_at": "2026-05-12",
            }},
            {("mf-wms", "pom.xml"): pom},
        )
        report = verify_module.verify(str(ws), wf)
        assert report["summary"]["pass"] == 1

    def test_multi_module_provider(self, tmp_path, verify_module):
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [
                    {"name": "wms-interfaces", "version": "1.0.72-SNAPSHOT"},
                    {"name": "wms-common", "version": "1.0.72-SNAPSHOT"},
                ],
                "published_at": "2026-05-12",
            }},
            {
                ("mf-wms", "app/pom.xml"): _POM_TEMPLATE.format(
                    artifact="wms-interfaces", version="1.0.72-SNAPSHOT", prop_version="x"),
                ("mf-wms", "core/pom.xml"): _POM_TEMPLATE.format(
                    artifact="wms-common", version="1.0.71-0511", prop_version="x"),
            },
        )
        report = verify_module.verify(str(ws), wf)
        assert report["summary"]["pass"] == 1
        assert report["summary"]["fail"] == 1

    def test_target_dir_pruned(self, tmp_path, verify_module):
        # pom.xml inside target/ should NOT be scanned (build artifact)
        ws, wf = _make_workspace(
            tmp_path,
            ["wms", "mf-wms"],
            {"wms": {
                "service": "wms",
                "modules": [{"name": "wms-interfaces", "version": "1.0.72-SNAPSHOT"}],
                "published_at": "2026-05-12",
            }},
            {
                ("mf-wms", "pom.xml"): _POM_TEMPLATE.format(
                    artifact="wms-interfaces", version="1.0.72-SNAPSHOT", prop_version="x"),
                ("mf-wms", "target/classes/META-INF/maven/x/pom.xml"): _POM_TEMPLATE.format(
                    artifact="wms-interfaces", version="0.0.0-stale", prop_version="x"),
            },
        )
        report = verify_module.verify(str(ws), wf)
        # Only the top-level pom should produce a check
        assert len(report["checks"]) == 1
        assert report["checks"][0]["status"] == "PASS"
