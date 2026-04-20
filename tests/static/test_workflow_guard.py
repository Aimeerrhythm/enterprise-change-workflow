"""DC-2: verify-completion should contain workflow integrity checks.

Source: Anthropic "Building Effective Agents" — guardrails pattern;
        OpenAI Agents SDK — "fail fast when checks do not pass".
"""
from __future__ import annotations

from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


class TestWorkflowGuardPresence:

    def test_verify_completion_references_ecw_artifacts(self):
        """verify-completion should be aware of ECW artifact paths."""
        content = (HOOKS_DIR / "verify-completion.py").read_text(encoding="utf-8")
        assert "session-data" in content or "session_state" in content

    def test_references_impl_verify(self):
        """verify-completion should reference impl-verify for semantic verification reminder."""
        content = (HOOKS_DIR / "verify-completion.py").read_text(encoding="utf-8")
        assert "impl-verify" in content or "impl_verify" in content

    def test_checks_impl_verify_was_executed(self):
        """verify-completion should verify impl-verify actually ran (not just remind)."""
        content = (HOOKS_DIR / "verify-completion.py").read_text(encoding="utf-8")
        assert "impl-verify-findings" in content or "impl_verify_findings" in content
