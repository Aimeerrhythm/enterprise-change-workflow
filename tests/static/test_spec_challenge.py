"""Tests for spec-challenge SKILL.md adversarial review architecture.

Content-assertion tests verifying the spec-challenge skill:
adversarial agent dispatch, user-driven decision flow, auto-trigger,
and session split recommendation.
"""
import re

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


class TestSpecChallengeArchitecture:
    """Verify spec-challenge SKILL.md has adversarial review architecture."""

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "spec-challenge" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_has_agent_dispatch(self):
        """Must describe dispatching spec-challenge agent for review."""
        assert "agent" in self.lower and "dispatch" in self.lower

    def test_model_selection_opus(self):
        """Must specify opus model for adversarial review."""
        assert "opus" in self.lower

    def test_has_user_driven_decisions(self):
        """Must describe user-driven per-item confirmation (AskUserQuestion)."""
        assert "askuserquestion" in self.lower

    def test_auto_trigger_p0(self):
        """Must auto-trigger for P0 changes."""
        assert re.search(r'p0.{0,40}(auto|trigger|after)', self.lower) or \
               re.search(r'(auto\w*|trigger|after).{0,60}p0', self.lower)

    def test_auto_trigger_p1_cross_domain(self):
        """Must auto-trigger for P1 cross-domain changes."""
        assert re.search(r'p1.{0,40}cross.?domain', self.lower)

    def test_persists_report_file(self):
        """Must persist review report to spec-challenge-report.md."""
        assert "spec-challenge-report.md" in self.content

    def test_has_session_split_recommendation(self):
        """Must recommend session split after review completion."""
        assert "session" in self.lower and "split" in self.lower or \
               "new session" in self.lower

    def test_has_timeout(self):
        """Must specify timeout for agent dispatch (300s)."""
        assert "300" in self.content


class TestSpecChallengePlanRevision:
    """Verify spec-challenge has correct Plan revision strategy.

    Finding-05: Plan revision via subagent Edit on 75KB file caused 33-min bottleneck.
    Coordinator should revise directly using Write, not dispatch subagent with Edit.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "spec-challenge" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_plan_revision_by_coordinator(self):
        """Plan revision should be done by coordinator (main session), not subagent."""
        has_coordinator_revision = bool(
            re.search(r'coordinator.{0,80}(revis|modif|updat|rewrit).{0,40}plan', self.lower)
            or re.search(r'(revis|modif|updat|rewrit).{0,40}plan.{0,80}coordinator', self.lower)
            or re.search(r'(do not|never|avoid).{0,40}(dispatch|sub-?agent).{0,40}(revis|modif|rewrit)', self.lower)
            or re.search(r'(main session|directly).{0,60}(revis|modif|rewrit).{0,40}plan', self.lower)
        )
        assert has_coordinator_revision, \
            "Plan revision must be done by coordinator, not subagent"

    def test_plan_revision_uses_write(self):
        """Plan revision should use Write (full rewrite), not Edit (partial replace)."""
        has_write_instruction = bool(
            re.search(r'write.{0,40}(overwrite|rewrite|full|entire).{0,40}plan', self.lower)
            or re.search(r'(overwrite|rewrite|full|entire).{0,40}plan.{0,40}write', self.lower)
            or re.search(r'(use|prefer)\s+write\b.{0,40}(plan|file)', self.lower)
        )
        assert has_write_instruction, \
            "Plan revision must use Write tool for full rewrite"

    def test_plan_revision_no_edit_for_large_files(self):
        """Must warn against using Edit tool for large Plan files."""
        has_edit_warning = bool(
            re.search(r'(do not|never|avoid).{0,40}edit.{0,40}(large|big|plan)', self.lower)
            or re.search(r'edit.{0,60}(fail|error|unreliable|fragile).{0,40}(large|big|plan)', self.lower)
            or re.search(r'(large|big).{0,40}(file|plan).{0,40}(do not|never|avoid).{0,40}edit', self.lower)
        )
        assert has_edit_warning, \
            "Must warn against Edit tool for large Plan files"


class TestSpecChallengeSessionContinuity:
    """Verify spec-challenge recommends continuing in current session.

    Finding-06: Session switch UX is poor — manual close/open/passphrase.
    Should recommend continuing in current session with PreCompact protection.
    """

    @pytest.fixture(autouse=True)
    def load_skill(self):
        self.content = (ROOT / "skills" / "spec-challenge" / "SKILL.md").read_text()
        self.lower = self.content.lower()

    def test_continue_is_recommended(self):
        """'Continue in current session' must be the recommended option."""
        has_continue_recommended = bool(
            re.search(r'continue.{0,40}(current|this).{0,20}session.{0,40}recommend', self.lower)
            or re.search(r'recommend.{0,40}continue.{0,40}(current|this).{0,20}session', self.lower)
        )
        assert has_continue_recommended, \
            "Continue in current session must be the recommended option"

    def test_no_scary_warning_on_continue(self):
        """Must NOT have scary warning about information loss on continue option."""
        has_scary_warning = bool(
            re.search(
                r'continue.{0,80}(information loss|信息丢失|context compression.{0,20}(loss|丢失))',
                self.lower
            )
        )
        assert not has_scary_warning, \
            "Must not have scary warning about information loss on continue option"

    def test_mentions_precompact_protection(self):
        """Must mention PreCompact hook as context protection mechanism."""
        has_precompact = bool(
            re.search(r'pre.?compact.{0,60}(protect|preserv|sav|checkpoint|recover)', self.lower)
            or re.search(r'(protect|preserv|sav|checkpoint|recover).{0,60}pre.?compact', self.lower)
        )
        assert has_precompact, \
            "Must mention PreCompact hook as context protection mechanism"
