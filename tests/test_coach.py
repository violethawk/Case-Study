from case_study.coach import provide_feedback, CoachFeedback, is_ai_enabled


def test_provide_feedback_returns_coach_feedback():
    fb = provide_feedback("frame", "I would use Porter's Five Forces.")
    assert isinstance(fb, CoachFeedback)
    assert fb.strengths
    assert fb.gaps
    assert fb.questions


def test_feedback_for_all_stages():
    stages = [
        "restatement", "frame", "assumptions", "hypotheses",
        "analyses", "updates", "conclusion", "additional_insights",
    ]
    for stage in stages:
        fb = provide_feedback(stage, "Some input text here.")
        assert fb.strengths
        assert fb.gaps
        assert fb.questions


def test_feedback_with_list_input():
    fb = provide_feedback("hypotheses", ["hypothesis one", "hypothesis two"])
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


def test_heuristic_feedback_always_passes():
    fb = provide_feedback("frame", "I would use Porter's Five Forces.")
    assert fb.passed is True


def test_heuristic_feedback_all_stages_pass():
    stages = [
        "restatement", "frame", "assumptions", "hypotheses",
        "analyses", "updates", "conclusion", "additional_insights",
    ]
    for stage in stages:
        fb = provide_feedback(stage, "Some input text here.")
        assert fb.passed is True, f"{stage} should pass with heuristic backend"


def test_is_ai_enabled_without_key():
    assert is_ai_enabled() is False
