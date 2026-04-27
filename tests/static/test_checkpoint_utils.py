"""Unit tests for CheckpointStore in hooks/marker_utils.py"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "hooks"


@pytest.fixture
def marker_module():
    spec = importlib.util.spec_from_file_location(
        "marker_utils", HOOKS_DIR / "marker_utils.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    store = marker_module.CheckpointStore.from_latest_workflow(str(tmp_path))
    assert store is None


def test_list_returns_paths(marker_module, project):
    wf_dir = project / ".claude" / "ecw" / "session-data" / "20260427-1430"
    (wf_dir / "session-state.md").write_text("s")
    store = marker_module.CheckpointStore(str(project), "20260427-1430")
    paths = store.list(return_paths=True)
    assert any("session-state.md" in p for p in paths)


# ── Integration: functions that now delegate to CheckpointStore ──

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
