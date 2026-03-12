from pathlib import Path

from case_study.cases import load_cases, get_case_by_id


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_cases.json"


def test_load_cases_returns_list():
    cases = load_cases(DATA_FILE)
    assert isinstance(cases, list)
    assert len(cases) > 0


def test_each_case_has_required_fields():
    cases = load_cases(DATA_FILE)
    for case in cases:
        assert "id" in case
        assert "prompt" in case
        assert "category" in case
        assert "difficulty" in case


def test_case_categories_are_valid():
    valid_categories = {"strategy", "market-sizing", "quantitative"}
    cases = load_cases(DATA_FILE)
    for case in cases:
        assert case["category"] in valid_categories, f"{case['id']} has invalid category: {case['category']}"


def test_get_case_by_id_found():
    cases = load_cases(DATA_FILE)
    result = get_case_by_id(cases[0]["id"], cases)
    assert result is not None
    assert result["id"] == cases[0]["id"]


def test_get_case_by_id_not_found():
    cases = load_cases(DATA_FILE)
    result = get_case_by_id("nonexistent_case_id", cases)
    assert result is None
