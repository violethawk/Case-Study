"""Tests for the engine module – stage specs, session flow, and helpers."""

import pytest

from case_study.engine import (
    STAGES,
    STAGE_NAMES,
    STAGES_BY_CATEGORY,
    STRATEGY_STAGES,
    MARKET_SIZING_STAGES,
    QUANTITATIVE_STAGES,
    _SINGLE_FIELDS,
    _MULTI_FIELDS,
    _is_stage_complete,
    get_stages_for_category,
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
    """Every stage name across all categories must correspond to a Session field."""
    sess = Session(case_id="x", timestamp="t")
    all_names = {s.name for stages in STAGES_BY_CATEGORY.values() for s in stages}
    for name in all_names:
        assert hasattr(sess, name), f"Session missing field: {name}"


def test_single_and_multi_fields_are_disjoint():
    assert _SINGLE_FIELDS & _MULTI_FIELDS == set()


def test_all_stages_classified():
    all_names = {s.name for stages in STAGES_BY_CATEGORY.values() for s in stages}
    assert _SINGLE_FIELDS | _MULTI_FIELDS == all_names


def test_multi_stages_have_item_name():
    for stages in STAGES_BY_CATEGORY.values():
        for spec in stages:
            if spec.multi:
                assert spec.item_name, f"{spec.name} is multi but has no item_name"


def test_strategy_stages_count():
    assert len(STRATEGY_STAGES) == 7


def test_market_sizing_stages_count():
    assert len(MARKET_SIZING_STAGES) == 6


def test_quantitative_stages_count():
    assert len(QUANTITATIVE_STAGES) == 6


def test_strategy_stage_names():
    names = tuple(s.name for s in STRATEGY_STAGES)
    assert names == (
        "restatement", "frame", "assumptions", "equation",
        "calculation", "conclusion", "additional_insights",
    )


def test_market_sizing_stage_names():
    names = tuple(s.name for s in MARKET_SIZING_STAGES)
    assert names == (
        "restatement", "structure", "assumptions",
        "calculation", "sanity_check", "conclusion",
    )


def test_quantitative_stage_names():
    names = tuple(s.name for s in QUANTITATIVE_STAGES)
    assert names == (
        "restatement", "setup", "assumptions",
        "calculation", "sensitivity", "conclusion",
    )


def test_get_stages_for_category_defaults_to_strategy():
    assert get_stages_for_category("unknown") is STRATEGY_STAGES


def test_get_stages_for_category():
    assert get_stages_for_category("strategy") is STRATEGY_STAGES
    assert get_stages_for_category("market-sizing") is MARKET_SIZING_STAGES
    assert get_stages_for_category("quantitative") is QUANTITATIVE_STAGES


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
    sess = Session(case_id="x", timestamp="t", assumptions=["a1", "a2"])
    _clear_stage(sess, "assumptions")
    assert sess.assumptions == []


def test_clear_new_single_field():
    sess = Session(case_id="x", timestamp="t", structure="top-down approach")
    _clear_stage(sess, "structure")
    assert sess.structure is None


def test_clear_new_multi_field():
    sess = Session(case_id="x", timestamp="t", calculation=["step 1", "step 2"])
    _clear_stage(sess, "calculation")
    assert sess.calculation == []


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
        equation="Revenue = P * Q",
        calculation=["step1", "step2"],
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
    assert "EQUATION:" in out
    assert "CALCULATION:" in out
    assert "CONCLUSION:" in out
    assert "ADDITIONAL INSIGHTS:" in out
    assert "Extra thoughts" in out


def test_print_session_market_sizing(capsys):
    sess = Session(
        case_id="test",
        timestamp="2026-01-01_00-00-00",
        category="market-sizing",
        restatement="Estimate X",
        structure="Top-down approach",
        assumptions=["a1"],
        calculation=["step 1", "step 2"],
        sanity_check="Looks reasonable",
        conclusion="About 1M",
    )
    print_session(sess)
    out = capsys.readouterr().out
    assert "STRUCTURE:" in out
    assert "CALCULATION:" in out
    assert "SANITY CHECK:" in out
    # Should NOT contain strategy-only stages
    assert "FRAME:" not in out
    assert "HYPOTHESES:" not in out


# ---------------------------------------------------------------------------
# run_session – integration with mocked input
# ---------------------------------------------------------------------------

def test_run_session_already_complete(capsys):
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        equation="Revenue = P * Q", calculation=["step1"],
        conclusion="c", additional_insights="ai",
    )
    run_session(sess, coach_enabled=False)
    assert "already complete" in capsys.readouterr().out


def test_run_session_single_stage(monkeypatch, tmp_path, capsys):
    """Run a session that only needs the last stage (additional_insights)."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        equation="Revenue = P * Q", calculation=["step1"],
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
    """Run a session that needs equation stage onward."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Revenue = Price * Volume",                    # equation
        "Price = $50, Volume = 10K, Revenue = $500K",  # calculation step 1
        "n",                                            # no more calc steps
        "Recommend expansion",                          # conclusion
        "Watch for regulatory changes",                 # additional insights
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.equation == "Revenue = Price * Volume"
    assert sess.calculation == ["Price = $50, Volume = 10K, Revenue = $500K"]
    assert sess.conclusion == "Recommend expansion"
    assert sess.additional_insights == "Watch for regulatory changes"


def test_run_session_market_sizing(monkeypatch, tmp_path, capsys):
    """Run a market-sizing session through all 6 stages."""
    sess = Session(case_id="x", timestamp="t", category="market-sizing")
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Estimate number of coffee shops in the US",  # restatement
        "n",                                            # no frameworks
        "Top-down from population",                    # structure
        "US population 330M",                          # assumption 1
        "n",                                            # no more assumptions
        "330M / 300 = 1.1M",                           # calculation step 1
        "n",                                            # no more steps
        "1.1M seems high, Starbucks has 16K alone",   # sanity check
        "About 200K coffee shops in the US",           # conclusion
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.restatement == "Estimate number of coffee shops in the US"
    assert sess.structure == "Top-down from population"
    assert sess.calculation == ["330M / 300 = 1.1M"]
    assert sess.sanity_check == "1.1M seems high, Starbucks has 16K alone"
    assert sess.conclusion == "About 200K coffee shops in the US"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_quantitative(monkeypatch, tmp_path, capsys):
    """Run a quantitative session through all 6 stages."""
    sess = Session(case_id="x", timestamp="t", category="quantitative")
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Calculate break-even price for the new product",  # restatement
        "Break-even = Fixed Costs / (Price - Variable Cost)",  # setup
        "Fixed costs are $500K per year",                   # assumption 1
        "n",                                                 # no more assumptions
        "500K / (P - 20) = 10K units, so P = $70",         # calculation step 1
        "n",                                                 # no more steps
        "If variable cost rises 25%, price needs to be $75", # sensitivity
        "Set price at $70 with $5 buffer for cost increases", # conclusion
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.setup == "Break-even = Fixed Costs / (Price - Variable Cost)"
    assert sess.sensitivity == "If variable cost rises 25%, price needs to be $75"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_with_coach(monkeypatch, tmp_path, capsys):
    """Coach feedback is printed when enabled and user opts in."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", frame="f", assumptions=["a"],
        equation="Revenue = P * Q", calculation=["step1"],
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
