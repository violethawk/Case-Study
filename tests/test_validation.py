from case_study.validation import validate_response, validate_multi_item


def test_empty_response_rejected():
    result = validate_response("")
    assert result.accepted is False
    assert result.short is True


def test_whitespace_only_rejected():
    result = validate_response("   ")
    assert result.accepted is False


def test_short_response_accepted_with_warning():
    result = validate_response("short")
    assert result.accepted is True
    assert result.short is True


def test_adequate_response_accepted():
    result = validate_response("This is a sufficiently long response.")
    assert result.accepted is True
    assert result.short is False


def test_validate_multi_item_delegates():
    result = validate_multi_item("A valid item for the list")
    assert result.accepted is True
    assert result.short is False
