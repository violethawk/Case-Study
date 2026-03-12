"""Tests for the engine module – stage specs, session flow, and helpers."""

import pytest

from case_study.engine import (
    STAGES,
    STAGE_NAMES,
    _SINGLE_FIELDS,
    _MULTI_FIELDS,
    _is_stage_complete,
    run_session,
    print_session,
    _clear_stage,
    choose_case,
)
from case_study.session import Session


# ---------------------------------------------------------------------------
# Stage spec consistency
# ---------------------------------------------------------------------------

def test_stage_names_match_session_fields():
    """Every stage name must correspond to a Session dataclass field."""
    sess = Session(case_id="x", timestamp="t")
    for name in STAGE_NAMES:
        assert hasattr(sess, name), f"Session missing field: {name}"


def test_single_and_multi_fields_are_disjoint():
    assert _SINGLE_FIELDS & _MULTI_FIELDS == set()


def test_all_stages_classified():
    assert _SINGLE_FIELDS | _MULTI_FIELDS == set(STAGE_NAMES)


def test_multi_stages_have_item_name():
    for spec in STAGES:
        if spec.multi:
            assert spec.item_name, f"{spec.name} is multi but has no item_name"


# ---------------------------------------------------------------------------
# _is_stage_complete
# ---------------------------------------------------------------------------

def test_stage_complete_with_string():
    assert _is_stage_complete("some text") is True


def test_stage_complete_with_none():
    assert _is_stage_complete(None) is False


def test_stage_complete_with_empty_string():
    assert _is_stage_complete("") is False


def test_stage_complete_with_empty_list():
    assert _is_stage_complete([]) is False


def test_stage_complete_with_populated_list():
    assert _is_stage_complete(["item"]) is True


# ---------------------------------------------------------------------------
# choose_case
# ---------------------------------------------------------------------------

def test_choose_case_empty_list(capsys):
    result = choose_case([])
    assert result is None
    assert "No cases available" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# _clear_stage
# ---------------------------------------------------------------------------

def test_clear_single_field():
    sess = Session(case_id="x", timestamp="t", frame="some frame")
    _clear_stage(sess, "frame")
    assert sess.frame is None


def test_clear_multi_field():
    sess = Session(case_id="x", timestamp="t", hypotheses=["h1", "h2"])
    _clear_stage(sess, "hypotheses")
    assert sess.hypotheses == []


# ---------------------------------------------------------------------------
# print_session
# ---------------------------------------------------------------------------

def test_print_session_empty(capsys):
    sess = Session(case_id="test", timestamp="2026-01-01_00-00-00")
    print_session(sess)
    out = capsys.readouterr().out
    assert "Case ID: test" in out
    assert "Timestamp: 2026-01-01_00-00-00" in out
    # No stage headers when everything is empty
    assert "RESTATEMENT:" not in out


def test_print_session_populated(capsys):
    sess = Session(
        case_id="test",
        timestamp="2026-01-01_00-00-00",
        restatement="My restatement",
        frame="My frame",
        assumptions=["a1", "a2"],
        hypotheses=["h1"],
        analyses=["an1"],
        updates=["u1"],
        conclusion="My conclusion",
        additional_insights="Extra thoughts",
    )
    print_session(sess)
    out = capsys.readouterr().out
    assert "RESTATEMENT:" in out
    assert "My restatement" in out
    assert "FRAME:" in out
    assert "ASSUMPTIONS:" in out
    assert "1. a1" in out
    assert "2. a2" in out
    assert "CONCLUSION:" in out
    assert "ADDITIONAL INSIGHTS:" in out
    assert "Extra thoughts" in out


# ---------------------------------------------------------------------------
# run_session – integration with mocked input
# ---------------------------------------------------------------------------

def test_run_session_already_complete(capsys):
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        hypotheses=["h"], analyses=["an"], updates=["u"],
        conclusion="c", additional_insights="ai",
    )
    run_session(sess, coach_enabled=False)
    assert "already complete" in capsys.readouterr().out


def test_run_session_single_stage(monkeypatch, tmp_path, capsys):
    """Run a session that only needs the last stage (additional_insights)."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        hypotheses=["h"], analyses=["an"], updates=["u"],
        conclusion="c",
    )
    # Mock save to use tmp_path and mock input for additional_insights
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)
    inputs = iter(["These are my additional insights about the case"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.additional_insights == "These are my additional insights about the case"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_multi_stage(monkeypatch, tmp_path, capsys):
    """Run a session that needs hypotheses (multi) stage onward."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    # Inputs: hypothesis text, "n" (no more), analysis text, "n", update text, "n",
    # conclusion text, additional_insights text
    inputs = iter([
        "Market demand is growing",    # hypothesis 1
        "n",                            # no more hypotheses
        "Revenue analysis needed",      # analysis 1
        "n",                            # no more analyses
        "Hypothesis confirmed",         # update 1
        "n",                            # no more updates
        "Recommend expansion",          # conclusion
        "Watch for regulatory changes", # additional insights
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.hypotheses == ["Market demand is growing"]
    assert sess.analyses == ["Revenue analysis needed"]
    assert sess.updates == ["Hypothesis confirmed"]
    assert sess.conclusion == "Recommend expansion"
    assert sess.additional_insights == "Watch for regulatory changes"


def test_run_session_with_coach(monkeypatch, tmp_path, capsys):
    """Coach feedback is printed when enabled and user opts in."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        hypotheses=["h"], analyses=["an"], updates=["u"],
        conclusion="c",
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "These are my additional insights about the case",
        "y",  # yes to coach feedback
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=True)

    out = capsys.readouterr().out
    assert "STRENGTHS:" in out
    assert "GAPS:" in out
    assert "SUGGESTED QUESTIONS:" in out
