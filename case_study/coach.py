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
    "frame": (
        "The user must: (1) choose and name a specific framework or structure, "
        "(2) explain why it fits this problem, (3) outline the key areas or "
        "buckets they will analyze. Vague or unstructured answers = not passed."
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
) -> DataReveal | None:
    """Generate an interviewer data reveal after the given stage.

    Returns ``None`` if the stage doesn't warrant a reveal, AI is not
    enabled, or the API call fails.  Beginner difficulty skips reveals
    entirely; intermediate only triggers on a subset of stages.
    """
    if stage not in DATA_REVEAL_STAGES:
        return None
    if not _GEMINI_API_KEY:
        return None
    # Beginner: no curveballs
    if difficulty == "beginner":
        return None
    # Intermediate: only reveal after calculation (the most impactful stage)
    if difficulty == "intermediate" and stage != "calculation":
        return None

    if isinstance(content, str):
        texts = [content]
    else:
        texts = list(content)

    try:
        return _gemini_data_reveal(stage, texts, case_context)
    except Exception:
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


def _gemini_data_reveal(stage: str, texts: list[str], case_context: str) -> DataReveal:
    """Call Gemini to generate an interviewer data reveal."""
    from google import genai

    client = genai.Client(api_key=_GEMINI_API_KEY)

    reveal_guidance = DATA_REVEAL_STAGES.get(stage, "")
    user_input = "\n".join(texts) if len(texts) > 1 else texts[0]
    prompt = (
        f"{DATA_REVEAL_PROMPT}\n\n"
        f"Case context:\n{case_context}\n\n"
        f"Stage just completed: {stage}\n"
        f"Reveal guidance: {reveal_guidance}\n\n"
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
# Heuristic fallback (always passes — cannot meaningfully evaluate)
# ---------------------------------------------------------------------------

def _heuristic_feedback(stage: str, texts: list[str]) -> CoachFeedback:
    """Generate deterministic feedback based on input length and stage.

    The heuristic backend always sets ``passed=True`` because it cannot
    meaningfully evaluate response quality without an LLM.
    """
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
    }
    key_aliases = {"analyze": "analyses", "update": "updates", "conclude": "conclusion"}
    resolved_key = key_aliases.get(stage_key, stage_key)
    gaps = gaps_map.get(
        resolved_key,
        "Consider expanding on your thought process and ensuring that all major aspects of the problem are addressed.",
    )

    # Stage-specific questions
    questions_map = {
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
    }
    questions = questions_map.get(
        resolved_key,
        "What other perspectives or dimensions might enrich your reasoning?",
    )

    return CoachFeedback(strengths=strengths, gaps=gaps, questions=questions, passed=True)


# ---------------------------------------------------------------------------
# Stage hints (shown to users at beginner/intermediate difficulty)
# ---------------------------------------------------------------------------

STAGE_HINTS: dict[str, dict[str, str]] = {
    "restatement": {
        "hint": "Start by repeating the question back: Who is the client? What do they want to decide? What constraints did the prompt mention?",
        "structure": "Try this format:\n- **Client:** [who]\n- **Question:** [what they need to decide]\n- **Key constraints:** [time, budget, scope]\n- **Clarifying questions:** [anything unclear]",
    },
    "frame": {
        "hint": "Pick a framework that fits the problem type. For growth questions, think revenue vs. cost. For market entry, think market attractiveness vs. competitive position.",
        "structure": "A good frame includes:\n- **Framework chosen:** [name and why]\n- **Key areas to analyze:** [2-4 buckets]\n- **How they connect:** [which area drives the answer most]",
    },
    "assumptions": {
        "hint": "State what you're taking as given before doing math. Good assumptions are specific and testable (e.g., 'US population is 330M' not 'the market is big').",
        "structure": "For each assumption:\n- **Assumption:** [specific claim]\n- **Justification:** [why you believe it]\n- **Impact if wrong:** [high/medium/low]",
    },
    "hypotheses": {
        "hint": "Form a testable guess about what's driving the problem. For example: 'I hypothesize that revenue decline is driven by pricing pressure rather than volume loss.' Good hypotheses are specific and can be confirmed or refuted with data.",
        "structure": "For each hypothesis:\n- **Hypothesis:** [specific, testable claim]\n- **Category:** [demand/supply/internal/external]\n- **How to test:** [what data or analysis would confirm or refute it]\n- **Why it matters:** [impact if true]",
    },
    "equation": {
        "hint": "Break the problem into a formula. For example, Profit = Revenue - Cost, or Revenue = Price x Volume. Which variables do you know vs. need to estimate?",
        "structure": "Write your equation, then list:\n- **Known variables:** [from the case]\n- **Variables to estimate:** [what you'll calculate]\n- **Key driver:** [which variable matters most]",
    },
    "structure": {
        "hint": "Choose top-down (start big, subdivide) or bottom-up (start small, multiply up). Top-down example: US population → % in cities → % who drink coffee → cups per day.",
        "structure": "Outline your approach:\n- **Method:** [top-down or bottom-up]\n- **Starting point:** [your anchor number]\n- **Steps:** [how you'll break it down]\n- **Segments:** [any key splits like urban/rural]",
    },
    "setup": {
        "hint": "Before calculating, map out what you're solving for and what variables you need. Think of it like setting up an algebra problem before solving.",
        "structure": "Set up clearly:\n- **Solving for:** [the target quantity]\n- **Key formula:** [relationship between variables]\n- **Data from case:** [numbers you were given]\n- **Approach:** [step-by-step plan]",
    },
    "calculation": {
        "hint": "Show every step of your math. Label your units. Round to keep numbers manageable — interviewers care about the approach more than decimal precision.",
        "structure": "For each step:\n- **Step N:** [what you're calculating]\n- **Math:** [the actual computation]\n- **Result:** [intermediate answer with units]",
    },
    "sanity_check": {
        "hint": "Compare your answer to something you know. If you estimated 1M coffee shops in the US but Starbucks has 16K, that's a red flag. Try a completely different approach to see if you get a similar number.",
        "structure": "Check your work:\n- **Your estimate:** [final number]\n- **Benchmark:** [a known data point to compare against]\n- **Alternative approach:** [quick back-of-envelope from a different angle]\n- **Assessment:** [reasonable / too high / too low]",
    },
    "sensitivity": {
        "hint": "Which of your assumptions would change the answer most if they were wrong? Try varying your top 2-3 assumptions by +/- 50% and see what happens.",
        "structure": "For each key variable:\n- **Variable:** [name]\n- **Base case:** [your assumption]\n- **If +50%:** [new result]\n- **If -50%:** [new result]\n- **Conclusion:** [which variable matters most]",
    },
    "conclusion": {
        "hint": "State your recommendation clearly and back it up. A great conclusion has: (1) the answer, (2) the top 2-3 reasons, (3) one key risk.",
        "structure": "Structure your answer:\n- **Recommendation:** [clear, one-sentence answer]\n- **Supporting reasons:** [2-3 key points from your analysis]\n- **Key risk:** [what could make this wrong]\n- **Next steps:** [what you'd investigate further]",
    },
    "additional_insights": {
        "hint": "Go beyond the question. Think about: How would competitors react? What could go wrong during implementation? Are there adjacent opportunities?",
        "structure": "Consider:\n- **Implementation risks:** [what could go wrong]\n- **Competitive response:** [how rivals might react]\n- **Adjacent opportunities:** [related ideas worth exploring]\n- **Timeline considerations:** [short vs. long term]",
    },
}
