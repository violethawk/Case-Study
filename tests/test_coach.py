from case_study.coach import (
    provide_feedback,
    CoachFeedback,
    is_ai_enabled,
    _check_heuristic_rules,
    generate_probe_question,
    answer_clarifying_questions,
    generate_data_reveal,
    _heuristic_data_reveal,
)


def test_provide_feedback_returns_coach_feedback():
    fb = provide_feedback("frame", "I would use Porter's Five Forces framework to structure the analysis into key competitive areas.")
    assert isinstance(fb, CoachFeedback)
    assert fb.strengths
    assert fb.gaps
    assert fb.questions


def test_feedback_with_list_input():
    fb = provide_feedback("hypotheses", [
        "Revenue decline is driven by pricing pressure from competitors",
        "Volume loss is caused by customers switching to digital alternatives",
    ])
    assert isinstance(fb, CoachFeedback)


def test_format_for_cli():
    fb = CoachFeedback(strengths="Good", gaps="Check X", questions="Why Y?")
    output = fb.format_for_cli()
    assert "STRENGTHS:" in output
    assert "GAPS:" in output
    assert "SUGGESTED QUESTIONS:" in output
    assert "PASSED" in output


def test_format_for_cli_not_passed():
    fb = CoachFeedback(strengths="Good", gaps="Missing X", questions="Why?", passed=False)
    output = fb.format_for_cli()
    assert "NOT YET" in output


def test_is_ai_enabled_without_key():
    assert is_ai_enabled() is False


# ---------------------------------------------------------------------------
# Heuristic rules
# ---------------------------------------------------------------------------

def test_heuristic_passes_good_restatement():
    fb = provide_feedback(
        "restatement",
        "The client is a major bank looking to decide whether to expand into digital banking services."
    )
    assert fb.passed is True


def test_heuristic_fails_too_short():
    fb = provide_feedback("restatement", "The problem is about a bank.")
    assert fb.passed is False


def test_heuristic_fails_missing_keywords_frame():
    fb = provide_feedback(
        "frame",
        "I think we should look at the problem from different perspectives and consider various angles to analyze it thoroughly."
    )
    assert fb.passed is False


def test_heuristic_passes_good_frame():
    fb = provide_feedback(
        "frame",
        "I will structure this problem using the profitability framework, breaking it down into revenue and cost drivers to identify the key areas of concern."
    )
    assert fb.passed is True


def test_heuristic_hypotheses_needs_two_items():
    fb = provide_feedback("hypotheses", ["Revenue is declining due to competitive pricing"])
    assert fb.passed is False


def test_heuristic_hypotheses_passes_with_two():
    fb = provide_feedback("hypotheses", [
        "Revenue is declining due to competitive pricing pressure in the market",
        "Volume is decreasing because customers are switching to alternative products",
    ])
    assert fb.passed is True


def test_heuristic_equation_needs_math():
    fb = provide_feedback("equation", "I think we need to look at the financial drivers of this business")
    assert fb.passed is False


def test_heuristic_equation_passes():
    fb = provide_feedback("equation", "Profit = Revenue - Costs, where Revenue = Price x Volume")
    assert fb.passed is True


def test_heuristic_calculation_needs_numbers():
    fb = provide_feedback("calculation", ["We multiply the price by the volume to get revenue"])
    assert fb.passed is False


def test_heuristic_calculation_passes():
    fb = provide_feedback("calculation", ["Price = $50 x Volume of 10K units = $500K revenue"])
    assert fb.passed is True


def test_heuristic_conclusion_passes():
    fb = provide_feedback(
        "conclusion",
        "I recommend the client pursue the digital expansion strategy because the market opportunity exceeds $500M and the risk of cannibalization is manageable."
    )
    assert fb.passed is True


def test_heuristic_conclusion_fails_missing_keywords():
    fb = provide_feedback(
        "conclusion",
        "The analysis has been thorough and covered many important aspects of the situation at hand."
    )
    assert fb.passed is False


def test_heuristic_additional_insights_passes():
    fb = provide_feedback(
        "additional_insights",
        "Key risks include regulatory changes that could impact the timeline. Competitors may respond with price cuts."
    )
    assert fb.passed is True


def test_heuristic_framework_passes():
    fb = provide_feedback(
        "framework",
        "I will use the Profitability framework because this is fundamentally a question about declining margins."
    )
    assert fb.passed is True


def test_heuristic_framework_fails_no_keywords():
    fb = provide_feedback("framework", "I will look at the problem.")
    assert fb.passed is False


def test_check_heuristic_rules_returns_reasons():
    passed, reasons = _check_heuristic_rules("restatement", ["Short."])
    assert passed is False
    assert len(reasons) > 0


# ---------------------------------------------------------------------------
# Clarifying questions
# ---------------------------------------------------------------------------

def test_heuristic_clarifying_questions_passes():
    fb = provide_feedback("clarifying_questions", [
        "What is the timeline for this strategic decision?",
        "Are there any budget constraints we should be aware of?",
    ])
    assert fb.passed is True


def test_heuristic_clarifying_questions_fails_one_item():
    fb = provide_feedback("clarifying_questions", [
        "What is the scope?",
    ])
    assert fb.passed is False


# ---------------------------------------------------------------------------
# Exhibit interpretation
# ---------------------------------------------------------------------------

def test_heuristic_exhibit_interpretation_passes():
    fb = provide_feedback(
        "exhibit_interpretation",
        "The key insight from this data is that the premium segment shows 3x faster growth than mass market, which suggests the client should focus investment on premium.",
    )
    assert fb.passed is True


def test_heuristic_exhibit_interpretation_fails_too_short():
    fb = provide_feedback("exhibit_interpretation", "Revenue is growing.")
    assert fb.passed is False


# ---------------------------------------------------------------------------
# Probe questions
# ---------------------------------------------------------------------------

def test_generate_probe_question_heuristic():
    """Heuristic probes should return a string at intermediate+."""
    probe = generate_probe_question("frame", "I'll look at costs and revenue.", difficulty="intermediate")
    assert probe is not None
    assert len(probe) > 10


def test_generate_probe_question_beginner_returns_none():
    probe = generate_probe_question("frame", "anything", difficulty="beginner")
    assert probe is None


# ---------------------------------------------------------------------------
# Clarifying question answers
# ---------------------------------------------------------------------------

def test_answer_clarifying_questions_heuristic():
    answers = answer_clarifying_questions(["What is the budget?", "Who decides?"])
    assert len(answers) == 2
    assert all(isinstance(a, str) for a in answers)


# ---------------------------------------------------------------------------
# Mandatory data reveals
# ---------------------------------------------------------------------------

def test_heuristic_data_reveal_returns_reveal():
    reveal = _heuristic_data_reveal("frame")
    assert reveal is not None
    assert reveal.reveal
    assert reveal.reveal_type in ("data", "constraint", "curveball")


def test_mandatory_reveal_intermediate_frame():
    """At intermediate difficulty, frame is a mandatory reveal stage."""
    reveal = generate_data_reveal("frame", "Some framing response", difficulty="intermediate")
    assert reveal is not None
    assert reveal.reveal


def test_no_reveal_beginner():
    reveal = generate_data_reveal("frame", "Some framing response", difficulty="beginner")
    assert reveal is None
