"""
Core logic for running a case study session.

The engine orchestrates the user through a category-specific sequence
of reasoning stages.  Strategy cases use a 9-stage loop with
framework selection, hypothesis-driven reasoning and quantitative
analysis.  Market-sizing cases follow a 7-stage flow and
quantitative cases a 6-stage flow.

It interacts with the CLI, prompts for user input, validates
responses, optionally invokes the AI coach, and persists the session
state after each stage.
"""

from __future__ import annotations

import json
import time as _time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import cases, coach, validation
from .session import Session


FRAMEWORKS_FILE = Path(__file__).resolve().parent.parent / "data" / "frameworks.json"

# ---------------------------------------------------------------------------
# Stage definitions – each stage is described declaratively so the main
# run loop can handle them uniformly without per-stage if/elif branches.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StageSpec:
    """Declarative description of a single reasoning stage."""

    name: str
    prompt: str
    multi: bool = False
    item_name: str = ""
    preamble: tuple[str, ...] = ()
    offer_frameworks: bool = False


# ---- Individual stage specs ------------------------------------------------

_restatement = StageSpec(
    name="restatement",
    prompt="Restate the problem:\n> ",
    preamble=(
        "Before diving in, restate the problem in your own words.",
        "This confirms your understanding and highlights any clarifying questions.",
    ),
)

_clarifying_questions = StageSpec(
    name="clarifying_questions",
    prompt="",
    multi=True,
    item_name="Clarifying Question",
    preamble=(
        "What clarifying questions would you ask the interviewer before structuring?",
        "Good clarifying questions show you understand the problem and prevent solving the wrong case.",
    ),
)

_exhibit_interpretation = StageSpec(
    name="exhibit_interpretation",
    prompt="What is the key headline takeaway from this exhibit? Lead with the 'so what.'\n> ",
    preamble=(
        "The interviewer has shared a data exhibit.",
        "State the headline insight — what does this data tell us?",
        "Lead with the conclusion, then support with 1-2 data points.",
    ),
)

_framework = StageSpec(
    name="framework",
    prompt="Which framework will you use for this problem?\n> ",
    offer_frameworks=True,
    preamble=(
        "Select a framework to structure your analysis.",
        "Choose the one that best fits the problem type.",
    ),
)

_frame = StageSpec(
    name="frame",
    prompt="How will you apply your chosen framework to structure this problem?\n> ",
    preamble=(
        "Now explain how you'll apply your framework.",
        "Outline the key areas or buckets you'll analyze and why they matter.",
    ),
)

_assumptions = StageSpec(
    name="assumptions",
    prompt="",
    multi=True,
    item_name="Assumption",
    preamble=(
        "State and justify your key assumptions before proceeding.",
        "e.g., 'I assume US population of 330M' or 'I assume no competitor response in year 1.'",
    ),
)

_equation = StageSpec(
    name="equation",
    prompt="Break the problem into a quantitative equation:\n> ",
    preamble=(
        "Express the key relationship as an equation.",
        "e.g., Revenue = Price x Volume, or Profit = Revenue - Costs.",
        "Identify which variables you need to estimate or calculate.",
    ),
)

_hypotheses = StageSpec(
    name="hypotheses",
    prompt="",
    multi=True,
    item_name="Hypothesis",
    preamble=("Enter one possible explanation or strategic path.",),
)

_analyses = StageSpec(
    name="analyses",
    prompt="",
    multi=True,
    item_name="Analysis",
    preamble=("What analysis would you perform?",),
)

_updates = StageSpec(
    name="updates",
    prompt="",
    multi=True,
    item_name="Update",
    preamble=("How do your hypotheses change based on your analysis?",),
)

_conclusion = StageSpec(
    name="conclusion",
    prompt="What is your recommendation?\n> ",
)

_additional_insights = StageSpec(
    name="additional_insights",
    prompt="Additional insights:\n> ",
    preamble=(
        "Go beyond the case: what additional considerations, risks, or opportunities",
        "should the client think about that were not directly asked?",
    ),
)

_structure = StageSpec(
    name="structure",
    prompt="How will you structure this estimation? Break it into components:\n> ",
    preamble=(
        "Before calculating, decompose the problem into logical components.",
        "Choose a top-down or bottom-up approach and outline the key segments.",
    ),
)

_setup = StageSpec(
    name="setup",
    prompt="Set up the problem: what are you solving for and what is your approach?\n> ",
    preamble=(
        "Clearly define what quantity you are solving for.",
        "Identify the key variables, relationships, and your calculation approach.",
    ),
)

_calculation = StageSpec(
    name="calculation",
    prompt="",
    multi=True,
    item_name="Calculation Step",
    preamble=(
        "Work through your calculations step by step.",
        "Show your work clearly so the interviewer can follow your reasoning.",
    ),
)

_sanity_check = StageSpec(
    name="sanity_check",
    prompt="Sanity-check your estimate. Does it pass the smell test?\n> ",
    preamble=(
        "Compare your result to a known benchmark or try an alternative approach.",
        "Assess whether the magnitude is reasonable.",
    ),
)

_sensitivity = StageSpec(
    name="sensitivity",
    prompt="Which assumptions most affect your answer? How sensitive is the result?\n> ",
    preamble=(
        "Identify the 2-3 assumptions with the largest impact on your result.",
        "Show how varying them changes the output and discuss the range of outcomes.",
    ),
)

# ---- Category-specific stage sequences ------------------------------------

STRATEGY_STAGES: tuple[StageSpec, ...] = (
    _restatement, _clarifying_questions, _framework, _frame, _assumptions,
    _hypotheses, _equation, _calculation, _conclusion, _additional_insights,
)

MARKET_SIZING_STAGES: tuple[StageSpec, ...] = (
    _restatement, _clarifying_questions, _framework, _structure,
    _assumptions, _calculation, _sanity_check, _conclusion,
)

QUANTITATIVE_STAGES: tuple[StageSpec, ...] = (
    _restatement, _clarifying_questions, _setup, _assumptions,
    _calculation, _sensitivity, _conclusion,
)

STAGES_BY_CATEGORY: dict[str, tuple[StageSpec, ...]] = {
    "strategy": STRATEGY_STAGES,
    "market-sizing": MARKET_SIZING_STAGES,
    "quantitative": QUANTITATIVE_STAGES,
}

# Default for backward compatibility
STAGES = STRATEGY_STAGES
STAGE_NAMES: tuple[str, ...] = tuple(s.name for s in STAGES)

# All unique specs across every category (for field classification).
_ALL_SPECS = {s.name: s for stages in STAGES_BY_CATEGORY.values() for s in stages}
_SINGLE_FIELDS = frozenset(name for name, s in _ALL_SPECS.items() if not s.multi)
_MULTI_FIELDS = frozenset(name for name, s in _ALL_SPECS.items() if s.multi)


def get_stages_for_category(category: str) -> tuple[StageSpec, ...]:
    """Return the stage sequence for the given case category."""
    return STAGES_BY_CATEGORY.get(category, STRATEGY_STAGES)


def get_stages_with_exhibit(
    category: str, case_data: dict[str, Any] | None = None,
) -> tuple[StageSpec, ...]:
    """Return stages with exhibit_interpretation inserted if case has an exhibit.

    If the case data includes an ``exhibit`` key with an ``appears_after``
    field, the exhibit interpretation stage is inserted right after that stage.
    """
    stages = list(get_stages_for_category(category))
    if not case_data or "exhibit" not in case_data:
        return tuple(stages)
    exhibit = case_data["exhibit"]
    after_stage = exhibit.get("appears_after", "frame")
    for i, s in enumerate(stages):
        if s.name == after_stage:
            stages.insert(i + 1, _exhibit_interpretation)
            break
    return tuple(stages)


def check_time_expired(sess: Session, difficulty: str = "advanced") -> bool:
    """Return True if total elapsed time exceeds the case limit at advanced difficulty."""
    if difficulty != "advanced":
        return False
    total_elapsed = sum(sess.stage_times.values())
    limit = TOTAL_CASE_TIME_LIMIT.get(sess.category, 1500)
    return total_elapsed > limit


# ---------------------------------------------------------------------------
# Stage time targets (seconds) for a 25-minute case interview
# ---------------------------------------------------------------------------

STAGE_TIME_LIMITS: dict[str, dict[str, int]] = {
    "strategy": {
        "restatement": 120,           # 2 min
        "clarifying_questions": 90,   # 1.5 min
        "framework": 120,             # 2 min
        "frame": 150,                 # 2.5 min
        "assumptions": 120,           # 2 min
        "hypotheses": 180,            # 3 min
        "equation": 150,              # 2.5 min
        "calculation": 240,           # 4 min
        "conclusion": 210,            # 3.5 min
        "additional_insights": 120,   # 2 min
        "exhibit_interpretation": 90, # 1.5 min
    },
    "market-sizing": {
        "restatement": 120,           # 2 min
        "clarifying_questions": 90,   # 1.5 min
        "framework": 120,             # 2 min
        "structure": 150,             # 2.5 min
        "assumptions": 150,           # 2.5 min
        "calculation": 420,           # 7 min
        "sanity_check": 240,          # 4 min
        "conclusion": 150,            # 2.5 min
        "exhibit_interpretation": 90, # 1.5 min
    },
    "quantitative": {
        "restatement": 120,           # 2 min
        "clarifying_questions": 90,   # 1.5 min
        "setup": 210,                 # 3.5 min
        "assumptions": 150,           # 2.5 min
        "calculation": 420,           # 7 min
        "sensitivity": 270,           # 4.5 min
        "conclusion": 210,            # 3.5 min
        "exhibit_interpretation": 90, # 1.5 min
    },
}

# Total case time limit (seconds) — used for hard time pressure at advanced
TOTAL_CASE_TIME_LIMIT: dict[str, int] = {
    "strategy": 1500,       # 25 min
    "market-sizing": 1500,  # 25 min
    "quantitative": 1500,   # 25 min
}


def get_stage_time_limit(category: str, stage_name: str) -> int:
    """Return the target time in seconds for a stage, or 180 as default."""
    return STAGE_TIME_LIMITS.get(category, {}).get(stage_name, 180)


def format_time_warning(elapsed_seconds: float, target_seconds: int) -> str | None:
    """Return a warning string if the stage took too long, else None."""
    if elapsed_seconds <= target_seconds:
        return None
    e_min, e_sec = divmod(int(elapsed_seconds), 60)
    t_min, t_sec = divmod(target_seconds, 60)
    elapsed_str = f"{e_min}:{e_sec:02d}"
    target_str = f"{t_min}:{t_sec:02d}"
    ratio = elapsed_seconds / target_seconds
    if ratio > 1.5:
        severity = "WARNING"
    else:
        severity = "NOTE"
    return f"{severity}: This stage took {elapsed_str} -- target pace is {target_str}. In a real interview, manage time carefully."


def _is_stage_complete(value: object) -> bool:
    """Return True if a stage field has been filled in."""
    return value is not None and value != "" and value != []


def load_frameworks() -> list[dict[str, Any]]:
    """Load the business frameworks reference from the data directory."""
    if FRAMEWORKS_FILE.exists():
        with FRAMEWORKS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []


def display_frameworks() -> None:
    """Print a summary of available business frameworks."""
    frameworks = load_frameworks()
    if not frameworks:
        return
    print("\nAVAILABLE FRAMEWORKS FOR REFERENCE:")
    for fw in frameworks:
        print(f"  {fw['name']} ({fw['full_name']})")
        print(f"    {fw['description'][:100]}...")
    print()


def choose_case(cases_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prompt the user to select a case from the provided list.

    The cases are displayed with an index and ID.  The user may
    select by entering either the index or the case identifier.
    Returns the chosen case dictionary or ``None`` if no valid choice
    is made.
    """
    if not cases_list:
        print("No cases available.")
        return None
    print("Available cases:")
    for idx, c in enumerate(cases_list, start=1):
        print(f"  {idx}. {c['id']} – {c['prompt'][:60]}...")
    while True:
        choice = input("Select a case by number or ID (or 'q' to cancel): ").strip()
        if choice.lower() == "q":
            return None
        # Try numeric index
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(cases_list):
                return cases_list[index]
        # Try case id
        selected = next((c for c in cases_list if c["id"] == choice), None)
        if selected:
            return selected
        print("Invalid selection. Please try again.")


def ask_yes_no(prompt: str) -> bool:
    """Prompt the user for a yes/no answer returning True for yes."""
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer 'y' or 'n'.")


def prompt_for_stage(prompt_text: str) -> str:
    """Prompt the user for a free-form response and validate it."""
    while True:
        response = input(prompt_text).rstrip()
        result = validation.validate_response(response)
        if not result.accepted:
            print(result.message)
            continue
        if result.short:
            # Ask if user wants to expand
            expand = ask_yes_no(f"{result.message} Would you like to expand your reasoning? (y/n) ")
            if expand:
                continue
        return response


def prompt_for_multi_items(item_name: str) -> list[str]:
    """Prompt the user to enter multiple items (hypotheses, analyses or updates)."""
    items: list[str] = []
    count = 1
    while True:
        prompt = f"{item_name} {count}:\n> "
        response = input(prompt).rstrip()
        result = validation.validate_multi_item(response)
        if not result.accepted:
            print(result.message)
            continue
        if result.short:
            expand = ask_yes_no(f"{result.message} Would you like to expand your reasoning? (y/n) ")
            if expand:
                continue
        items.append(response)
        count += 1
        more = ask_yes_no(f"Add another {item_name.lower()}? (y/n) ")
        if not more:
            break
    return items


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

def _run_stage(
    spec: StageSpec,
    sess: Session,
    coach_enabled: bool,
    case_context: str = "",
    difficulty: str = "advanced",
) -> None:
    """Execute a single stage: print preamble, collect input, save, offer coach.

    When coach mode is enabled and the AI backend is available, the
    stage acts as a gate — the user must revise and resubmit until
    the coach marks the response as passed.  With the heuristic
    fallback the stage always passes on the first attempt.

    After a stage passes, a mid-case data reveal may be generated and
    printed to simulate an interviewer sharing new information.
    """
    ai_gating = coach_enabled and coach.is_ai_enabled()
    stage_start = _time.time()

    for line in spec.preamble:
        print(line)

    if spec.offer_frameworks:
        if ask_yes_no("Would you like to see a list of common business frameworks? (y/n) "):
            display_frameworks()

    while True:
        if spec.multi:
            value = prompt_for_multi_items(spec.item_name)
        else:
            value = prompt_for_stage(spec.prompt)

        setattr(sess, spec.name, value)
        sess.save()

        if not coach_enabled:
            break

        # Always evaluate when AI gating is on; otherwise ask
        if ai_gating or ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
            feedback = coach.provide_feedback(spec.name, value, case_context, difficulty)
            print("\n" + feedback.format_for_cli() + "\n")
            if feedback.passed:
                break
            # Not passed — loop back for revision
            print("Revise your response and try again.\n")
        else:
            break

    # Record stage timing
    elapsed = _time.time() - stage_start
    sess.stage_times[spec.name] = elapsed
    target = get_stage_time_limit(sess.category, spec.name)
    warning = format_time_warning(elapsed, target)
    if warning:
        print(f"\n{warning}")

    # Mid-case data reveal
    reveal = coach.generate_data_reveal(spec.name, value, case_context, difficulty, case_data=None)
    if reveal and reveal.reveal:
        print(f"\n--- INTERVIEWER ({reveal.reveal_type.upper()}) ---")
        print(reveal.reveal)
        print("---\n")


def run_session(
    sess: Session,
    coach_enabled: bool,
    case_context: str = "",
    difficulty: str = "advanced",
    case_data: dict[str, Any] | None = None,
) -> None:
    """Interactively run through the remaining stages of the session."""
    stages = get_stages_with_exhibit(sess.category, case_data)

    # Find the first incomplete stage
    start_index: int | None = None
    for i, spec in enumerate(stages):
        if not _is_stage_complete(getattr(sess, spec.name)):
            start_index = i
            break

    if start_index is None:
        print("This session is already complete.")
        return

    # Find conclusion stage index for time-expired skip
    conclusion_idx = next(
        (i for i, s in enumerate(stages) if s.name == "conclusion"), len(stages) - 1
    )

    for i, spec in enumerate(stages[start_index:], start=start_index):
        # Hard time pressure at advanced: skip to conclusion
        if check_time_expired(sess, difficulty) and spec.name != "conclusion":
            if i < conclusion_idx:
                print(f"\nTIME'S UP — In a real interview, you'd need to wrap up now.")
                print("Skipping to conclusion.\n")
                sess.time_expired = True
                sess.forced_conclusion = True
                # Skip to conclusion
                for skip_spec in stages[i:conclusion_idx]:
                    if not _is_stage_complete(getattr(sess, skip_spec.name)):
                        setattr(sess, skip_spec.name, "[Time expired — skipped]" if not skip_spec.multi else ["[Time expired — skipped]"])
                sess.save()
                # Run conclusion
                print("\n" + "CONCLUSION")
                _run_stage(stages[conclusion_idx], sess, coach_enabled, case_context, difficulty)
                break

        print("\n" + spec.name.upper().replace("_", " "))

        # Show exhibit data before the exhibit interpretation stage
        if spec.name == "exhibit_interpretation" and case_data and "exhibit" in case_data:
            exhibit = case_data["exhibit"]
            print(f"\n--- EXHIBIT: {exhibit.get('title', 'Data')} ---")
            print(exhibit.get("data", ""))
            print("---\n")

        _run_stage(spec, sess, coach_enabled, case_context, difficulty)

        # After clarifying questions, reveal interviewer answers
        if spec.name == "clarifying_questions" and sess.clarifying_questions:
            answers = coach.answer_clarifying_questions(
                sess.clarifying_questions, case_context
            )
            if answers:
                print("\n--- INTERVIEWER ANSWERS ---")
                for q, a in zip(sess.clarifying_questions, answers):
                    print(f"  Q: {q}")
                    print(f"  A: {a}\n")
                print("---\n")

    print("\nSession complete. Your reasoning has been saved.")


def _clear_stage(sess: Session, name: str) -> None:
    """Reset a single stage field to its empty default."""
    if name in _SINGLE_FIELDS:
        setattr(sess, name, None)
    else:
        setattr(sess, name, [])


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------

def start_session(coach_flag: bool | None) -> None:
    """Start a new case study session."""
    all_cases = cases.load_cases()
    selected_case = choose_case(all_cases)
    if not selected_case:
        print("No case selected. Exiting.")
        return
    # Ask about coach if not specified
    if coach_flag is None:
        coach_enabled = ask_yes_no("Would you like to enable coach mode for this session? (y/n) ")
    else:
        coach_enabled = coach_flag
    category = selected_case.get("category", "strategy")
    sess = Session.new(selected_case["id"], category=category)
    # Display case prompt and context
    print("\nCASE STUDY")
    print(selected_case["prompt"])
    context = selected_case.get("context", "")
    if context:
        print("Context:", context)
    case_context = selected_case["prompt"] + ("\n\n" + context if context else "")
    run_session(sess, coach_enabled, case_context, case_data=selected_case)


def resume_session(session_file: str, coach_flag: bool | None) -> None:
    """Resume an existing session."""
    try:
        sess = Session.load(session_file)
    except Exception as e:
        print(f"Failed to load session '{session_file}': {e}")
        return

    stages = get_stages_for_category(sess.category)
    stage_names = tuple(s.name for s in stages)

    # Determine if session is complete
    complete = all(_is_stage_complete(getattr(sess, name)) for name in stage_names)
    # Ask about coach if not specified
    if coach_flag is None:
        coach_enabled = ask_yes_no("Would you like to enable coach mode for this session? (y/n) ")
    else:
        coach_enabled = coach_flag
    if complete:
        print("This session is already complete.\n")
        print_session(sess)
        print("Options:")
        print("1. Review session")
        print("2. Duplicate and revise")
        print("3. Exit")
        while True:
            choice = input("Select an option (1/2/3): ").strip()
            if choice == "1":
                return
            elif choice == "2":
                new_sess = Session.new(sess.case_id, category=sess.category)
                for name in stage_names:
                    val = getattr(sess, name)
                    setattr(new_sess, name, list(val) if isinstance(val, list) else val)
                run_session(new_sess, coach_enabled)
                return
            elif choice == "3":
                return
            else:
                print("Invalid choice.")
    else:
        print("Resuming session...")
        print_session(sess)
        print("Options:")
        print("1. Continue from next incomplete stage")
        print("2. Edit most recent completed stage")
        print("3. Exit")
        while True:
            choice = input("Select an option (1/2/3): ").strip()
            if choice == "1":
                run_session(sess, coach_enabled)
                return
            elif choice == "2":
                last_stage_index = -1
                for i, name in enumerate(stage_names):
                    if _is_stage_complete(getattr(sess, name)):
                        last_stage_index = i
                    else:
                        break
                if last_stage_index >= 0:
                    for name in stage_names[last_stage_index:]:
                        _clear_stage(sess, name)
                    sess.save()
                    run_session(sess, coach_enabled)
                    return
                else:
                    print("No completed stages to edit.")
                    return
            elif choice == "3":
                return
            else:
                print("Invalid choice.")


def print_session(sess: Session) -> None:
    """Pretty-print the contents of a session."""
    stages = get_stages_for_category(sess.category)
    print(f"Case ID: {sess.case_id}")
    print(f"Timestamp: {sess.timestamp}")
    for spec in stages:
        val = getattr(sess, spec.name)
        if not val:
            continue
        print(f"\n{spec.name.upper().replace('_', ' ')}:")
        if isinstance(val, list):
            for i, item in enumerate(val, start=1):
                print(f"  {i}. {item}")
        else:
            print(val)
