"""DC-5: Cross-skill artifact files should have schema definitions.

Source: OpenAI Agents SDK — Sessions for structured state;
        Data Contracts (Andrew Jones, 2023).
"""
from __future__ import annotations

from pathlib import Path

import pytest

SCHEMA_FILE = Path(__file__).resolve().parent.parent.parent / "templates" / "artifact-schemas.md"
KNOWN_ARTIFACTS = [
    "session-state.md",
    "domain-collab-report.md",
    "knowledge-summary.md",
    "phase2-assessment.md",
    "requirements-summary.md",
    "impl-verify-findings.md",
    "spec-challenge-report.md",
]


class TestArtifactSchema:

    def test_schema_file_exists(self):
        """artifact-schemas.md should exist in templates/."""
        assert SCHEMA_FILE.exists()

    def test_all_artifacts_have_schema(self):
        """All known artifact files should be documented in the schema."""
        content = SCHEMA_FILE.read_text(encoding="utf-8")
        for artifact in KNOWN_ARTIFACTS:
            assert artifact in content, f"'{artifact}' not in schema"
