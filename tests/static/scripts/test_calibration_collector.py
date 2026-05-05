"""Tests for scripts/calibration-collector.py — Phase 3 multi-skill calibration data collector.

Issue #47: TDD tests written before implementation. All tests should FAIL until
calibration-collector.py is created.

The collector is a CLI script:
  python3 scripts/calibration-collector.py <project_root> <session_data_dir>
Outputs structured YAML to stdout with calibration dimensions.
"""
import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = ROOT / "scripts"
HOOKS_DIR = ROOT / "hooks"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_session_state(session_dir: Path, *, baseline_commit: str = "abc1234",
                          routing=None, domains=None):
    if routing is None:
        routing = ["ecw:risk-classifier", "ecw:domain-collab", "Phase 2",
                   "ecw:writing-plans", "ecw:spec-challenge",
                   "ecw:impl-verify", "ecw:biz-impact-analysis", "Phase 3"]
    if domains is None:
        domains = ["payment", "order"]
    state_file = session_dir / "session-state.md"
    import yaml as _yaml
    routing_yaml = _yaml.dump(routing, default_flow_style=True).strip()
    domains_yaml = _yaml.dump(domains, default_flow_style=True).strip()
    state_file.write_text(
        "# ECW Session State\n\n"
        "<!-- ECW:STATUS:START -->\n"
        "risk_level: P0\n"
        f"domains: {domains_yaml}\n"
        "mode: cross-domain\n"
        f"routing: {routing_yaml}\n"
        "current_phase: biz-impact-complete\n"
        f"baseline_commit: {baseline_commit}\n"
        "implementation_strategy: direct\n"
        "auto_continue: true\n"
        "<!-- ECW:STATUS:END -->\n"
    )
    return state_file


def _write_path_mappings(ecw_dir: Path):
    (ecw_dir / "ecw-path-mappings.md").write_text(textwrap.dedent("""\
        # ECW Path Mappings

        | Path Pattern | Domain |
        |---|---|
        | src/payment/ | payment |
        | src/order/ | order |
        | src/inventory/ | inventory |
    """))


def _write_plan_file(plans_dir: Path, task_count=5, files=None):
    plans_dir.mkdir(parents=True, exist_ok=True)
    if files is None:
        files = ["src/payment/RefundService.java", "src/payment/RefundController.java",
                 "src/order/OrderService.java"]
    tasks = []
    for i in range(1, task_count + 1):
        tasks.append(f"### Task {i}: Task description {i}\n\n**Files**: {files[0]}\n")
    files_section = "\n".join(f"- `{f}`" for f in files)
    plan = (
        "# Implementation Plan\n\n"
        f"## Files to Modify\n\n{files_section}\n\n"
        + "\n".join(tasks)
    )
    plan_path = plans_dir / "20260504-a3f1-plan.md"
    plan_path.write_text(plan)
    return plan_path


def _write_spec_challenge_report(session_dir: Path, accepted=3, rejected=1, deferred=0):
    rows = []
    for i in range(1, accepted + 1):
        rows.append(f"| F{i} | accepted | — |")
    for i in range(accepted + 1, accepted + rejected + 1):
        rows.append(f"| F{i} | rejected | user rationale |")
    for i in range(accepted + rejected + 1, accepted + rejected + deferred + 1):
        rows.append(f"| F{i} | deferred | — |")
    table = "\n".join(rows)
    report = (
        "# Spec-Challenge Report\n\n"
        "## Findings\n\nF1: some finding\n\n"
        "## User Decisions\n\n"
        "| Finding | Decision | Rationale |\n"
        "|---------|----------|-----------|\n"
        f"{table}\n"
    )
    (session_dir / "spec-challenge-report.md").write_text(report)


def _write_impl_verify_findings(session_dir: Path, req_findings=0, other_findings=2):
    lines = ["# impl-verify Findings\n\n## Round 1\n"]
    for i in range(req_findings):
        lines.append(
            f"- **must-fix** [dimension: requirements] Finding {i+1}: "
            "Requirement gap — missing edge case\n"
        )
    for i in range(other_findings):
        lines.append(
            f"- **must-fix** [dimension: code-quality] Finding {i+1}: "
            "Code quality issue\n"
        )
    (session_dir / "impl-verify-findings.md").write_text("\n".join(lines))


def _run_collector(project_root: Path, session_data_dir: Path,
                   git_diff_files=None, git_log_lines=None, env=None):
    """Run calibration-collector.py with mocked git commands via subprocess."""
    script = SCRIPTS_DIR / "calibration-collector.py"
    if not script.exists():
        pytest.skip("calibration-collector.py not yet implemented (TDD red phase)")

    # Write mock git wrappers into a temp bin dir
    import tempfile, os, stat
    bin_dir = Path(tempfile.mkdtemp())
    git_diff_output = "\n".join(git_diff_files or []) + "\n"
    git_log_output = "\n".join(git_log_lines or ["abc1234 step 1: init"]) + "\n"

    git_mock = bin_dir / "git"
    git_mock.write_text(
        "#!/bin/sh\n"
        'if echo "$@" | grep -q "diff"; then\n'
        f'  printf {repr(git_diff_output)}\n'
        'elif echo "$@" | grep -q "log"; then\n'
        f'  printf {repr(git_log_output)}\n'
        'else\n'
        '  exit 0\n'
        'fi\n'
    )
    git_mock.chmod(git_mock.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    run_env = os.environ.copy()
    run_env["PATH"] = f"{bin_dir}:{run_env['PATH']}"
    if env:
        run_env.update(env)

    result = subprocess.run(
        [sys.executable, str(script), str(project_root), str(session_data_dir)],
        capture_output=True, text=True, env=run_env
    )
    return result


# ── Existence check ─────────────────────────────────────────────────────────────

class TestCollectorExists:
    """The calibration-collector.py script must exist."""

    def test_script_exists(self):
        assert (SCRIPTS_DIR / "calibration-collector.py").exists(), \
            "scripts/calibration-collector.py must exist (issue #47 Phase B)"

    def test_script_has_module_docstring(self):
        content = (SCRIPTS_DIR / "calibration-collector.py").read_text()
        assert '"""' in content or "'''" in content, \
            "Script must have a module docstring"

    def test_script_accepts_two_args(self):
        """Running with wrong arg count must exit with non-zero and print usage."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "calibration-collector.py")],
            capture_output=True, text=True
        )
        assert result.returncode != 0, \
            "Must exit non-zero when called with no arguments"


# ── Domain Calibration ──────────────────────────────────────────────────────────

class TestDomainCalibration:
    """calibration-collector.py must compare predicted domains vs actual changed domains."""

    @pytest.fixture
    def project(self, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-a3f1"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="abc1234",
                              domains=["payment", "order"])
        _write_path_mappings(ecw_dir)
        return tmp_path, session_dir

    def test_domain_calibration_correct_prediction(self, project):
        """When changed files map to exactly the predicted domains, deviation is empty."""
        tmp_path, session_dir = project
        result = _run_collector(
            tmp_path, session_dir,
            git_diff_files=["src/payment/RefundService.java", "src/order/OrderService.java"],
        )
        assert result.returncode == 0, f"Collector failed: {result.stderr}"
        data = yaml.safe_load(result.stdout)
        dc = data.get("domain_calibration", {})
        assert dc.get("over_predicted", []) == []
        assert dc.get("missed", []) == []

    def test_domain_calibration_over_predicted(self, project):
        """When order was predicted but no order files changed → over_predicted = [order]."""
        tmp_path, session_dir = project
        result = _run_collector(
            tmp_path, session_dir,
            git_diff_files=["src/payment/RefundService.java"],
        )
        assert result.returncode == 0, f"Collector failed: {result.stderr}"
        data = yaml.safe_load(result.stdout)
        dc = data.get("domain_calibration", {})
        assert "order" in dc.get("over_predicted", [])
        assert "payment" not in dc.get("over_predicted", [])

    def test_domain_calibration_missed(self, project):
        """When inventory files changed but inventory was not predicted → missed = [inventory]."""
        tmp_path, session_dir = project
        result = _run_collector(
            tmp_path, session_dir,
            git_diff_files=["src/payment/RefundService.java",
                            "src/inventory/StockService.java"],
        )
        assert result.returncode == 0, f"Collector failed: {result.stderr}"
        data = yaml.safe_load(result.stdout)
        dc = data.get("domain_calibration", {})
        assert "inventory" in dc.get("missed", [])

    def test_domain_calibration_skipped_when_no_domain_collab(self, tmp_path):
        """When domain-collab is NOT in routing (single-domain), domain_calibration is skipped."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-b1f2"
        session_dir.mkdir(parents=True)
        # Routing without domain-collab
        _write_session_state(session_dir, baseline_commit="abc1234",
                              routing=["ecw:risk-classifier", "Phase 2",
                                       "ecw:writing-plans", "ecw:impl-verify", "Phase 3"],
                              domains=["payment"])
        _write_path_mappings(ecw_dir)
        result = _run_collector(
            tmp_path, session_dir,
            git_diff_files=["src/payment/RefundService.java"],
        )
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        dc = data.get("domain_calibration", {})
        assert dc.get("skipped") is True, \
            "domain_calibration must be skipped when domain-collab not in routing"


# ── Plan Calibration ────────────────────────────────────────────────────────────

class TestPlanCalibration:
    """calibration-collector.py must compare planned vs actual task count and files."""

    @pytest.fixture
    def project(self, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-a3f1"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="abc1234")
        plans_dir = tmp_path / ".claude" / "plans"
        plan_path = _write_plan_file(plans_dir, task_count=5,
                                      files=["src/payment/A.java", "src/order/B.java"])
        # Store plan path in session state so collector can find it
        state_file = session_dir / "session-state.md"
        content = state_file.read_text()
        state_file.write_text(content.replace(
            "<!-- ECW:STATUS:END -->",
            f"plan_path: {plan_path}\n<!-- ECW:STATUS:END -->"
        ))
        return tmp_path, session_dir

    def test_plan_task_ratio_correct(self, project):
        """task_ratio = actual_commits / planned_tasks."""
        tmp_path, session_dir = project
        # 7 actual commits (plan had 5 tasks → ratio 1.4)
        commits = [f"abc000{i} step {i}: desc" for i in range(1, 8)]
        result = _run_collector(tmp_path, session_dir, git_log_lines=commits,
                                git_diff_files=["src/payment/A.java"])
        assert result.returncode == 0, f"Collector failed: {result.stderr}"
        data = yaml.safe_load(result.stdout)
        pc = data.get("plan_calibration", {})
        assert pc.get("planned_tasks") == 5
        assert pc.get("actual_commits") == 7
        assert abs(pc.get("task_ratio", 0) - 1.4) < 0.01

    def test_plan_uncovered_files_detected(self, project):
        """Files in git diff but not in Plan are reported as uncovered_files."""
        tmp_path, session_dir = project
        result = _run_collector(
            tmp_path, session_dir,
            git_log_lines=["abc0001 step 1: desc"],
            git_diff_files=["src/payment/A.java", "src/payment/UnplannedFile.java"],
        )
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        pc = data.get("plan_calibration", {})
        uncovered = pc.get("uncovered_files", [])
        assert any("UnplannedFile" in f for f in uncovered), \
            "UnplannedFile.java must appear in uncovered_files"
        assert not any("A.java" in f for f in uncovered), \
            "A.java was in the Plan and must not appear in uncovered_files"

    def test_plan_calibration_skipped_when_no_writing_plans(self, tmp_path):
        """When writing-plans not in routing (P3), plan_calibration is skipped."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-p3"
        session_dir.mkdir(parents=True)
        _write_session_state(
            session_dir, baseline_commit="abc1234",
            routing=["ecw:risk-classifier", "Phase 3"],
        )
        result = _run_collector(tmp_path, session_dir,
                                git_log_lines=["abc step 1: trivial fix"],
                                git_diff_files=["src/Trivial.java"])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        pc = data.get("plan_calibration", {})
        assert pc.get("skipped") is True, \
            "plan_calibration must be skipped when writing-plans not in routing"


# ── Spec-Challenge Calibration ──────────────────────────────────────────────────

class TestSpecChallengeCalibration:
    """calibration-collector.py must parse User Decisions table for acceptance rate."""

    @pytest.fixture
    def project(self, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-a3f1"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="abc1234")
        return tmp_path, session_dir

    def test_acceptance_rate_computed(self, project):
        """acceptance_rate = accepted / (accepted + rejected)."""
        tmp_path, session_dir = project
        _write_spec_challenge_report(session_dir, accepted=3, rejected=1, deferred=0)
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        sc = data.get("spec_challenge_calibration", {})
        assert sc.get("accepted") == 3
        assert sc.get("rejected") == 1
        assert abs(sc.get("acceptance_rate", 0) - 0.75) < 0.01

    def test_skipped_when_no_spec_challenge_in_routing(self, tmp_path):
        """When spec-challenge not in routing, spec_challenge_calibration is skipped."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-nsc"
        session_dir.mkdir(parents=True)
        _write_session_state(
            session_dir, baseline_commit="abc1234",
            routing=["ecw:risk-classifier", "Phase 2", "ecw:writing-plans",
                     "ecw:impl-verify", "Phase 3"],
        )
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        sc = data.get("spec_challenge_calibration", {})
        assert sc.get("skipped") is True

    def test_skipped_when_no_user_decisions_table(self, project):
        """When spec-challenge-report.md lacks User Decisions table, skip calibration."""
        tmp_path, session_dir = project
        (session_dir / "spec-challenge-report.md").write_text(
            "# Spec-Challenge Report\n\n## Findings\n\nF1: some finding\n"
        )
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        sc = data.get("spec_challenge_calibration", {})
        assert sc.get("skipped") is True


# ── Requirements Calibration ────────────────────────────────────────────────────

class TestRequirementsCalibration:
    """calibration-collector.py must detect requirement-dimension findings from impl-verify."""

    @pytest.fixture
    def project(self, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-a3f1"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="abc1234",
                              routing=["ecw:risk-classifier",
                                       "ecw:requirements-elicitation", "Phase 2",
                                       "ecw:writing-plans", "ecw:impl-verify", "Phase 3"])
        return tmp_path, session_dir

    def test_no_requirement_gaps_when_clean(self, project):
        """When impl-verify has no requirement findings, requirement_gap_count = 0."""
        tmp_path, session_dir = project
        _write_impl_verify_findings(session_dir, req_findings=0, other_findings=2)
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        rc = data.get("requirements_calibration", {})
        assert rc.get("requirement_gap_count", 0) == 0

    def test_requirement_gaps_detected(self, project):
        """When impl-verify has requirement findings, they are counted as gaps."""
        tmp_path, session_dir = project
        _write_impl_verify_findings(session_dir, req_findings=2, other_findings=1)
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        rc = data.get("requirements_calibration", {})
        assert rc.get("requirement_gap_count") == 2

    def test_skipped_when_no_requirements_elicitation(self, tmp_path):
        """When requirements-elicitation not in routing, requirements_calibration is skipped."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-nre"
        session_dir.mkdir(parents=True)
        _write_session_state(
            session_dir, baseline_commit="abc1234",
            routing=["ecw:risk-classifier", "Phase 2", "ecw:writing-plans",
                     "ecw:impl-verify", "Phase 3"],
        )
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        rc = data.get("requirements_calibration", {})
        assert rc.get("skipped") is True


# ── Baseline Commit Fallback ────────────────────────────────────────────────────

class TestBaselineCommitFallback:
    """When baseline_commit is TBD, collector must attempt a fallback heuristic."""

    def test_fallback_when_baseline_is_tbd(self, tmp_path):
        """When baseline_commit = TBD, collector uses heuristic (not crash)."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-tbd"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="TBD")
        _write_path_mappings(ecw_dir)
        result = _run_collector(
            tmp_path, session_dir,
            git_diff_files=["src/payment/A.java"],
            git_log_lines=["abc0002 step 2: add test", "abc0001 step 1: initial"],
        )
        assert result.returncode == 0, \
            f"Must not crash when baseline_commit=TBD; stderr: {result.stderr}"
        data = yaml.safe_load(result.stdout)
        assert data is not None, "Must output valid YAML even with TBD baseline"


# ── Output Format ───────────────────────────────────────────────────────────────

class TestOutputFormat:
    """Collector output must be valid YAML with expected top-level keys."""

    @pytest.fixture
    def project(self, tmp_path):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260504-fmt"
        session_dir.mkdir(parents=True)
        _write_session_state(session_dir, baseline_commit="abc1234")
        _write_path_mappings(ecw_dir)
        return tmp_path, session_dir

    def test_output_is_valid_yaml(self, project):
        tmp_path, session_dir = project
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        parsed = yaml.safe_load(result.stdout)
        assert isinstance(parsed, dict), "Output must be a YAML mapping"

    def test_output_has_expected_top_level_keys(self, project):
        tmp_path, session_dir = project
        result = _run_collector(tmp_path, session_dir,
                                git_diff_files=[], git_log_lines=[])
        assert result.returncode == 0
        data = yaml.safe_load(result.stdout)
        expected_keys = {
            "domain_calibration", "plan_calibration",
            "spec_challenge_calibration", "requirements_calibration",
        }
        assert expected_keys.issubset(data.keys()), \
            f"Missing top-level keys. Got: {set(data.keys())}"
