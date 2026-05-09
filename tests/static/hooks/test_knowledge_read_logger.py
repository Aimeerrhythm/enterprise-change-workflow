"""Unit tests for hooks/knowledge-read-logger.py

Tests the PostToolUse(Read) hook that auto-logs knowledge file reads to
session-data/{workflow-id}/knowledge-reads.jsonl.

Key behaviors:
- Knowledge files (under knowledge_root) → appended to knowledge-reads.jsonl
- Non-knowledge files → skipped (fast path, no file I/O)
- No active session-state.md → skipped
- No ecw.yml → defaults to .claude/knowledge/
- Cross-session append → records accumulate in same file
- Output is always {"result": "continue"} (never blocks)
"""
from __future__ import annotations

import importlib.util
import json
import os
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "hooks"


@pytest.fixture
def knowledge_logger():
    """Import knowledge-read-logger.py as a module."""
    spec = importlib.util.spec_from_file_location(
        "knowledge_read_logger",
        HOOKS_DIR / "knowledge-read-logger.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def project(tmp_path):
    """Minimal ECW project with knowledge_root configured."""
    ecw_dir = tmp_path / ".claude" / "ecw"
    ecw_dir.mkdir(parents=True)
    (ecw_dir / "ecw.yml").write_text(
        "project:\n  name: test\n"
        "paths:\n  knowledge_root: .claude/knowledge/\n",
        encoding="utf-8",
    )
    session_dir = ecw_dir / "session-data" / "20260505-test"
    session_dir.mkdir(parents=True)
    (session_dir / "session-state.json").write_text(
        json.dumps({"risk_level": "P1", "routing": []}),
        encoding="utf-8",
    )
    knowledge_dir = tmp_path / ".claude" / "knowledge" / "common"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "cross-domain-rules.md").write_text("# Rules\n", encoding="utf-8")
    return tmp_path


def _make_read_event(file_path, cwd):
    """Build a PostToolUse(Read) hook stdin payload."""
    return json.dumps({
        "hook_event_name": "PostToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": file_path},
        "cwd": str(cwd),
    })


def _run_main(mod, stdin_str):
    """Run mod.main() with mocked stdin, return stdout as parsed JSON."""
    output_lines = []
    with patch("sys.stdin", StringIO(stdin_str)), \
         patch("sys.stdout") as mock_stdout:
        mock_stdout.write = lambda s: output_lines.append(s)
        try:
            mod.main()
        except SystemExit:
            pass
    # Extract what was printed
    output = "".join(output_lines)
    if not output:
        return None
    return json.loads(output)


# ══════════════════════════════════════════════════════
# Fast Path — Non-Knowledge Files
# ══════════════════════════════════════════════════════

class TestFastPath:
    """Non-knowledge file reads must be skipped without any file I/O."""

    def test_source_code_file_skipped(self, knowledge_logger, project, tmp_path):
        src_file = str(tmp_path / "src" / "Main.java")
        stdin = _make_read_event(src_file, tmp_path)
        result = knowledge_logger._should_log(
            file_path=src_file,
            cwd=str(tmp_path),
            knowledge_abs=str(tmp_path / ".claude" / "knowledge") + os.sep,
        )
        assert result is False

    def test_knowledge_file_not_skipped(self, knowledge_logger, project, tmp_path):
        kf = str(tmp_path / ".claude" / "knowledge" / "common" / "cross-domain-rules.md")
        result = knowledge_logger._should_log(
            file_path=kf,
            cwd=str(tmp_path),
            knowledge_abs=str(tmp_path / ".claude" / "knowledge") + os.sep,
        )
        assert result is True

    def test_no_knowledge_substring_exits_early(self, knowledge_logger, project, tmp_path):
        """Path without '/knowledge/' at all should be false immediately."""
        result = knowledge_logger._should_log(
            file_path="/some/other/src/Main.java",
            cwd=str(tmp_path),
            knowledge_abs=str(tmp_path / ".claude" / "knowledge") + os.sep,
        )
        assert result is False


# ══════════════════════════════════════════════════════
# JSONL Record Writing
# ══════════════════════════════════════════════════════

class TestRecordWriting:
    """When a knowledge file is read, a JSONL record is appended."""

    def test_jsonl_record_written(self, knowledge_logger, project):
        kf = str(project / ".claude" / "knowledge" / "common" / "cross-domain-rules.md")
        stdin = _make_read_event(kf, project)
        with patch("sys.stdin", StringIO(stdin)), patch("sys.stdout"):
            knowledge_logger.main()
        log_file = project / ".claude" / "ecw" / "session-data" / "20260505-test" / "knowledge-reads.jsonl"
        assert log_file.exists(), "knowledge-reads.jsonl must be created"
        line = log_file.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert "ts" in record
        assert "file" in record
        assert record["file"].endswith("cross-domain-rules.md")

    def test_record_has_relative_path(self, knowledge_logger, project):
        kf = str(project / ".claude" / "knowledge" / "common" / "cross-domain-rules.md")
        stdin = _make_read_event(kf, project)
        with patch("sys.stdin", StringIO(stdin)), patch("sys.stdout"):
            knowledge_logger.main()
        log_file = project / ".claude" / "ecw" / "session-data" / "20260505-test" / "knowledge-reads.jsonl"
        record = json.loads(log_file.read_text(encoding="utf-8").strip())
        # Should be relative to cwd, not absolute
        assert not record["file"].startswith("/"), "file path must be relative"

    def test_always_outputs_continue(self, knowledge_logger, project, capsys):
        kf = str(project / ".claude" / "knowledge" / "common" / "cross-domain-rules.md")
        stdin = _make_read_event(kf, project)
        with patch("sys.stdin", StringIO(stdin)):
            knowledge_logger.main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result == {"result": "continue"}

    def test_cross_session_append(self, knowledge_logger, project):
        """Two main() calls append to same file, not overwrite."""
        kf = str(project / ".claude" / "knowledge" / "common" / "cross-domain-rules.md")
        for _ in range(2):
            stdin = _make_read_event(kf, project)
            with patch("sys.stdin", StringIO(stdin)), patch("sys.stdout"):
                knowledge_logger.main()
        log_file = project / ".claude" / "ecw" / "session-data" / "20260505-test" / "knowledge-reads.jsonl"
        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(lines) == 2, "Each read must produce a separate JSONL line"


# ══════════════════════════════════════════════════════
# Missing Session State
# ══════════════════════════════════════════════════════

class TestNoSession:
    """When there's no active session-state.md, hook must silently skip."""

    def test_no_session_dir(self, knowledge_logger, tmp_path):
        """No .claude/ecw/session-data → skip without error."""
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        (ecw_dir / "ecw.yml").write_text(
            "project:\n  name: test\n"
            "paths:\n  knowledge_root: .claude/knowledge/\n",
            encoding="utf-8",
        )
        kf = str(tmp_path / ".claude" / "knowledge" / "rules.md")
        Path(kf).parent.mkdir(parents=True)
        Path(kf).write_text("# rules\n", encoding="utf-8")
        stdin = _make_read_event(kf, tmp_path)
        with patch("sys.stdin", StringIO(stdin)):
            knowledge_logger.main()
        # No JSONL file should be created
        session_data = tmp_path / ".claude" / "ecw" / "session-data"
        assert not any(session_data.rglob("knowledge-reads.jsonl")) if session_data.exists() else True

    def test_no_session_still_outputs_continue(self, knowledge_logger, tmp_path, capsys):
        ecw_dir = tmp_path / ".claude" / "ecw"
        ecw_dir.mkdir(parents=True)
        (ecw_dir / "ecw.yml").write_text(
            "project:\n  name: test\n"
            "paths:\n  knowledge_root: .claude/knowledge/\n",
            encoding="utf-8",
        )
        kf = str(tmp_path / ".claude" / "knowledge" / "rules.md")
        Path(kf).parent.mkdir(parents=True)
        Path(kf).write_text("# rules\n", encoding="utf-8")
        stdin = _make_read_event(kf, tmp_path)
        with patch("sys.stdin", StringIO(stdin)):
            knowledge_logger.main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result == {"result": "continue"}


# ══════════════════════════════════════════════════════
# Default knowledge_root (no ecw.yml)
# ══════════════════════════════════════════════════════

class TestDefaultKnowledgeRoot:
    """When ecw.yml is absent, default to .claude/knowledge/."""

    def test_default_root_used_when_no_ecw_yml(self, knowledge_logger, tmp_path):
        """No ecw.yml → still detect knowledge files under .claude/knowledge/."""
        session_dir = tmp_path / ".claude" / "ecw" / "session-data" / "20260505-default"
        session_dir.mkdir(parents=True)
        (session_dir / "session-state.json").write_text('{"risk_level": "P1"}', encoding="utf-8")
        kf = str(tmp_path / ".claude" / "knowledge" / "rules.md")
        Path(kf).parent.mkdir(parents=True)
        Path(kf).write_text("# rules\n", encoding="utf-8")
        stdin = _make_read_event(kf, tmp_path)
        with patch("sys.stdin", StringIO(stdin)), patch("sys.stdout"):
            knowledge_logger.main()
        log_file = session_dir / "knowledge-reads.jsonl"
        assert log_file.exists()


# ══════════════════════════════════════════════════════
# Invalid / Malformed Input
# ══════════════════════════════════════════════════════

class TestMalformedInput:
    """Hook must never crash or block on bad input."""

    def test_empty_stdin(self, knowledge_logger, capsys):
        with patch("sys.stdin", StringIO("{}")):
            knowledge_logger.main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result == {"result": "continue"}

    def test_missing_file_path(self, knowledge_logger, capsys):
        stdin = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Read", "cwd": "/tmp"})
        with patch("sys.stdin", StringIO(stdin)):
            knowledge_logger.main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result == {"result": "continue"}

    def test_wrong_tool_name(self, knowledge_logger, capsys):
        stdin = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "/some/knowledge/file.md"},
            "cwd": "/tmp",
        })
        with patch("sys.stdin", StringIO(stdin)):
            knowledge_logger.main()
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result == {"result": "continue"}
