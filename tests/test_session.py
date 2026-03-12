import json
from pathlib import Path

import pytest

from case_study.session import Session, list_sessions


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


def test_new_session_defaults_are_empty():
    session = Session.new("test")
    assert session.category == "strategy"
    assert session.restatement is None
    assert session.framework is None
    assert session.frame is None
    assert session.assumptions == []
    assert session.equation is None
    assert session.hypotheses == []
    assert session.analyses == []
    assert session.updates == []
    assert session.conclusion is None
    assert session.additional_insights is None
    assert session.structure is None
    assert session.setup is None
    assert session.calculation == []
    assert session.sanity_check is None
    assert session.sensitivity is None
    assert session.stage_times == {}
    assert session.total_time_seconds == 0.0
    assert session.completed_at is None
    assert session.stage_attempts == {}
    assert session.difficulty is None
    assert session.coach_enabled is False


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        Session.load("/nonexistent/path/file.json")


def test_load_backwards_compatible(tmp_path):
    """Loading a JSON without the newer fields should still work."""
    data = {"case_id": "old", "timestamp": "2025-01-01_00-00-00", "frame": "f"}
    path = tmp_path / "old.json"
    path.write_text(json.dumps(data))
    sess = Session.load(path)
    assert sess.case_id == "old"
    assert sess.frame == "f"
    assert sess.restatement is None
    assert sess.framework is None
    assert sess.assumptions == []
    assert sess.additional_insights is None
    assert sess.category == "strategy"
    assert sess.structure is None
    assert sess.calculation == []
    assert sess.stage_times == {}
    assert sess.completed_at is None


def test_session_timestamp_is_local():
    """Timestamp should not be UTC-specific; just check format."""
    import re
    sess = Session.new("tz_test")
    assert re.match(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", sess.timestamp)


def test_list_sessions_returns_json_only(tmp_path):
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.txt").write_text("not json")
    (tmp_path / "c.json").write_text("{}")
    result = list_sessions(tmp_path)
    assert len(result) == 2
    assert all(p.suffix == ".json" for p in result)


def test_list_sessions_creates_directory(tmp_path):
    target = tmp_path / "new_dir"
    assert not target.exists()
    result = list_sessions(target)
    assert target.exists()
    assert result == []


def test_new_session_with_category():
    sess = Session.new("sizing_case", category="market-sizing")
    assert sess.category == "market-sizing"
    assert sess.case_id == "sizing_case"


def test_market_sizing_session_round_trip(tmp_path):
    sess = Session(
        case_id="coffee",
        timestamp="2026-01-01_00-00-00",
        category="market-sizing",
        restatement="Estimate coffee shops",
        structure="Top-down from population",
        assumptions=["330M US population"],
        calculation=["330M / 1000 = 330K", "Adjust for density: 200K"],
        sanity_check="Reasonable vs known data",
        conclusion="About 200K",
    )
    sess.save(tmp_path)
    loaded = Session.load(tmp_path / sess.filename)
    assert loaded.category == "market-sizing"
    assert loaded.structure == "Top-down from population"
    assert loaded.calculation == ["330M / 1000 = 330K", "Adjust for density: 200K"]
    assert loaded.sanity_check == "Reasonable vs known data"
    # Strategy-only fields should be empty
    assert loaded.frame is None
    assert loaded.hypotheses == []


def test_save_overwrite(tmp_path):
    """Saving the same session twice should overwrite the file."""
    sess = Session(case_id="x", timestamp="2026-01-01_00-00-00")
    sess.save(tmp_path)
    sess.frame = "updated"
    sess.save(tmp_path)
    loaded = Session.load(tmp_path / sess.filename)
    assert loaded.frame == "updated"
