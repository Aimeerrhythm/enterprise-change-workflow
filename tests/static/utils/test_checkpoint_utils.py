"""Unit tests for CheckpointStore in hooks/marker_utils.py"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


def _load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def marker_module():
    return _load_module("marker_utils", "marker_utils.py")


@pytest.fixture
def project(tmp_path):
    """Project root with one workflow-id subdir."""
    wf_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf_dir.mkdir(parents=True)
    return tmp_path


def test_write_creates_file(marker_module, project):
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    store.write("phase2-assessment", "# Phase 2\ncontent")
    p = project / ".claude" / "ecw" / "session-data" / "20260427-1430" / "phase2-assessment.md"
    assert p.exists()
    assert "content" in p.read_text()


def test_read_existing(marker_module, project):
    p = project / ".claude" / "ecw" / "session-data" / "20260427-1430" / "knowledge-summary.md"
    p.write_text("summary text")
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    assert store.read("knowledge-summary") == "summary text"


def test_read_missing_returns_none(marker_module, project):
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    assert store.read("spec-challenge-report") is None


def test_exists_true_and_false(marker_module, project):
    p = project / ".claude" / "ecw" / "session-data" / "20260427-1430" / "domain-collab-report.md"
    p.write_text("x")
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    assert store.exists("domain-collab-report") is True
    assert store.exists("phase2-assessment") is False


def test_list_returns_existing_names(marker_module, project):
    wf_dir = project / ".claude" / "ecw" / "session-data" / "20260427-1430"
    (wf_dir / "session-state.md").write_text("state")
    (wf_dir / "phase2-assessment.md").write_text("p2")
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    names = store.list()
    assert "session-state" in names
    assert "phase2-assessment" in names


def test_from_latest_workflow_picks_newest(marker_module, tmp_path):
    sd = tmp_path / ".claude" / "ecw" / "session-data"
    old = sd / "20260425-0900"
    new = sd / "20260427-1430"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (new / "session-state.md").write_text("new")
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is not None
    assert store.workflow_id == "20260427-1430"


def test_from_latest_workflow_returns_none_when_no_session_data(marker_module, tmp_path):
    """No session-data directory at all → None."""
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is None


def test_from_latest_workflow_legacy_root_files(marker_module, tmp_path):
    """No subdirectories but root .md files → fallback store with workflow_id=''."""
    sd = tmp_path / ".claude" / "ecw" / "session-data"
    sd.mkdir(parents=True)
    (sd / "requirements-summary.md").write_text("req")
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is not None
    assert store.workflow_id == ""
    assert "requirements-summary" in store.list()


def test_list_returns_paths(marker_module, project):
    wf_dir = project / ".claude" / "ecw" / "session-data" / "20260427-1430"
    (wf_dir / "session-state.md").write_text("s")
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    paths = store.list(return_paths=True)
    assert any("session-state.md" in p for p in paths)


# ── CheckpointStore: additional cases ──

def test_get_checkpoint_files_no_session_data(marker_module, tmp_path):
    """CheckpointStore.from_latest_workflow returns None when session-data absent."""
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is None


def test_get_checkpoint_files_with_subdir(marker_module, tmp_path):
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "session-state.md").write_text("state")
    (wf / "phase2-assessment.md").write_text("p2")
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is not None
    paths = store.list(return_paths=True)
    assert len(paths) == 2


# ── check_impl_verify_convergence: cross-workflow search + status detection tests ──

@pytest.fixture
def verify_module():
    return _load_module("verify_completion", "verify-completion.py")


def test_check_impl_verify_convergence_finds_in_older_workflow(verify_module, tmp_path):
    """check_impl_verify_convergence must search ALL workflow subdirs, not just the latest."""
    old_wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260425-0900"
    new_wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    old_wf.mkdir(parents=True)
    new_wf.mkdir(parents=True)
    # findings exist only in the OLDER workflow dir, no unresolved must-fix rows
    (old_wf / "impl-verify-findings.md").write_text("findings — all clear")
    assert verify_module.check_impl_verify_convergence(str(tmp_path)) == "pass"


def test_check_impl_verify_convergence_not_run_when_absent(verify_module, tmp_path):
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "session-state.md").write_text("state")
    assert verify_module.check_impl_verify_convergence(str(tmp_path)) == "not-run"


def test_check_impl_verify_convergence_has_must_fix(verify_module, tmp_path):
    """Returns 'has-must-fix' when findings table has a row with must-fix and no [FIXED]."""
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "impl-verify-findings.md").write_text(
        "| # | Type | Location | Severity |\n"
        "| 1 | State machine gap | Foo.java:42 | must-fix |\n"
    )
    assert verify_module.check_impl_verify_convergence(str(tmp_path)) == "has-must-fix"


def test_check_impl_verify_convergence_pass_when_all_fixed(verify_module, tmp_path):
    """Returns 'pass' when all must-fix rows are marked [FIXED]."""
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "impl-verify-findings.md").write_text(
        "| # | Type | Location | Severity |\n"
        "| 1 | [FIXED] State machine gap | Foo.java:42 | must-fix |\n"
    )
    assert verify_module.check_impl_verify_convergence(str(tmp_path)) == "pass"


def test_check_impl_verify_skill_gate_blocks(verify_module, tmp_path):
    """check() blocks Skill(ecw:biz-impact-analysis) when findings have unresolved must-fix."""
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "impl-verify-findings.md").write_text(
        "| 1 | Missing validation | Bar.java:10 | must-fix |\n"
    )
    input_data = {
        "cwd": str(tmp_path),
        "tool_name": "Skill",
        "tool_input": {"skill": "ecw:biz-impact-analysis"},
    }
    action, _ = verify_module.check(input_data)
    assert action == "block"


def test_check_impl_verify_skill_gate_passes_when_clean(verify_module, tmp_path):
    """check() allows Skill(ecw:biz-impact-analysis) when findings show no unresolved items."""
    wf = tmp_path / ".claude" / "ecw" / "session-data" / "20260427-1430"
    wf.mkdir(parents=True)
    (wf / "impl-verify-findings.md").write_text(
        "| 1 | [FIXED] Missing validation | Bar.java:10 | must-fix |\n"
    )
    input_data = {
        "cwd": str(tmp_path),
        "tool_name": "Skill",
        "tool_input": {"skill": "ecw:biz-impact-analysis"},
    }
    action, _ = verify_module.check(input_data)
    assert action == "continue"
