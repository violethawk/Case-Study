"""Tests for the CLI argument parsing and dispatch."""

import io
import sys
from unittest.mock import patch

import pytest

from case_study.cli import main


def test_start_dispatches_to_engine(monkeypatch):
    """start subcommand calls engine.start_session with correct coach flag."""
    calls = []
    monkeypatch.setattr(
        "case_study.cli.engine.start_session",
        lambda coach_flag: calls.append(("start", coach_flag)),
    )
    main(["start"])
    assert calls == [("start", None)]


def test_start_with_coach_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "case_study.cli.engine.start_session",
        lambda coach_flag: calls.append(("start", coach_flag)),
    )
    main(["start", "--coach"])
    assert calls == [("start", True)]


def test_resume_dispatches_to_engine(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "case_study.cli.engine.resume_session",
        lambda sf, cf: calls.append(("resume", sf, cf)),
    )
    main(["resume", "sessions/test.json"])
    assert calls == [("resume", "sessions/test.json", None)]


def test_resume_with_coach_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "case_study.cli.engine.resume_session",
        lambda sf, cf: calls.append(("resume", sf, cf)),
    )
    main(["resume", "--coach", "sessions/test.json"])
    assert calls == [("resume", "sessions/test.json", True)]


def test_list_no_sessions(monkeypatch, capsys):
    monkeypatch.setattr("case_study.cli.list_sessions", lambda: [])
    main(["list"])
    assert "No sessions found" in capsys.readouterr().out


def test_list_with_sessions(monkeypatch, capsys):
    from pathlib import Path

    monkeypatch.setattr(
        "case_study.cli.list_sessions",
        lambda: [Path("sessions/a.json"), Path("sessions/b.json")],
    )
    main(["list"])
    out = capsys.readouterr().out
    assert "a.json" in out
    assert "b.json" in out


def test_missing_subcommand():
    with pytest.raises(SystemExit):
        main([])
