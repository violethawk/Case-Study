import json
from pathlib import Path

from case_study.session import Session


def test_new_session_has_case_id():
    session = Session.new("test_case")
    assert session.case_id == "test_case"
    assert session.timestamp


def test_session_filename_format():
    session = Session(case_id="abc", timestamp="2026-01-01_12-00-00")
    assert session.filename == "abc_2026-01-01_12-00-00.json"


def test_session_save_and_load(tmp_path):
    session = Session(
        case_id="test",
        timestamp="2026-01-01_00-00-00",
        restatement="Test restatement",
        frame="Test frame",
        assumptions=["assume1", "assume2"],
        hypotheses=["h1", "h2"],
        analyses=["a1"],
        updates=["u1"],
        conclusion="Test conclusion",
        additional_insights="Test insights",
    )
    session.save(tmp_path)

    loaded = Session.load(tmp_path / session.filename)
    assert loaded.case_id == "test"
    assert loaded.restatement == "Test restatement"
    assert loaded.frame == "Test frame"
    assert loaded.assumptions == ["assume1", "assume2"]
    assert loaded.hypotheses == ["h1", "h2"]
    assert loaded.conclusion == "Test conclusion"
    assert loaded.additional_insights == "Test insights"


def test_session_save_creates_directory(tmp_path):
    nested = tmp_path / "sub" / "dir"
    session = Session.new("test")
    session.save(nested)
    assert (nested / session.filename).exists()
