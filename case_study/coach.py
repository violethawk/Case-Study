"""
AI coaching module.

This module provides feedback on the user's reasoning at each stage
of a case study session.  When a ``GEMINI_API_KEY`` environment
variable is set the coach calls Google's Gemini 3.1 Flash Lite model
for tailored feedback **and** evaluates whether the response meets
the quality bar to advance (the "Mario levels" gate).  Otherwise it
falls back to deterministic heuristics that always pass.

The public interface is :func:`provide_feedback`, which always returns
a :class:`CoachFeedback` dataclass regardless of which backend is used.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from collections.abc import Iterable

_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Stage-specific evaluation criteria used in the Gemini prompt.
STAGE_CRITERIA: dict[str, str] = {
    "restatement": (
        "The user must: (1) restate the core question in their own words, "
        "(2) identify the client/decision-maker, (3) note any key constraints "
        "or goals mentioned in the prompt. Missing any of these = not passed."
    ),
    "framework": (
        "The user must: (1) select and name a specific framework, "
        "(2) briefly explain why it fits this problem type. "
        "Simply naming a framework without justification = not passed."
    ),
    "frame": (
        "The user must: (1) explain how they will apply their chosen framework, "
        "(2) outline the key areas or buckets they will analyze, "
        "(3) indicate which area is likely most important. "
        "Vague or unstructured answers = not passed."
    ),
    "assumptions": (
        "The user must: (1) state at least 2 explicit assumptions, "
        "(2) each assumption should be justified (why they believe it), "
        "(3) flag which assumptions are most critical. Unjustified or missing assumptions = not passed."
    ),
    "equation": (
        "The user must: (1) express the problem as a clear quantitative equation "
        "or formula (e.g., Revenue = Price x Volume), (2) identify which variables "
        "are known vs. need estimation, (3) explain why this decomposition captures "
        "the key drivers. A vague or non-quantitative breakdown = not passed."
    ),
    "hypotheses": (
        "The user must: (1) propose at least 2 distinct hypotheses, "
        "(2) hypotheses should span different categories (e.g. demand-side vs supply-side, "
        "internal vs external), (3) each hypothesis should be testable. "
        "A single hypothesis or overlapping hypotheses = not passed."
    ),
    "analyses": (
        "The user must: (1) describe at least 2 specific analyses they would perform, "
        "(2) link each analysis to a hypothesis it would test, "
        "(3) note what data they would need. Vague or disconnected analyses = not passed."
    ),
    "updates": (
        "The user must: (1) reference their earlier hypotheses, "
        "(2) state which were strengthened or weakened and why, "
        "(3) note any remaining uncertainty. Simply restating hypotheses = not passed."
    ),
    "conclusion": (
        "The user must: (1) state a clear recommendation, "
        "(2) support it with reasoning tied to their analysis, "
        "(3) acknowledge at least one risk or trade-off. "
        "An unsupported opinion or missing risks = not passed."
    ),
    "additional_insights": (
        "The user must: (1) go beyond what was directly asked, "
        "(2) mention at least one of: implementation risks, competitive responses, "
        "second-order effects, or adjacent opportunities, "
        "(3) show business judgment. Generic or shallow responses = not passed."
    ),
    "structure": (
        "The user must: (1) identify the key components or segments of the estimation, "
        "(2) explain a logical top-down or bottom-up approach, (3) outline what they "
        "will calculate in each step. Unstructured or missing decomposition = not passed."
    ),
    "setup": (
        "The user must: (1) clearly state what quantity they are solving for, "
        "(2) identify the key variables and relationships, (3) outline their calculation "
        "approach step by step. Jumping to numbers without structure = not passed."
    ),
    "calculation": (
        "The user must: (1) show each calculation step explicitly, "
        "(2) use their stated assumptions consistently, (3) arrive at a clear numeric result. "
        "Skipped steps or arithmetic errors = not passed."
    ),
    "sanity_check": (
        "The user must: (1) compare their estimate to a known benchmark or alternative approach, "
        "(2) assess whether the magnitude is reasonable, (3) note what would change the answer "
        "most. Skipping the cross-check or accepting an unreasonable number = not passed."
    ),
    "sensitivity": (
        "The user must: (1) identify the 2-3 assumptions with the largest impact on the result, "
        "(2) show how varying those assumptions changes the output, (3) discuss the range of "
        "plausible outcomes. Ignoring key drivers or only testing one variable = not passed."
    ),
    "clarifying_questions": (
        "The user must: (1) ask at least 2 relevant clarifying questions, "
        "(2) questions should target scope, constraints, or ambiguity in the problem, "
        "(3) questions should demonstrate they've read the prompt carefully. "
        "Generic or irrelevant questions = not passed."
    ),
    "exhibit_interpretation": (
        "The user must: (1) lead with a clear headline insight ('so what'), "
        "(2) support the headline with specific data points from the exhibit, "
        "(3) connect the insight to the case question. "
        "Describing the exhibit without a takeaway = not passed."
    ),
}

# ---------------------------------------------------------------------------
# Difficulty-specific prompts
# ---------------------------------------------------------------------------

DIFFICULTY_LEVELS = ("beginner", "intermediate", "advanced")

_RESPONSE_FORMAT = """
Respond with ONLY valid JSON in this exact format (no markdown fences):
{"passed": true/false, "strengths": "...", "gaps": "...", "questions": "..."}

Where:
- "passed" is true if the response meets the stage criteria, false otherwise
- "strengths" highlights what the candidate did well
- "gaps" identifies what is missing or weak
- "questions" contains 1-2 follow-up questions to deepen their reasoning
"""

SYSTEM_PROMPTS: dict[str, str] = {
    "beginner": (
        "You are a friendly case interview coach helping someone who is new to "
        "consulting-style cases. Your job is to teach and encourage.\n\n"
        "Your style:\n"
        "- Be warm and supportive. Celebrate what the candidate got right before "
        "noting gaps.\n"
        "- When something is missing, explain WHY it matters — teach the principle "
        "behind it (e.g., 'In a real interview, the interviewer wants to see that "
        "you size the market before jumping to strategy').\n"
        "- Give concrete hints about what to add, without giving away the answer "
        "(e.g., 'Think about what drives revenue — what are the components?').\n"
        "- Be lenient on passing: if the candidate shows genuine effort and covers "
        "the basics, let them pass even if the answer isn't polished.\n"
        "- Ask gentle guiding questions, not aggressive probes.\n"
        "- NEVER give away the answer or solve the case.\n"
        + _RESPONSE_FORMAT
    ),
    "intermediate": (
        "You are an experienced case interview coach conducting a practice session. "
        "You balance encouragement with honest, specific feedback.\n\n"
        "Your style:\n"
        "- Reference the candidate's actual words when highlighting strengths or gaps.\n"
        "- Point out quantitative errors specifically but constructively "
        "(e.g., 'Your margin calculation seems off — double-check the cost figure').\n"
        "- Challenge weak assumptions gently: 'What if that assumption is wrong? "
        "How sensitive is your answer to it?'\n"
        "- Ask follow-up questions that a real interviewer might ask, but frame them "
        "as learning opportunities.\n"
        "- Be fair on passing: the response should show structured thinking and "
        "cover the key requirements, but doesn't need to be perfect.\n"
        "- NEVER give away the answer or solve the case.\n"
        + _RESPONSE_FORMAT
    ),
    "advanced": (
        "You are a senior MBB (McKinsey/Bain/BCG) interviewer conducting a live "
        "case interview. You evaluate like a real final-round interviewer.\n\n"
        "Your style:\n"
        "- Be direct and specific. Reference the candidate's exact words when "
        "pointing out strengths or gaps.\n"
        "- Call out quantitative errors sharply "
        "(e.g., 'Your revenue calculation assumes X but the case says Y').\n"
        "- Challenge weak assumptions aggressively: 'What if that assumption is "
        "off by 50%? How would that change your answer?'\n"
        "- Ask pointed follow-up questions that probe logic — a real interviewer "
        "would say 'Walk me through why you chose that driver' not "
        "'Consider other perspectives.'\n"
        "- Be rigorous on passing: the response must show structured thinking, "
        "quantitative precision, and hit all key requirements.\n"
        "- NEVER give away the answer or solve the case.\n"
        + _RESPONSE_FORMAT
    ),
}

# Default for backward compatibility
SYSTEM_PROMPT = SYSTEM_PROMPTS["advanced"]

DATA_REVEAL_PROMPT = """\
You are a senior MBB interviewer conducting a live case interview. \
The candidate has just completed a stage of their analysis. Your job is to \
provide a brief piece of new information, data, or a curveball that the \
candidate must factor into their next steps — just like a real interviewer \
would share a new exhibit or data point mid-case.

Rules:
- The reveal should be 2-4 sentences, concise and specific.
- It must be RELEVANT to the case context and the candidate's response so far.
- It should challenge or complicate their thinking — not confirm it.
- Types of reveals: new data point, competitor action, market shift, \
client constraint, surprising survey result, cost figure, or regulatory change.
- Do NOT evaluate the candidate's response. Just share the new information \
as if you're handing them a new exhibit.
- NEVER solve the case or hint at the answer.
- Write in first person as the interviewer: "Let me share some additional data..."

Respond with ONLY valid JSON in this exact format (no markdown fences):
{"reveal": "...", "type": "data|constraint|curveball"}

Where:
- "reveal" is the interviewer's statement sharing new information
- "type" categorizes the reveal
"""


# Stages after which the interviewer reveals new data.
# Maps stage name -> brief description of what kind of reveal to generate.
DATA_REVEAL_STAGES: dict[str, str] = {
    "frame": "Share a data exhibit or key metric that the candidate should factor into their analysis.",
    "assumptions": "Challenge one of the candidate's assumptions with a contradicting data point or market reality.",
    "hypotheses": "Share data that challenges or complicates one of the candidate's hypotheses, forcing them to reconsider.",
    "equation": "Provide an additional variable or constraint that complicates the candidate's equation.",
    "structure": "Share a data exhibit or segmentation insight that the candidate should incorporate.",
    "setup": "Provide an additional data point or constraint that the candidate should factor in.",
    "calculation": "Reveal a surprising figure or market shift that may change the candidate's numbers.",
}


@dataclass
class DataReveal:
    """A mid-case data reveal from the interviewer."""

    reveal: str
    reveal_type: str = "data"


@dataclass
class CoachFeedback:
    """Encapsulates feedback returned by the AI coach."""

    strengths: str
    gaps: str
    questions: str
    passed: bool = True

    def format_for_cli(self) -> str:
        """Return a human-readable representation suitable for the CLI."""
        status = "PASSED" if self.passed else "NOT YET — revise and resubmit"
        lines = [
            f"RESULT: {status}",
            "",
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_ai_enabled() -> bool:
    """Return True if the Gemini API key is configured."""
    return bool(_GEMINI_API_KEY)


def provide_feedback(
    stage: str,
    content: Iterable[str] | str,
    case_context: str = "",
    difficulty: str = "advanced",
) -> CoachFeedback:
    """Generate feedback for the given stage and content.

    Uses Gemini 3.1 Flash Lite when ``GEMINI_API_KEY`` is set,
    otherwise falls back to heuristic feedback.

    Parameters
    ----------
    stage : str
        The name of the reasoning stage (e.g. "frame", "equation").
    content : iterable of str or str
        The user's raw input(s) for this stage.
    case_context : str
        The case prompt and context for more specific feedback.
    difficulty : str
        One of "beginner", "intermediate", "advanced".

    Returns
    -------
    CoachFeedback
    """
    if isinstance(content, str):
        texts = [content]
    else:
        texts = list(content)

    if _GEMINI_API_KEY:
        try:
            return _gemini_feedback(stage, texts, case_context, difficulty)
        except Exception:
            # Fall back to heuristics on any API error
            pass

    return _heuristic_feedback(stage, texts)


def generate_data_reveal(
    stage: str,
    content: Iterable[str] | str,
    case_context: str = "",
    difficulty: str = "advanced",
    case_data: dict | None = None,
) -> DataReveal | None:
    """Generate an interviewer data reveal after the given stage.

    Returns ``None`` if the stage doesn't warrant a reveal, AI is not
    enabled, or the API call fails.  Beginner difficulty skips reveals
    entirely; intermediate only triggers on a subset of stages.
    """
    if stage not in DATA_REVEAL_STAGES:
        return None
    # Beginner: no curveballs
    if difficulty == "beginner":
        return None

    # Mandatory reveal stages per difficulty
    mandatory_stages_int = {"frame", "calculation"}
    mandatory_stages_adv = {"frame", "hypotheses", "calculation"}
    is_mandatory = (
        (difficulty == "intermediate" and stage in mandatory_stages_int)
        or (difficulty == "advanced" and stage in mandatory_stages_adv)
    )

    # Non-mandatory intermediate stages: skip
    if difficulty == "intermediate" and not is_mandatory:
        return None

    if isinstance(content, str):
        texts = [content]
    else:
        texts = list(content)

    # Try case-embedded reveals first
    if case_data:
        case_reveals = case_data.get("reveals", {})
        if stage in case_reveals:
            r = case_reveals[stage]
            return DataReveal(
                reveal=r.get("reveal", r) if isinstance(r, dict) else r,
                reveal_type=r.get("type", "data") if isinstance(r, dict) else "data",
            )

    if _GEMINI_API_KEY:
        try:
            # At advanced, instruct Gemini to contradict hypothesis
            extra = ""
            if difficulty == "advanced":
                extra = (
                    " IMPORTANT: The reveal MUST contradict or complicate the "
                    "candidate's working hypothesis or assumptions. Force them to adapt."
                )
            return _gemini_data_reveal(stage, texts, case_context, extra)
        except Exception:
            pass

    # Heuristic fallback for mandatory reveals
    if is_mandatory:
        return _heuristic_data_reveal(stage)

    return None


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

def _strip_markdown_fences(raw: str) -> str:
    """Remove markdown code fences from model output."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[: raw.rfind("```")]
    return raw.strip()


def _gemini_feedback(
    stage: str,
    texts: list[str],
    case_context: str = "",
    difficulty: str = "advanced",
) -> CoachFeedback:
    """Call Gemini 3.1 Flash Lite and parse the structured response."""
    from google import genai

    client = genai.Client(api_key=_GEMINI_API_KEY)

    # Resolve stage key for criteria lookup
    key_aliases = {"analyze": "analyses", "update": "updates", "conclude": "conclusion"}
    resolved_key = key_aliases.get(stage.lower(), stage.lower())
    criteria = STAGE_CRITERIA.get(resolved_key, "Evaluate the quality and completeness of the response.")

    system_prompt = SYSTEM_PROMPTS.get(difficulty, SYSTEM_PROMPTS["advanced"])
    user_input = "\n".join(texts) if len(texts) > 1 else texts[0]
    context_section = f"\nCase context:\n{case_context}\n" if case_context else ""
    prompt = (
        f"{system_prompt}\n\n"
        f"Stage: {stage}\n"
        f"{context_section}\n"
        f"Passing criteria for this stage:\n{criteria}\n\n"
        f"Candidate's response:\n{user_input}\n\n"
        "Evaluate the response and provide your interviewer feedback as JSON."
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
    )
    raw = _strip_markdown_fences(response.text.strip())

    data = json.loads(raw)
    return CoachFeedback(
        strengths=data.get("strengths", ""),
        gaps=data.get("gaps", ""),
        questions=data.get("questions", ""),
        passed=bool(data.get("passed", True)),
    )


def _gemini_data_reveal(
    stage: str, texts: list[str], case_context: str, extra: str = "",
) -> DataReveal:
    """Call Gemini to generate an interviewer data reveal."""
    from google import genai

    client = genai.Client(api_key=_GEMINI_API_KEY)

    reveal_guidance = DATA_REVEAL_STAGES.get(stage, "")
    user_input = "\n".join(texts) if len(texts) > 1 else texts[0]
    prompt = (
        f"{DATA_REVEAL_PROMPT}\n\n"
        f"Case context:\n{case_context}\n\n"
        f"Stage just completed: {stage}\n"
        f"Reveal guidance: {reveal_guidance}{extra}\n\n"
        f"Candidate's response:\n{user_input}\n\n"
        "Generate a brief, specific data reveal as JSON."
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
    )
    raw = _strip_markdown_fences(response.text.strip())

    data = json.loads(raw)
    return DataReveal(
        reveal=data.get("reveal", ""),
        reveal_type=data.get("type", "data"),
    )


# ---------------------------------------------------------------------------
# Heuristic data reveals (fallback when no API key)
# ---------------------------------------------------------------------------

_HEURISTIC_REVEALS: dict[str, DataReveal] = {
    "frame": DataReveal(
        reveal=(
            "Let me share some additional context: the competitive landscape has "
            "shifted significantly in the last 18 months. Two new entrants have "
            "captured roughly 12% market share combined. How does this affect "
            "your analysis?"
        ),
        reveal_type="data",
    ),
    "hypotheses": DataReveal(
        reveal=(
            "Interesting hypotheses. I should mention — our internal data shows "
            "that the factor you've identified as primary actually only accounts "
            "for about 15% of the variance. What else might be driving this?"
        ),
        reveal_type="curveball",
    ),
    "assumptions": DataReveal(
        reveal=(
            "One thing to consider: a recent industry report suggests that one "
            "of your key assumptions may be off by 30-40%. How would that change "
            "your approach?"
        ),
        reveal_type="constraint",
    ),
    "calculation": DataReveal(
        reveal=(
            "Good progress on the numbers. However, I just received updated "
            "figures: the actual cost base is about 20% higher than what you've "
            "been using. Can you quickly adjust your calculation?"
        ),
        reveal_type="data",
    ),
    "structure": DataReveal(
        reveal=(
            "Before you proceed — there's a significant geographic skew in this "
            "market. The top 3 metro areas account for 60% of total demand. "
            "Does that change how you'd structure your estimation?"
        ),
        reveal_type="data",
    ),
    "setup": DataReveal(
        reveal=(
            "One additional constraint: the client has a hard capital expenditure "
            "ceiling that may limit some of the options you're considering. "
            "Factor that into your setup."
        ),
        reveal_type="constraint",
    ),
    "equation": DataReveal(
        reveal=(
            "Good equation. But there's a non-obvious cost component you may be "
            "missing — regulatory compliance costs have been rising 25% year-over-year "
            "in this industry. How would you incorporate that?"
        ),
        reveal_type="data",
    ),
}


def _heuristic_data_reveal(stage: str) -> DataReveal:
    """Return a pre-built data reveal for mandatory stages without API."""
    return _HEURISTIC_REVEALS.get(
        stage,
        DataReveal(
            reveal="The interviewer shares additional data that may affect your analysis.",
            reveal_type="data",
        ),
    )


# ---------------------------------------------------------------------------
# Clarifying question answers
# ---------------------------------------------------------------------------

_CLARIFYING_ANSWER_PROMPT = """\
You are a case interviewer. The candidate has asked clarifying questions about the case.
Answer each question briefly and helpfully, staying consistent with the case data provided.
Keep answers to 1-2 sentences each. If the case data doesn't cover the question, say
"That's a good question — for this case, assume [reasonable default]."

Respond with ONLY valid JSON in this exact format (no markdown fences):
{"answers": ["answer 1", "answer 2", ...]}
"""


def answer_clarifying_questions(
    questions: list[str],
    case_context: str = "",
) -> list[str]:
    """Answer the candidate's clarifying questions as the interviewer.

    Uses Gemini when available, otherwise returns generic responses.
    """
    if not questions:
        return []

    if _GEMINI_API_KEY:
        try:
            return _gemini_answer_questions(questions, case_context)
        except Exception:
            pass

    # Heuristic fallback
    return [
        "Good question. Based on the information provided, you can proceed "
        "with reasonable assumptions on that point."
        for _ in questions
    ]


def _gemini_answer_questions(questions: list[str], case_context: str) -> list[str]:
    """Call Gemini to answer clarifying questions."""
    from google import genai

    client = genai.Client(api_key=_GEMINI_API_KEY)
    q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    prompt = (
        f"{_CLARIFYING_ANSWER_PROMPT}\n\n"
        f"Case context:\n{case_context}\n\n"
        f"Candidate's questions:\n{q_text}\n\n"
        "Answer each question as JSON."
    )
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
    )
    raw = _strip_markdown_fences(response.text.strip())
    data = json.loads(raw)
    return data.get("answers", [])


# ---------------------------------------------------------------------------
# Multi-turn probing
# ---------------------------------------------------------------------------

_PROBE_PROMPT = """\
You are an MBB case interviewer. The candidate just submitted their response for this stage.
Ask ONE pointed follow-up question that tests depth of understanding. Examples:
- "Walk me through why you chose that specific driver."
- "What happens to your recommendation if that assumption is off by 50%?"
- "Can you quantify that? Give me a rough number."

The question should be specific to their response, not generic.

Respond with ONLY valid JSON (no markdown fences):
{"probe": "your follow-up question"}
"""

# Pre-built probe questions for heuristic fallback
_HEURISTIC_PROBES: dict[str, str] = {
    "restatement": "What's the single most important piece of information you'd want from the interviewer before proceeding?",
    "framework": "Why this framework over the alternatives? What would you miss if you used a different one?",
    "frame": "Which of your buckets do you think will be the most important, and why?",
    "assumptions": "Which of your assumptions would most change your answer if it were wrong?",
    "hypotheses": "If your primary hypothesis is ruled out in the first 2 minutes of analysis, where do you pivot?",
    "equation": "What happens to your recommendation if the key variable in your equation doubles?",
    "calculation": "Walk me through the step where you're least confident in your numbers.",
    "conclusion": "What's the biggest risk to your recommendation, and how would you mitigate it?",
    "additional_insights": "If you had 5 more minutes with the CEO, what's the one thing you'd investigate?",
    "structure": "What segment of your decomposition carries the most uncertainty?",
    "setup": "Before you calculate, what result would make you rethink your entire approach?",
    "sanity_check": "If your estimate is off by 2x, which assumption is most likely the culprit?",
    "sensitivity": "Which variable would you recommend the client monitor most closely post-decision?",
    "exhibit_interpretation": "How does this insight change what you'd prioritize in the rest of the case?",
    "clarifying_questions": "Is there anything about the scope of this problem that still feels ambiguous?",
}


def generate_probe_question(
    stage: str,
    content: Iterable[str] | str,
    case_context: str = "",
    difficulty: str = "advanced",
) -> str | None:
    """Generate a follow-up probe question after a stage submission.

    Returns None for beginner difficulty (no probing).
    """
    if difficulty == "beginner":
        return None

    if isinstance(content, str):
        texts = [content]
    else:
        texts = list(content)

    if _GEMINI_API_KEY:
        try:
            return _gemini_probe(stage, texts, case_context)
        except Exception:
            pass

    return _HEURISTIC_PROBES.get(stage)


def _gemini_probe(stage: str, texts: list[str], case_context: str) -> str:
    """Call Gemini to generate a probe question."""
    from google import genai

    client = genai.Client(api_key=_GEMINI_API_KEY)
    user_input = "\n".join(texts) if len(texts) > 1 else texts[0]
    prompt = (
        f"{_PROBE_PROMPT}\n\n"
        f"Case context:\n{case_context}\n\n"
        f"Stage: {stage}\n"
        f"Candidate's response:\n{user_input}\n\n"
        "Generate your follow-up probe as JSON."
    )
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
    )
    raw = _strip_markdown_fences(response.text.strip())
    data = json.loads(raw)
    return data.get("probe", "")


# ---------------------------------------------------------------------------
# Heuristic rules for pass/fail without an LLM
# ---------------------------------------------------------------------------

import re as _re

# Each rule: min_words (for single), min_items (for multi), min_item_words,
# required_patterns (must match at least one, case-insensitive)
HEURISTIC_RULES: dict[str, dict] = {
    "restatement": {
        "min_words": 15,
        "patterns": [r"\bclient\b", r"\bquestion\b", r"\bdecid", r"\bgoal\b",
                     r"\bobjective\b", r"\bdetermin", r"\?"],
    },
    "framework": {
        "min_words": 5,
        "patterns": [r"\bframework\b", r"\bporter", r"\b3c", r"\b4p", r"\bswot\b",
                     r"\bprofit", r"\bcost.*benefit", r"\bvalue.chain", r"\bmece\b",
                     r"\bstructur", r"\bsegment", r"\bsupply.*demand"],
    },
    "frame": {
        "min_words": 20,
        "patterns": [r"\bframework\b", r"\bstructur", r"\banalyz", r"\bbucket",
                     r"\barea\b", r"\bdriver", r"\bcomponent", r"\bfactor"],
    },
    "assumptions": {
        "min_items": 2,
        "min_item_words": 6,
    },
    "hypotheses": {
        "min_items": 2,
        "min_item_words": 6,
    },
    "equation": {
        "min_words": 10,
        "patterns": [r"=", r"\*", r"\btimes\b", r"\bdivid", r"\bminus\b",
                     r"\bplus\b", r"\brevenue\b", r"\bcost\b", r"\bprofit\b",
                     r"\bprice\b", r"\bvolume\b", r"\bmargin\b", r"x\s"],
    },
    "calculation": {
        "min_items": 1,
        "min_item_words": 5,
        "require_numbers": True,
    },
    "conclusion": {
        "min_words": 20,
        "patterns": [r"\brecommend", r"\bshould\b", r"\bsuggest", r"\bpropose",
                     r"\bconclude", r"\btherefore\b", r"\bdecision\b",
                     r"\badvise\b", r"\bpursue\b", r"\bfocus\b"],
    },
    "additional_insights": {
        "min_words": 15,
        "patterns": [r"\brisk", r"\bcompetit", r"\bimplement", r"\bregulat",
                     r"\bopportunit", r"\blong.term", r"\bmonitor", r"\bchalleng",
                     r"\bsecond.order", r"\badjacent"],
    },
    "structure": {
        "min_words": 15,
        "patterns": [r"\btop.down", r"\bbottom.up", r"\bsegment", r"\bcomponent",
                     r"\bbreak", r"\bdecompos", r"\bsplit", r"\bdivid",
                     r"\bpopulation", r"\bmarket"],
    },
    "setup": {
        "min_words": 15,
        "patterns": [r"\bsolv", r"\bvariable", r"\bformula", r"\bcalculat",
                     r"\bapproach", r"\brelationship", r"\bequation",
                     r"\bidentif"],
    },
    "sanity_check": {
        "min_words": 15,
        "patterns": [r"\bbenchmark", r"\bcompar", r"\breasonab", r"\bmagnitude",
                     r"\bcheck", r"\bverif", r"\balternativ", r"\bsmell",
                     r"\bknown\b", r"\bexpect"],
    },
    "sensitivity": {
        "min_words": 15,
        "patterns": [r"\bsensitiv", r"\bimpact", r"\bvary", r"\bchang",
                     r"\bassumption", r"\bdriver", r"\brange\b", r"\buncertain"],
    },
    "analyses": {
        "min_items": 2,
        "min_item_words": 6,
    },
    "updates": {
        "min_items": 1,
        "min_item_words": 8,
        "patterns": [r"\bstrengthen", r"\bweaken", r"\bconfirm", r"\breject",
                     r"\bsupport", r"\bchang", r"\bupdat", r"\brevis",
                     r"\binvalidat", r"\brevised"],
    },
    "clarifying_questions": {
        "min_items": 2,
        "min_item_words": 5,
    },
    "exhibit_interpretation": {
        "min_words": 15,
        "patterns": [r"\bbecause\b", r"\bdriv", r"\bkey\b", r"\binsight",
                     r"\btakeaway", r"\bimpl", r"\bshow", r"\bsuggest",
                     r"\bindicate", r"\bconfirm", r"\brule"],
    },
}


def _check_heuristic_rules(stage: str, texts: list[str]) -> tuple[bool, list[str]]:
    """Check heuristic rules for a stage. Returns (passed, failure_reasons)."""
    key_aliases = {"analyze": "analyses", "update": "updates", "conclude": "conclusion"}
    resolved = key_aliases.get(stage.lower(), stage.lower())
    rules = HEURISTIC_RULES.get(resolved, {})
    if not rules:
        return True, []

    failures: list[str] = []
    combined = " ".join(t.strip() for t in texts)
    word_count = len(combined.split())
    is_multi = len(texts) > 1 or resolved in {"assumptions", "hypotheses", "analyses",
                                                "updates", "calculation"}

    # Min words check (single-response stages)
    min_words = rules.get("min_words", 0)
    if min_words and not is_multi and word_count < min_words:
        failures.append(f"Response too brief ({word_count} words, minimum {min_words}).")

    # Min items check (multi-response stages)
    min_items = rules.get("min_items", 0)
    if min_items and len(texts) < min_items:
        failures.append(f"Too few items ({len(texts)}, minimum {min_items}).")

    # Min words per item (multi-response stages)
    min_item_words = rules.get("min_item_words", 0)
    if min_item_words and is_multi:
        for i, t in enumerate(texts):
            if len(t.split()) < min_item_words:
                failures.append(f"Item {i+1} is too brief ({len(t.split())} words, minimum {min_item_words}).")
                break  # Only flag the first short item

    # Required patterns check
    patterns = rules.get("patterns", [])
    if patterns:
        matched = any(_re.search(p, combined, _re.IGNORECASE) for p in patterns)
        if not matched:
            failures.append("Missing key terminology expected for this stage.")

    # Numbers required check (calculation)
    if rules.get("require_numbers"):
        has_numbers = any(_re.search(r"\d", t) for t in texts)
        if not has_numbers:
            failures.append("Calculation steps should include specific numbers.")

    return len(failures) == 0, failures


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

def _heuristic_feedback(stage: str, texts: list[str]) -> CoachFeedback:
    """Generate deterministic feedback based on heuristic rules.

    Uses structural checks (word count, keyword patterns, item counts)
    to provide a pass/fail gate even without an LLM.
    """
    passed, failures = _check_heuristic_rules(stage, texts)
    total_length = sum(len(t.strip()) for t in texts)

    # Strengths based on response length
    if total_length > 200:
        strengths = (
            "You provided a comprehensive response with a high level of detail. "
            "This depth suggests that you've considered multiple factors."
        )
    elif total_length > 80:
        strengths = (
            "Your response is fairly detailed and demonstrates structured thinking."
        )
    else:
        strengths = (
            "You have started to outline your thoughts. With more elaboration your reasoning could be clearer."
        )

    # Stage-specific gaps
    stage_key = stage.lower()
    gaps_map = {
        "framework": (
            "Have you chosen a framework that fits this specific problem type? "
            "Consider whether your framework covers the key dimensions of the case. "
            "A good framework choice should be justified — explain why this one fits better than alternatives."
        ),
        "restatement": (
            "Did you capture all the key elements of the problem? Check that you've identified the client, "
            "the core question, any constraints mentioned, and the desired outcome. "
            "If anything was unclear, note what clarifying questions you would ask the interviewer."
        ),
        "frame": (
            "Ensure you have clearly defined the objective, the key stakeholders and the metrics that matter. "
            "Consider whether you've chosen an appropriate framework (e.g., 3C's, 4P's, Porter's Five Forces, "
            "Profitability, SWOT) to organize your analysis. A clear structure prevents you from missing key areas."
        ),
        "assumptions": (
            "Check that each assumption is explicitly stated and justified. "
            "Distinguish between assumptions you've made (because data is unavailable) and facts given in the case. "
            "Flag any assumptions that, if wrong, would significantly change your analysis."
        ),
        "equation": (
            "Check that your equation captures the key drivers of the problem. "
            "Have you identified all the variables? Is the decomposition MECE "
            "(mutually exclusive, collectively exhaustive)? Consider whether a "
            "different equation structure might better capture the dynamics."
        ),
        "hypotheses": (
            "Check that your hypotheses cover different categories (e.g., customer, product, market, operations) "
            "and that they are mutually exclusive and collectively exhaustive where possible."
        ),
        "analyses": (
            "Be explicit about the analyses you would perform and why they matter. "
            "If you mention calculations, note the data required to perform them."
        ),
        "updates": (
            "Indicate which hypotheses were invalidated or strengthened by your analysis. "
            "Note any remaining uncertainties or assumptions."
        ),
        "conclusion": (
            "Ensure your recommendation logically follows from the analysis and addresses the original objective. "
            "Consider noting risks, trade-offs and next steps."
        ),
        "additional_insights": (
            "Think beyond what was directly asked. Consider implementation risks, second-order effects, "
            "competitive responses, organizational challenges, or adjacent opportunities the client should explore. "
            "Strong candidates show business judgment by surfacing issues the interviewer didn't explicitly raise."
        ),
        "structure": (
            "Have you clearly decomposed the problem into components? Check that your approach "
            "is either top-down or bottom-up and covers all major segments. Consider whether "
            "there are alternative structures that might capture more of the market."
        ),
        "setup": (
            "Have you clearly identified the key variables and their relationships? "
            "Check that your approach is structured before diving into calculations. "
            "Consider whether you've identified all the relevant data from the case."
        ),
        "calculation": (
            "Check each step of your calculation for consistency with your assumptions. "
            "Are your units correct throughout? Have you clearly shown your work so "
            "the interviewer can follow your reasoning?"
        ),
        "sanity_check": (
            "Does your final number pass the smell test? Try approaching the problem from "
            "a completely different angle to see if you get a similar magnitude. "
            "Consider per-capita, per-household, or percentage-of-GDP checks."
        ),
        "sensitivity": (
            "Which assumptions drive the largest changes in your result? "
            "Have you tested what happens when key inputs vary by +/- 50%? "
            "Consider which variables are most uncertain and most impactful."
        ),
        "clarifying_questions": (
            "Did your questions target the most critical unknowns? Consider asking about "
            "scope, constraints, timeline, success criteria, and competitive landscape. "
            "The best clarifying questions narrow the problem space and prevent solving the wrong case."
        ),
        "exhibit_interpretation": (
            "Did you lead with the headline insight, or just describe what the data shows? "
            "The 'so what' should be your first sentence. Then support it with specific "
            "data points and connect it to the case question."
        ),
    }
    key_aliases = {"analyze": "analyses", "update": "updates", "conclude": "conclusion"}
    resolved_key = key_aliases.get(stage_key, stage_key)
    gaps = gaps_map.get(
        resolved_key,
        "Consider expanding on your thought process and ensuring that all major aspects of the problem are addressed.",
    )

    # Stage-specific questions
    questions_map = {
        "framework": (
            "Why did you choose this framework over alternatives? "
            "Does it cover both the supply side and demand side of the problem?"
        ),
        "restatement": (
            "Have you identified who the client is and what they ultimately want to achieve? "
            "Are there any terms or concepts in the prompt you'd want the interviewer to clarify?"
        ),
        "frame": (
            "What decision is truly being made? What does success look like? "
            "Are there time constraints or specific metrics that leadership cares about? "
            "Which framework best fits this type of problem?"
        ),
        "assumptions": (
            "Which of your assumptions are most critical to the outcome? "
            "What would change if your key assumptions were off by 50%? "
            "Are there assumptions you can verify with data from the case?"
        ),
        "equation": (
            "Does your equation capture all the important levers? "
            "Could you decompose any of the variables further (e.g., Volume = Market Size x Market Share)? "
            "Which variable has the most uncertainty?"
        ),
        "hypotheses": (
            "Have you considered drivers from customer behaviour, market trends, internal capabilities and external factors?"
        ),
        "analyses": (
            "What data would validate or refute each hypothesis? "
            "Are there benchmarks or prior case examples you could compare against?"
        ),
        "updates": (
            "Which hypotheses now seem most plausible? "
            "What additional information would help you further narrow down the options?"
        ),
        "conclusion": (
            "What implementation challenges might arise? "
            "How would you measure the success of your recommendation over time?"
        ),
        "additional_insights": (
            "What could go wrong with your recommendation? How might competitors react? "
            "Are there regulatory, cultural, or organizational barriers to consider? "
            "What would you recommend the client monitor over the next 6-12 months?"
        ),
        "structure": (
            "Could you approach this estimation from a different angle (e.g., supply-side vs. demand-side)? "
            "Are there market segments you might be overlooking?"
        ),
        "setup": (
            "Have you identified all the variables you need? "
            "Is there a simpler way to set up the calculation that reduces the chance of error?"
        ),
        "calculation": (
            "Can you verify any intermediate results against known data points? "
            "Are there any shortcuts or approximations that could simplify your math?"
        ),
        "sanity_check": (
            "How does your estimate compare to publicly available data or industry benchmarks? "
            "What is the biggest source of uncertainty in your estimate?"
        ),
        "sensitivity": (
            "If the most uncertain assumption is off by 2x, does your conclusion change? "
            "Which variable would you want to research first to narrow the range?"
        ),
        "clarifying_questions": (
            "Are there any constraints or scope boundaries you haven't asked about? "
            "What would change your entire approach if the answer were different than expected?"
        ),
        "exhibit_interpretation": (
            "What second-order insight does this data suggest? "
            "How does this change your prioritization for the rest of the case?"
        ),
    }
    questions = questions_map.get(
        resolved_key,
        "What other perspectives or dimensions might enrich your reasoning?",
    )

    if failures:
        failure_text = "Your response did not meet the minimum requirements: " + "; ".join(failures)
        gaps = failure_text + "\n\n" + gaps

    return CoachFeedback(strengths=strengths, gaps=gaps, questions=questions, passed=passed)


# ---------------------------------------------------------------------------
# Stage hints (shown to users at beginner/intermediate difficulty)
# ---------------------------------------------------------------------------

STAGE_HINTS: dict[str, dict[str, str]] = {
    "framework": {
        "hint": "Pick the framework that best fits the problem type. Profitability for profit decline, 3C's for competitive strategy, Porter's Five Forces for industry analysis.",
        "structure": "Include:\n- **Framework:** [name]\n- **Why this framework:** [1-2 sentences on why it fits this problem better than alternatives]",
        "mbb_context": "MBB interviewers test whether you can choose the RIGHT tool for the job. Picking a generic framework signals weak business judgment. The best candidates match framework to problem type in under 30 seconds.",
        "example_standard": "I'll use a profitability framework.",
        "example_elite": "This is fundamentally a margin compression problem, so I'll use the Profitability framework — breaking the issue into Revenue (Price x Volume) and Costs (Fixed vs Variable). This lets me isolate whether the client's problem is demand-side or cost-side before going deeper.",
    },
    "restatement": {
        "hint": "Start by repeating the question back: Who is the client? What do they want to decide? What constraints did the prompt mention?",
        "structure": "Try this format:\n- **Client:** [who]\n- **Question:** [what they need to decide]\n- **Key constraints:** [time, budget, scope]\n- **Clarifying questions:** [anything unclear]",
        "mbb_context": "Every MBB case starts with restating the problem. Interviewers use this to test whether you can cut through noise and identify the REAL question. Getting this wrong means solving the wrong problem for 25 minutes.",
        "example_standard": "The client is a bank that wants to grow.",
        "example_elite": "Our client is a mid-size regional bank whose CEO wants to determine whether to invest in digital banking capabilities. The core question is: will this investment generate sufficient ROI within 3 years to justify the capital outlay, given competitive pressure from fintechs? I'd want to clarify: what's their current digital penetration, and is there a specific ROI threshold the board requires?",
    },
    "frame": {
        "hint": "Now apply your framework. Identify 2-4 key areas you'll analyze and explain which one you think matters most.",
        "structure": "A good frame includes:\n- **Key areas to analyze:** [2-4 buckets]\n- **Priority area:** [which one you'll investigate first and why]\n- **How they connect:** [which area drives the answer most]",
        "mbb_context": "Framing is where interviewers decide if you think like a consultant. A MECE structure (mutually exclusive, collectively exhaustive) shows you won't miss anything. The elite move is to state which bucket you'll attack FIRST and why — it shows you already have a hypothesis forming.",
        "example_standard": "I'll look at the market, competition, and internal capabilities.",
        "example_elite": "Using the 3C's, I'll structure my analysis into: (1) Customer — are digital banking needs growing and where; (2) Competition — what are fintechs offering that we aren't; (3) Capabilities — can we build or buy the technology. I'll start with Competition because if fintechs have already locked up the digital segment, the investment thesis changes entirely. Let me begin there.",
    },
    "assumptions": {
        "hint": "State what you're taking as given before doing math. Good assumptions are specific and testable (e.g., 'US population is 330M' not 'the market is big').",
        "structure": "For each assumption:\n- **Assumption:** [specific claim]\n- **Justification:** [why you believe it]\n- **Impact if wrong:** [high/medium/low]",
        "mbb_context": "Consultants live and die by assumptions. MBB interviewers want to see that you (1) know what you're assuming vs. what's fact, (2) can justify each assumption, and (3) understand which assumptions matter most. The elite move: flag which assumption you'd test first if you had real data.",
        "example_standard": "I assume the market is growing.",
        "example_elite": "I'm assuming: (1) US digital banking adoption is ~65% and growing at 8% annually — this is my highest-impact assumption because if adoption is plateauing, the market opportunity shrinks significantly. (2) Average customer acquisition cost for digital banking is ~$200, based on fintech benchmarks. I'd want to validate assumption #1 first because it determines whether we're entering a growing or mature market.",
    },
    "hypotheses": {
        "hint": "Form a testable guess about what's driving the problem. Use the language of proof: 'I hypothesize X. If true, we should see Y in the data. If false, I'll pivot to Z.'",
        "structure": "For each hypothesis:\n- **Hypothesis:** [specific, testable claim]\n- **What would confirm it:** [data or evidence]\n- **What would rule it out:** [contradicting evidence]\n- **If ruled out, pivot to:** [next branch]",
        "mbb_context": "Hypothesis-driven thinking is THE skill that separates MBB from other consulting. You're not exploring — you're testing. Elite candidates use 'ruling in/out' language: 'This data rules out X as the primary driver. I'm moving to Y.' If a branch yields nothing, kill it in 20 seconds and pivot.",
        "example_standard": "Maybe the problem is costs. Or maybe it's revenue.",
        "example_elite": "Hypothesis 1: The profit decline is driven by customer churn in the premium segment, not overall volume loss. If true, we should see premium segment revenue declining faster than mass market. If premium is stable, I'll rule out churn and pivot to pricing pressure.\n\nHypothesis 2: Rising input costs (not pricing) are compressing margins. If true, COGS as a % of revenue should be trending up over 3 years. If COGS is flat, I'm ruling out cost-side and focusing purely on the revenue story.",
    },
    "equation": {
        "hint": "Break the problem into a formula. Before calculating, pre-commit: 'If this variable is above X, I'll recommend A. If below, I'll recommend B.' This builds a decision bridge.",
        "structure": "Write your equation, then:\n- **Known variables:** [from the case]\n- **Variables to estimate:** [what you'll calculate]\n- **Pre-commitment:** [what the result means for your recommendation]",
        "mbb_context": "MBB interviewers want to see that your math has PURPOSE. Pre-commitment is the elite technique: before touching numbers, state what the result will mean. 'If margin exceeds 15%, I'll recommend expanding. If below 10%, I'll recommend restructuring.' This shows you're testing a decision, not just crunching numbers.",
        "example_standard": "Revenue = Price x Volume. Let me calculate the revenue.",
        "example_elite": "Profit = Revenue - Costs, where Revenue = Price x Volume and Costs = Fixed + Variable. Before I calculate: if the contribution margin is above 30%, this business is worth investing in and the problem is likely scale. If below 15%, we have a fundamental unit economics problem and I'll recommend restructuring before growth. Let me solve for contribution margin first.",
    },
    "structure": {
        "hint": "Choose top-down (start big, subdivide) or bottom-up (start small, multiply up). State your approach before calculating.",
        "structure": "Outline your approach:\n- **Method:** [top-down or bottom-up]\n- **Starting point:** [your anchor number]\n- **Steps:** [how you'll break it down]\n- **Pre-commitment:** [what range would surprise you and why]",
        "mbb_context": "In market-sizing cases, the structure IS the answer. MBB interviewers care less about the exact number and more about whether your decomposition is logical and MECE. The elite move: state your expected range before calculating, then check if your answer lands in it.",
        "example_standard": "I'll use a top-down approach starting with population.",
        "example_elite": "I'll use a top-down approach: US population (330M) → % who are pet owners (~67%) → average annual pet food spend → total market. Before calculating: I'd expect the US pet food market to be somewhere between $30B and $60B — if my estimate falls outside that range, I'll know I've made an error in my segmentation and will re-examine my assumptions.",
    },
    "setup": {
        "hint": "Before calculating, map out what you're solving for and what variables you need. Pre-commit to what the answer means for the decision.",
        "structure": "Set up clearly:\n- **Solving for:** [the target quantity]\n- **Key formula:** [relationship between variables]\n- **Data from case:** [numbers you were given]\n- **Pre-commitment:** [what the result means for the recommendation]",
        "mbb_context": "Setting up the problem cleanly prevents arithmetic errors and shows structured thinking. The elite move is pre-commitment: 'If break-even is under 10K units, this is viable. Above 50K, we should walk away.' You've built the decision bridge before you know the answer.",
        "example_standard": "I need to find the break-even point. Break-even = Fixed Costs / Contribution Margin.",
        "example_elite": "I'm solving for the break-even volume in units. Break-even = Fixed Costs / (Price - Variable Cost). From the case: Fixed Costs = $500K, Variable Cost = $20/unit. Before I solve: if break-even is under 10,000 units, this product is clearly viable given the client's distribution capacity of 50K units. If it's above 30,000, we have a problem. Let me calculate.",
    },
    "calculation": {
        "hint": "Show every step. Label units. After each result, state what it MEANS: 'This rules out X' or 'This confirms my hypothesis about Y.'",
        "structure": "For each step:\n- **Step N:** [what you're calculating]\n- **Math:** [the actual computation]\n- **Result:** [answer with units]\n- **So what:** [what this means for the case]",
        "mbb_context": "MBB interviewers don't care about mental math speed — they care about structured logic. After each calculation step, the elite move is to interpret the result: 'Revenue of $12M rules out market growth as the driver — we're clearly losing share.' Every number should advance your argument.",
        "example_standard": "Revenue = 1000 x $50 = $50,000",
        "example_elite": "Step 1: Market revenue = 100K customers x $120 avg spend = $12M. Step 2: Our share = $3M / $12M = 25%. This is actually healthy — it rules out market positioning as the primary issue. The problem must be on the cost side. Let me calculate margin next to confirm.",
    },
    "sanity_check": {
        "hint": "Don't just give one number — give a sanity RANGE. 'My estimate is $500M, with a range of $300M-$700M. The upside assumes X; the downside assumes Y.'",
        "structure": "Check your work:\n- **Your estimate:** [final number]\n- **Sanity range:** [low end — high end]\n- **What drives the range:** [key variable causing the spread]\n- **Cross-check:** [alternative approach or known benchmark]",
        "mbb_context": "The Sanity Range Trick separates good from great. Instead of defending a single number, give a confidence interval: '$500M estimate, sanity range $300M-$700M. The upside assumes a 20% premium on organic products.' This shows you understand the sensitivity of your assumptions and aren't overconfident in a point estimate.",
        "example_standard": "My estimate of 200K coffee shops seems about right.",
        "example_elite": "My estimate is 200K coffee shops. Sanity range: 150K to 280K. The lower bound assumes I'm overestimating rural density; the upper bound includes non-traditional locations (gas stations, grocery). Cross-check: Starbucks has ~16K locations and roughly 8% market share, implying ~200K total — right in my range. I'm confident in the $200K estimate.",
    },
    "sensitivity": {
        "hint": "Identify the 2-3 variables that swing the answer most. Show the range of outcomes and state which variable you'd research first.",
        "structure": "For each key variable:\n- **Variable:** [name]\n- **Base case:** [your assumption]\n- **Upside / downside:** [what happens if ±50%]\n- **Decision impact:** [does the recommendation change?]",
        "mbb_context": "Sensitivity analysis shows you understand that business decisions happen under uncertainty. The elite move: after testing variables, state clearly which ones change the decision. 'If customer acquisition cost doubles, the project NPV goes negative — this is the kill variable we need to validate before committing.'",
        "example_standard": "If costs go up, profit goes down.",
        "example_elite": "The three highest-impact variables: (1) Customer acquisition cost: at $200 (base), NPV = $2M. At $400, NPV goes negative — this is the kill variable. (2) Retention rate: 85% base → $2M NPV. At 70%, NPV drops to $0.5M — still positive, so retention is important but not decisive. (3) ARPU: base $50. Even at $35 (-30%), NPV stays positive. Conclusion: the decision hinges on acquisition cost. I'd recommend validating this with a small pilot before full rollout.",
    },
    "conclusion": {
        "hint": "Lead with a clear one-sentence recommendation. Support with 2-3 reasons. Acknowledge the key risk. Use decisive language: 'I recommend X because Y.'",
        "structure": "Structure your answer:\n- **Recommendation:** [clear, one-sentence answer]\n- **Supporting reasons:** [2-3 key points from your analysis]\n- **Key risk:** [what could make this wrong]\n- **Next steps:** [what you'd investigate further]",
        "mbb_context": "The conclusion is your 'elevator pitch' to the CEO. MBB partners want a clear, decisive recommendation — not a wishy-washy 'it depends.' The elite move: tie your recommendation back to the data. 'The 25% margin and $12M market confirm this is worth pursuing. The key risk is acquisition cost, which I'd validate with a 90-day pilot.'",
        "example_standard": "I think the company should probably consider expanding into digital banking.",
        "example_elite": "I recommend the client invest $5M in digital banking capabilities over 18 months. Three reasons: (1) the digital segment is growing at 15% vs 2% for traditional — we're ceding share to fintechs by not competing; (2) our analysis shows positive unit economics with break-even at 8K customers, well within reach given our 50K existing base; (3) the competitive window is narrowing — two more quarters of inaction and fintechs will have locked up the segment. Key risk: customer acquisition cost. I'd validate with a 3-month pilot in two metro markets before full rollout.",
    },
    "additional_insights": {
        "hint": "Go beyond the question. Think about: How would competitors react? What could go wrong during implementation? Are there adjacent opportunities?",
        "structure": "Consider:\n- **Implementation risks:** [what could go wrong]\n- **Competitive response:** [how rivals might react]\n- **Adjacent opportunities:** [related ideas worth exploring]\n- **Timeline considerations:** [short vs. long term]",
        "mbb_context": "This stage separates 'good' from 'partner-track' candidates. MBB interviewers want to see that you can zoom out from the immediate problem and think about second-order effects, competitive dynamics, and implementation realities. The elite move: identify the one thing that could kill the deal that nobody asked about.",
        "example_standard": "The company should also think about risks and opportunities.",
        "example_elite": "Three things the board should consider beyond our core recommendation: (1) Competitive response — if we launch digital, expect incumbent banks to respond within 6 months. We need a 'fast follower' defense plan. (2) Regulatory risk — digital banking regulations are tightening in 3 states; we should build compliance into the MVP, not bolt it on later. (3) Adjacent opportunity — our digital platform could serve as a distribution channel for insurance products, potentially adding $2-3M in year-2 revenue that isn't in our base case.",
    },
    "clarifying_questions": {
        "hint": "Ask 2-3 questions that target scope, constraints, or ambiguity. Good questions: 'What's the timeline for this decision?' 'Are there budget constraints?' 'Who are the key competitors?'",
        "structure": "Strong clarifying questions target:\n- **Scope:** What exactly are we optimizing for?\n- **Constraints:** Budget, timeline, regulatory limits?\n- **Context:** Market dynamics, competitive landscape?\n- **Success criteria:** How will the client measure success?",
        "mbb_context": "Every real MBB case starts with 2-3 clarifying questions. This is your first chance to show structured thinking. Interviewers EXPECT you to ask — jumping straight to a framework without clarifying signals inexperience. The best candidates ask questions that narrow the problem space and prevent solving the wrong case.",
        "example_standard": "Can you tell me more about the company? What industry are they in?",
        "example_elite": "Before I structure my approach, I'd like to clarify three things: (1) What's the decision timeline — is this a board-level decision for next quarter, or a longer-term strategic review? (2) Are there hard constraints on capital expenditure, or is the budget flexible if the ROI case is strong? (3) When you say 'growth,' are we optimizing for revenue growth, profit growth, or market share? These have very different strategic implications.",
    },
    "exhibit_interpretation": {
        "hint": "Lead with the 'so what' — not 'this chart shows margins by region.' Instead: 'Region B is subsidizing losses in Region A.' Support with 1-2 specific data points.",
        "structure": "Use this format:\n- **Headline:** [one-sentence takeaway]\n- **Key data points:** [2-3 specific numbers that support it]\n- **Implication for the case:** [how this changes your analysis]",
        "mbb_context": "Visual Literacy is a core MBB skill. Interviewers hand you an exhibit and watch HOW you read it. Average candidates describe what they see ('this shows revenue by segment'). Elite candidates lead with the insight ('Segment B is growing 3x faster than A, which means our growth story is actually a concentration risk'). The first sentence should always be the takeaway.",
        "example_standard": "This table shows revenue and growth by segment. The mass market has the most revenue.",
        "example_elite": "The key insight is that HNW customers are growing at 8% vs 1% for mass market — despite being the smallest segment. This tells me the growth opportunity is in HNW, not mass market. If we're allocating resources proportionally to current revenue, we're under-investing in our fastest-growing segment. I'd want to shift the analysis toward HNW economics and capacity.",
    },
}


# ---------------------------------------------------------------------------
# MBB Pro Tips (shown at intermediate/advanced alongside examples)
# ---------------------------------------------------------------------------

MBB_PRO_TIPS: dict[str, str] = {
    "hypotheses": (
        "**Elite technique — Language of Proof:** Don't just 'look at' data. "
        "Use it to RULE IN or RULE OUT branches. Say: 'This data rules out X "
        "as the primary driver. I'm moving to Y.' If a branch yields nothing, "
        "kill it in 20 seconds and pivot."
    ),
    "equation": (
        "**Elite technique — Pre-Commitment:** Before touching a calculator, "
        "tell the interviewer what the result will MEAN. 'If margin exceeds 15%, "
        "I'll recommend expanding. If below 10%, I'll recommend restructuring.' "
        "This builds a decision bridge before you know the answer."
    ),
    "calculation": (
        "**Elite technique — Interpret Every Number:** After each calculation, "
        "state what it means: 'Revenue of $12M rules out market decline — "
        "we're losing share.' Every number should advance your argument, "
        "not just sit on the page."
    ),
    "sanity_check": (
        "**Elite technique — Sanity Range:** Don't defend one number. Give a "
        "confidence interval: '$500M estimate, range $300M-$700M.' This shows "
        "you understand the sensitivity of your assumptions."
    ),
    "conclusion": (
        "**Elite technique — Headline First:** Lead with the recommendation "
        "like an executive summary. 'I recommend X because Y.' Not 'After "
        "considering many factors, it seems like maybe we should...' "
        "Be decisive."
    ),
}
