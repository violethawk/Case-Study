"""
Core logic for running a case study session.

The engine orchestrates the user through the five stages of the
reasoning loop: Frame → Hypothesize → Analyze → Update → Conclude.
It interacts with the CLI, prompts for user input, validates
responses, optionally invokes the AI coach, and persists the session
state after each stage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

from . import cases, coach, validation
from .session import Session, list_sessions


FRAMEWORKS_FILE = Path(__file__).resolve().parent.parent / "data" / "frameworks.json"


def load_frameworks() -> List[dict]:
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


def choose_case(cases_list: List[dict]) -> dict | None:
    """Prompt the user to select a case from the provided list.

    The cases are displayed with an index and ID.  The user may
    select by entering either the index or the case identifier.
    Returns the chosen case dictionary or ``None`` if no valid choice
    is made.
    """
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
    """Prompt the user for a free‑form response and validate it."""
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


def prompt_for_multi_items(item_name: str) -> List[str]:
    """Prompt the user to enter multiple items (hypotheses, analyses or updates)."""
    items = []
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


def run_session(sess: Session, coach_enabled: bool) -> None:
    """Interactively run through the remaining stages of the session."""
    # Determine starting point based on which fields are filled
    stages = [
        "restatement", "frame", "assumptions", "hypotheses",
        "analyses", "updates", "conclusion", "additional_insights",
    ]
    for stage in stages:
        if getattr(sess, stage) in (None, [], ""):
            start_stage = stage
            break
    else:
        start_stage = None

    if start_stage is None:
        print("This session is already complete.")
        return

    for stage in stages[stages.index(start_stage) : ]:
        print("\n" + stage.upper().replace("_", " "))

        if stage == "restatement":
            print("Before diving in, restate the problem in your own words.")
            print("This confirms your understanding and highlights any clarifying questions.")
            sess.restatement = prompt_for_stage("Restate the problem:\n> ")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.restatement)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "frame":
            if ask_yes_no("Would you like to see a list of common business frameworks? (y/n) "):
                display_frameworks()
            sess.frame = prompt_for_stage("How would you structure this problem? Which framework(s) will you use?\n> ")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.frame)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "assumptions":
            print("State and justify your key assumptions before proceeding.")
            print("e.g., 'I assume US population of 330M' or 'I assume no competitor response in year 1.'")
            sess.assumptions = prompt_for_multi_items("Assumption")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.assumptions)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "hypotheses":
            print("Enter one possible explanation or strategic path.")
            sess.hypotheses = prompt_for_multi_items("Hypothesis")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.hypotheses)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "analyses":
            print("What analysis would you perform?")
            sess.analyses = prompt_for_multi_items("Analysis")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.analyses)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "updates":
            print("How do your hypotheses change based on your analysis?")
            sess.updates = prompt_for_multi_items("Update")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.updates)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "conclusion":
            sess.conclusion = prompt_for_stage("What is your recommendation?\n> ")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.conclusion)
                print("\n" + feedback.format_for_cli() + "\n")

        elif stage == "additional_insights":
            print("Go beyond the case: what additional considerations, risks, or opportunities")
            print("should the client think about that were not directly asked?")
            sess.additional_insights = prompt_for_stage("Additional insights:\n> ")
            sess.save()
            if coach_enabled and ask_yes_no("Would you like coach feedback on this stage? (y/n) "):
                feedback = coach.provide_feedback(stage, sess.additional_insights)
                print("\n" + feedback.format_for_cli() + "\n")

        else:
            raise ValueError(f"Unknown stage: {stage}")

    print("\nSession complete. Your reasoning has been saved.")


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
    sess = Session.new(selected_case["id"])
    # Display case prompt and context
    print("\nCASE STUDY")
    print(selected_case["prompt"])
    context = selected_case.get("context")
    if context:
        print("Context:", context)
    run_session(sess, coach_enabled)


def resume_session(session_file: str, coach_flag: bool | None) -> None:
    """Resume an existing session."""
    try:
        sess = Session.load(session_file)
    except Exception as e:
        print(f"Failed to load session '{session_file}': {e}")
        return
    # Determine if session is complete
    complete = all([
        sess.restatement,
        sess.frame,
        sess.assumptions,
        sess.hypotheses,
        sess.analyses,
        sess.updates,
        sess.conclusion,
        sess.additional_insights,
    ])
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
                # Review – nothing to do
                return
            elif choice == "2":
                # Duplicate: create new session with same data except new timestamp
                new_sess = Session.new(sess.case_id)
                new_sess.restatement = sess.restatement
                new_sess.frame = sess.frame
                new_sess.assumptions = list(sess.assumptions)
                new_sess.hypotheses = list(sess.hypotheses)
                new_sess.analyses = list(sess.analyses)
                new_sess.updates = list(sess.updates)
                new_sess.conclusion = sess.conclusion
                new_sess.additional_insights = sess.additional_insights
                run_session(new_sess, coach_enabled)
                return
            elif choice == "3":
                return
            else:
                print("Invalid choice.")
    else:
        print("Resuming session...")
        print_session(sess)
        # Ask user whether to continue from next incomplete stage or edit most recent completed stage
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
                # Determine last completed stage
                # Stages order
                stage_order = [
                    "restatement", "frame", "assumptions", "hypotheses",
                    "analyses", "updates", "conclusion", "additional_insights",
                ]
                last_stage_index = -1
                for i, stg in enumerate(stage_order):
                    val = getattr(sess, stg)
                    if val:
                        last_stage_index = i
                    else:
                        break
                if last_stage_index >= 0:
                    # Clear last stage and subsequent
                    for stg in stage_order[last_stage_index:]:
                        if stg in ("restatement", "frame", "conclusion", "additional_insights"):
                            setattr(sess, stg, None)
                        else:
                            setattr(sess, stg, [])
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
    """Pretty‑print the contents of a session."""
    print(f"Case ID: {sess.case_id}")
    print(f"Timestamp: {sess.timestamp}")
    if sess.restatement:
        print("\nRESTATEMENT:")
        print(sess.restatement)
    if sess.frame:
        print("\nFRAME:")
        print(sess.frame)
    if sess.assumptions:
        print("\nASSUMPTIONS:")
        for i, a in enumerate(sess.assumptions, start=1):
            print(f"  {i}. {a}")
    if sess.hypotheses:
        print("\nHYPOTHESES:")
        for i, h in enumerate(sess.hypotheses, start=1):
            print(f"  {i}. {h}")
    if sess.analyses:
        print("\nANALYSES:")
        for i, a in enumerate(sess.analyses, start=1):
            print(f"  {i}. {a}")
    if sess.updates:
        print("\nUPDATES:")
        for i, u in enumerate(sess.updates, start=1):
            print(f"  {i}. {u}")
    if sess.conclusion:
        print("\nCONCLUSION:")
        print(sess.conclusion)
    if sess.additional_insights:
        print("\nADDITIONAL INSIGHTS:")
        print(sess.additional_insights)