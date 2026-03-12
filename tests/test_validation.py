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


def test_exactly_min_characters():
    result = validate_response("a" * 10)
    assert result.accepted is True
    assert result.short is False


def test_one_below_min_characters():
    result = validate_response("a" * 9)
    assert result.accepted is True
    assert result.short is True
    assert result.message is not None


def test_leading_trailing_whitespace_stripped():
    result = validate_response("   short   ")
    assert result.accepted is True
    assert result.short is True


def test_empty_response_has_message():
    result = validate_response("")
    assert result.message == "Response cannot be empty."


def test_multi_item_empty_rejected():
    result = validate_multi_item("")
    assert result.accepted is False
