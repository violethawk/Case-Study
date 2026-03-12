"""
AI coaching module (simplified).

This module provides a stubbed implementation of an "AI coach".  In
the MVP version of Case‑Study the coach does not contact any remote
service; instead it generates generic feedback based on simple
heuristics of the user’s input length and the current reasoning
stage.  The feedback adheres to the project’s guidelines: it avoids
providing answers to the case and focuses instead on the quality of
the thought process.

If a future version integrates with an actual AI model this module
serves as the integration point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class CoachFeedback:
    """Encapsulates feedback returned by the AI coach."""

    strengths: str
    gaps: str
    questions: str

    def format_for_cli(self) -> str:
        """Return a human‑readable representation suitable for the CLI."""
        lines = [
            "STRENGTHS:",
            self.strengths,
            "",
            "GAPS:",
            self.gaps,
            "",
            "SUGGESTED QUESTIONS:",
            self.questions,
        ]
        return "\n".join(lines)


def provide_feedback(stage: str, content: Iterable[str] | str) -> CoachFeedback:
    """Generate simple heuristic feedback for the given stage and content.

    Parameters
    ----------
    stage : str
        The name of the reasoning stage (e.g. "frame", "hypotheses").
    content : iterable of str or str
        The user’s raw input(s) for this stage.  A single string or
        list of strings is accepted.

    Returns
    -------
    CoachFeedback
        A dataclass containing the strengths, gaps and suggested
        questions for the user’s reasoning.
    """
    # Flatten input into a list of strings
    if isinstance(content, str):
        texts = [content]
    else:
        texts = list(content)

    # Combine length of all responses
    total_length = sum(len(t.strip()) for t in texts)
    num_items = len(texts)

    # Derive generic strengths
    if total_length > 200:
        strengths = (
            "You provided a comprehensive response with a high level of detail. "
            "This depth suggests that you’ve considered multiple factors."
        )
    elif total_length > 80:
        strengths = (
            "Your response is fairly detailed and demonstrates structured thinking."
        )
    else:
        strengths = (
            "You have started to outline your thoughts. With more elaboration your reasoning could be clearer."
        )

    # Derive generic gaps
    if stage.lower() == "frame":
        gaps = (
            "Ensure you have clearly defined the objective, the key stakeholders and the metrics that matter. "
            "Consider whether there are external constraints or assumptions that should be made explicit."
        )
    elif stage.lower() == "hypotheses":
        gaps = (
            "Check that your hypotheses cover different categories (e.g., customer, product, market, operations) "
            "and that they are mutually exclusive and collectively exhaustive where possible."
        )
    elif stage.lower() == "analyze":
        gaps = (
            "Be explicit about the analyses you would perform and why they matter. "
            "If you mention calculations, note the data required to perform them."
        )
    elif stage.lower() == "update":
        gaps = (
            "Indicate which hypotheses were invalidated or strengthened by your analysis. "
            "Note any remaining uncertainties or assumptions."
        )
    elif stage.lower() == "conclude":
        gaps = (
            "Ensure your recommendation logically follows from the analysis and addresses the original objective. "
            "Consider noting risks, trade‑offs and next steps."
        )
    else:
        gaps = (
            "Consider expanding on your thought process and ensuring that all major aspects of the problem are addressed."
        )

    # Derive generic questions
    if stage.lower() == "frame":
        questions = (
            "What decision is truly being made? What does success look like? "
            "Are there time constraints or specific metrics that leadership cares about?"
        )
    elif stage.lower() == "hypotheses":
        questions = (
            "Have you considered drivers from customer behaviour, market trends, internal capabilities and external factors?"
        )
    elif stage.lower() == "analyze":
        questions = (
            "What data would validate or refute each hypothesis? "
            "Are there benchmarks or prior case examples you could compare against?"
        )
    elif stage.lower() == "update":
        questions = (
            "Which hypotheses now seem most plausible? "
            "What additional information would help you further narrow down the options?"
        )
    elif stage.lower() == "conclude":
        questions = (
            "What implementation challenges might arise? "
            "How would you measure the success of your recommendation over time?"
        )
    else:
        questions = (
            "What other perspectives or dimensions might enrich your reasoning?"
        )

    return CoachFeedback(strengths=strengths, gaps=gaps, questions=questions)