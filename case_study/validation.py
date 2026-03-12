"""
Input validation utilities for the Case‑Study CLI.

This module centralises common validation rules applied to user
responses at each stage of the reasoning loop.  Validation logic
ensures that users provide non‑empty answers and discourages overly
terse responses by emitting warnings when responses fall below a
minimum length threshold.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Holds the outcome of validating a user response.

    Attributes
    ----------
    accepted : bool
        Whether the input satisfies the minimum requirements and can be
        accepted as a final answer.
    short : bool
        Whether the input falls below the recommended length and
        therefore warrants a user warning.  If true, the caller
        should ask the user whether they wish to expand their
        response.
    message : str | None
        Optional descriptive message to accompany invalid inputs.
    """

    accepted: bool
    short: bool
    message: str | None = None


MIN_CHARACTERS = 10


def validate_response(text: str) -> ValidationResult:
    """Validate a single free‑form response.

    Parameters
    ----------
    text : str
        User input to validate.

    Returns
    -------
    ValidationResult
        The result indicating whether the input meets the basic
        requirements and if it is considered short.
    """
    stripped = text.strip()
    if not stripped:
        return ValidationResult(
            accepted=False,
            short=True,
            message="Response cannot be empty."
        )
    if len(stripped) < MIN_CHARACTERS:
        return ValidationResult(
            accepted=True,
            short=True,
            message="Your response is very short."
        )
    return ValidationResult(accepted=True, short=False)


def validate_multi_item(item: str) -> ValidationResult:
    """Validate an individual entry in a list of items.

    This simply delegates to :func:`validate_response` but exists for
    semantic clarity.
    """
    return validate_response(item)