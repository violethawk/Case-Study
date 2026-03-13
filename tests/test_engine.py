"""Tests for the engine module – stage specs, session flow, and helpers."""

import pytest

from case_study.engine import (
    STAGES,
    STAGE_NAMES,
    STAGES_BY_CATEGORY,
    STAGE_TIME_LIMITS,
    TOTAL_CASE_TIME_LIMIT,
    STRATEGY_STAGES,
    MARKET_SIZING_STAGES,
    QUANTITATIVE_STAGES,
    _SINGLE_FIELDS,
    _MULTI_FIELDS,
    _is_stage_complete,
    get_stages_for_category,
    get_stages_with_exhibit,
    get_stage_time_limit,
    format_time_warning,
    check_time_expired,
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
    assert len(STRATEGY_STAGES) == 10


def test_market_sizing_stages_count():
    assert len(MARKET_SIZING_STAGES) == 8


def test_quantitative_stages_count():
    assert len(QUANTITATIVE_STAGES) == 7


def test_strategy_stage_names():
    names = tuple(s.name for s in STRATEGY_STAGES)
    assert names == (
        "restatement", "clarifying_questions", "framework", "frame",
        "assumptions", "hypotheses",
        "equation", "calculation", "conclusion", "additional_insights",
    )


def test_market_sizing_stage_names():
    names = tuple(s.name for s in MARKET_SIZING_STAGES)
    assert names == (
        "restatement", "clarifying_questions", "framework", "structure",
        "assumptions", "calculation", "sanity_check", "conclusion",
    )


def test_quantitative_stage_names():
    names = tuple(s.name for s in QUANTITATIVE_STAGES)
    assert names == (
        "restatement", "clarifying_questions", "setup", "assumptions",
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
        restatement="r", clarifying_questions=["q1", "q2"],
        framework="Profitability", frame="f",
        assumptions=["a"], hypotheses=["h1"],
        equation="Revenue = P * Q", calculation=["step1"],
        conclusion="c", additional_insights="ai",
    )
    run_session(sess, coach_enabled=False)
    assert "already complete" in capsys.readouterr().out


def test_run_session_single_stage(monkeypatch, tmp_path, capsys):
    """Run a session that only needs the last stage (additional_insights)."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", clarifying_questions=["q1", "q2"],
        framework="Profitability", frame="f",
        assumptions=["a"], hypotheses=["h1"],
        equation="Revenue = P * Q", calculation=["step1"],
        conclusion="c",
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)
    inputs = iter(["These are my additional insights about the case"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.additional_insights == "These are my additional insights about the case"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_multi_stage(monkeypatch, tmp_path, capsys):
    """Run a session that needs hypotheses stage onward."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", clarifying_questions=["q1", "q2"],
        framework="Profitability", frame="f",
        assumptions=["a"],
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Revenue decline is driven by pricing pressure",  # hypothesis 1
        "n",                                               # no more hypotheses
        "Revenue = Price * Volume",                        # equation
        "Price = $50, Volume = 10K, Revenue = $500K",      # calculation step 1
        "n",                                               # no more calc steps
        "Recommend expansion",                             # conclusion
        "Watch for regulatory changes",                    # additional insights
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.hypotheses == ["Revenue decline is driven by pricing pressure"]
    assert sess.equation == "Revenue = Price * Volume"
    assert sess.calculation == ["Price = $50, Volume = 10K, Revenue = $500K"]
    assert sess.conclusion == "Recommend expansion"
    assert sess.additional_insights == "Watch for regulatory changes"


def test_run_session_market_sizing(monkeypatch, tmp_path, capsys):
    """Run a market-sizing session through all 8 stages."""
    sess = Session(case_id="x", timestamp="t", category="market-sizing")
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Estimate number of coffee shops in the US",       # restatement
        "What is the geographic scope of this estimate",   # clarifying q 1
        "n",                                                # no more questions
        "n",                                                # no frameworks
        "Supply and Demand framework for market sizing",   # framework
        "Top-down from population",                        # structure
        "US population 330M",                              # assumption 1
        "n",                                                # no more assumptions
        "330M / 300 = 1.1M",                               # calculation step 1
        "n",                                                # no more steps
        "1.1M seems high, Starbucks has 16K alone",       # sanity check
        "About 200K coffee shops in the US",               # conclusion
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.restatement == "Estimate number of coffee shops in the US"
    assert sess.clarifying_questions == ["What is the geographic scope of this estimate"]
    assert sess.framework == "Supply and Demand framework for market sizing"
    assert sess.structure == "Top-down from population"
    assert sess.calculation == ["330M / 300 = 1.1M"]
    assert sess.sanity_check == "1.1M seems high, Starbucks has 16K alone"
    assert sess.conclusion == "About 200K coffee shops in the US"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_quantitative(monkeypatch, tmp_path, capsys):
    """Run a quantitative session through all 7 stages."""
    sess = Session(case_id="x", timestamp="t", category="quantitative")
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Calculate break-even price for the new product",       # restatement
        "What is the target production volume for year one",    # clarifying q 1
        "n",                                                     # no more questions
        "Break-even = Fixed Costs / (Price - Variable Cost)",   # setup
        "Fixed costs are $500K per year",                       # assumption 1
        "n",                                                     # no more assumptions
        "500K / (P - 20) = 10K units, so P = $70",             # calculation step 1
        "n",                                                     # no more steps
        "If variable cost rises 25%, price needs to be $75",   # sensitivity
        "Set price at $70 with $5 buffer for cost increases",  # conclusion
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=False)

    assert sess.clarifying_questions == ["What is the target production volume for year one"]
    assert sess.setup == "Break-even = Fixed Costs / (Price - Variable Cost)"
    assert sess.sensitivity == "If variable cost rises 25%, price needs to be $75"
    assert "Session complete" in capsys.readouterr().out


def test_run_session_with_coach(monkeypatch, tmp_path, capsys):
    """Coach feedback is printed when enabled and user opts in."""
    sess = Session(
        case_id="x", timestamp="t",
        restatement="r", clarifying_questions=["q1", "q2"],
        framework="Profitability", frame="f",
        assumptions=["a"], hypotheses=["h1"],
        equation="Revenue = P * Q", calculation=["step1"],
        conclusion="c",
    )
    monkeypatch.setattr(sess, "save", lambda directory=tmp_path: None)

    inputs = iter([
        "Key risks include regulatory changes that could delay implementation. Competitors may respond with aggressive pricing, and the client should monitor market share monthly to track impact.",
        "y",  # yes to coach feedback
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

    run_session(sess, coach_enabled=True)

    out = capsys.readouterr().out
    assert "STRENGTHS:" in out
    assert "GAPS:" in out
    assert "SUGGESTED QUESTIONS:" in out


# ---------------------------------------------------------------------------
# Time limits
# ---------------------------------------------------------------------------

def test_all_stages_have_time_limits():
    """Every stage in every category should have a time limit entry."""
    for category, stages in STAGES_BY_CATEGORY.items():
        for spec in stages:
            limit = get_stage_time_limit(category, spec.name)
            assert limit > 0, f"Missing time limit for {category}/{spec.name}"


def test_format_time_warning_under_target():
    assert format_time_warning(100, 120) is None


def test_format_time_warning_over_target():
    warning = format_time_warning(150, 120)
    assert warning is not None
    assert "NOTE" in warning


def test_format_time_warning_well_over_target():
    warning = format_time_warning(300, 120)
    assert warning is not None
    assert "WARNING" in warning


# ---------------------------------------------------------------------------
# Exhibit insertion
# ---------------------------------------------------------------------------

def test_get_stages_with_exhibit_no_exhibit():
    """Without exhibit data, stages should be unchanged."""
    stages = get_stages_with_exhibit("strategy", None)
    assert stages == STRATEGY_STAGES


def test_get_stages_with_exhibit():
    """With an exhibit, the exhibit_interpretation stage is inserted."""
    case_data = {
        "exhibit": {"title": "Test", "data": "x", "appears_after": "frame"},
    }
    stages = get_stages_with_exhibit("strategy", case_data)
    names = tuple(s.name for s in stages)
    frame_idx = names.index("frame")
    assert names[frame_idx + 1] == "exhibit_interpretation"
    assert len(stages) == len(STRATEGY_STAGES) + 1


# ---------------------------------------------------------------------------
# Time expiry
# ---------------------------------------------------------------------------

def test_check_time_expired_advanced():
    sess = Session(case_id="x", timestamp="t")
    sess.stage_times = {"restatement": 800, "framework": 800}
    assert check_time_expired(sess, "advanced") is True


def test_check_time_expired_not_advanced():
    sess = Session(case_id="x", timestamp="t")
    sess.stage_times = {"restatement": 800, "framework": 800}
    assert check_time_expired(sess, "intermediate") is False


def test_check_time_expired_under_limit():
    sess = Session(case_id="x", timestamp="t")
    sess.stage_times = {"restatement": 100}
    assert check_time_expired(sess, "advanced") is False


def test_total_case_time_limit_exists():
    for category in STAGES_BY_CATEGORY:
        assert category in TOTAL_CASE_TIME_LIMIT
