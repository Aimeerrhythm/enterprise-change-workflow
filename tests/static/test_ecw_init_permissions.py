"""Tests for ecw-init permission configuration.

Verifies that ecw-init command configures Write permissions for ECW artifact paths,
preventing permission confirmation prompts during workflow execution.
Finding-03 from WMS P0 integration test.
"""
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestEcwInitPermissions:
    """Verify ecw-init configures Write permissions for ECW paths."""

    @pytest.fixture(autouse=True)
    def load_command(self):
        self.content = (ROOT / "commands" / "ecw-init.md").read_text()
        self.lower = self.content.lower()

    def test_ecw_init_configures_ecw_write_permission(self):
        """ecw-init must configure Write permission for .claude/ecw/** paths."""
        has_ecw_write = bool(
            "write(.claude/ecw/" in self.lower
            or 'write(.claude/ecw/' in self.content
            or "Write(.claude/ecw/" in self.content
        )
        assert has_ecw_write, \
            "ecw-init must configure Write(.claude/ecw/**) permission"

    def test_ecw_init_configures_plans_write_permission(self):
        """ecw-init must configure Write permission for .claude/plans/** paths."""
        has_plans_write = bool(
            "write(.claude/plans/" in self.lower
            or 'write(.claude/plans/' in self.content
            or "Write(.claude/plans/" in self.content
        )
        assert has_plans_write, \
            "ecw-init must configure Write(.claude/plans/**) permission"
