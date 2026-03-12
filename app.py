"""
Streamlit web UI for the Case-Study project.

Provides a browser-based interface for the full case study session flow,
reusing the existing backend modules (cases, coach, validation, session).
"""

import time
import streamlit as st
from pathlib import Path

from case_study import cases, coach, validation
from case_study.session import Session, list_sessions
from case_study.engine import STAGES, load_frameworks

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGE_LABELS = {
    "restatement": "1. Restatement",
    "frame": "2. Frame",
    "assumptions": "3. Assumptions",
    "hypotheses": "4. Hypotheses",
    "analyses": "5. Analyses",
    "updates": "6. Updates",
    "conclusion": "7. Conclusion",
    "additional_insights": "8. Additional Insights",
}

STAGE_DESCRIPTIONS = {
    "restatement": "Restate the problem in your own words. This confirms your understanding and highlights any clarifying questions.",
    "frame": "How would you structure this problem? Which framework(s) will you use?",
    "assumptions": "State and justify your key assumptions before proceeding. e.g., 'I assume US population of 330M'.",
    "hypotheses": "Enter possible explanations or strategic paths.",
    "analyses": "What analyses would you perform to test your hypotheses?",
    "updates": "How do your hypotheses change based on your analysis?",
    "conclusion": "What is your recommendation?",
    "additional_insights": "Go beyond the case: what additional considerations, risks, or opportunities should the client think about?",
}

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
/* Header bar */
.main-header {
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    color: white;
    padding: 1.5rem 2rem;
    border-radius: 10px;
    margin-bottom: 1.5rem;
    text-align: center;
}
.main-header h1 {
    margin: 0;
    font-size: 2rem;
    font-weight: 700;
    color: white;
}
.main-header p {
    margin: 0.3rem 0 0 0;
    font-size: 1rem;
    opacity: 0.85;
    color: #e8eaf6;
}

/* Feedback cards */
.feedback-card {
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
    border-left: 4px solid;
}
.feedback-strengths {
    background: #e8f5e9;
    border-left-color: #2e7d32;
    color: #1b5e20;
}
.feedback-gaps {
    background: #fff3e0;
    border-left-color: #e65100;
    color: #bf360c;
}
.feedback-questions {
    background: #e3f2fd;
    border-left-color: #1565c0;
    color: #0d47a1;
}
.feedback-pass {
    background: #e8f5e9;
    border: 2px solid #2e7d32;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    color: #1b5e20;
    font-weight: 600;
}
.feedback-fail {
    background: #ffebee;
    border: 2px solid #c62828;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    color: #b71c1c;
    font-weight: 600;
}

/* Progress bar color override */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #1a237e, #42a5f5);
}

/* Stage label */
.stage-header {
    color: #1a237e;
    font-weight: 700;
}
.attempt-badge {
    background: #ff8f00;
    color: white;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.8rem;
    margin-left: 8px;
    font-weight: 600;
}

/* Report section */
.report-section {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin-bottom: 1rem;
    background: #fafafa;
}
.report-section h4 {
    color: #1a237e;
    margin-top: 0;
}

/* Timer display */
.timer-display {
    font-family: monospace;
    font-size: 1.3rem;
    color: #1a237e;
    font-weight: 700;
    text-align: center;
    padding: 0.5rem;
    background: #e8eaf6;
    border-radius: 6px;
    margin-bottom: 0.5rem;
}
</style>
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _display_name(raw: str) -> str:
    """Convert an underscore-separated ID into a readable title.

    e.g. 'bank_growth_001' -> 'Bank Growth 001'
         'additional_insights' -> 'Additional Insights'
    """
    return raw.replace("_", " ").title()


def get_stage_spec(name: str):
    """Return the StageSpec for the given stage name."""
    return next(s for s in STAGES if s.name == name)


def current_stage_index() -> int:
    """Return the index of the first incomplete stage, or len(STAGES) if all done."""
    sess = st.session_state.session
    for i, spec in enumerate(STAGES):
        val = getattr(sess, spec.name)
        if val is None or val == "" or val == []:
            return i
    return len(STAGES)


def save_session():
    """Persist the current session to disk."""
    st.session_state.session.save()


def load_all_cases():
    """Load and cache all cases."""
    return cases.load_cases()


def _format_elapsed(start_time: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    elapsed = int(time.time() - start_time)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _render_case_context(context_text: str):
    """Render case context, detecting text-based tables and using st.code for them."""
    if not context_text:
        return

    lines = context_text.split("\n")
    buffer = []
    in_table = False

    def flush_buffer():
        if buffer:
            text = "\n".join(buffer)
            if in_table:
                st.code(text, language=None)
            else:
                st.markdown(text)
            buffer.clear()

    for line in lines:
        # Detect table rows: lines containing | character (but not markdown bold etc.)
        stripped = line.strip()
        is_table_line = "|" in stripped and (
            stripped.startswith("|") or stripped.count("|") >= 2
        )
        # Also treat separator lines (---+---) as table
        is_separator = bool(stripped) and all(c in "-+| " for c in stripped) and len(stripped) > 3

        if is_table_line or is_separator:
            if not in_table:
                flush_buffer()
                in_table = True
            buffer.append(line)
        else:
            if in_table:
                flush_buffer()
                in_table = False
            buffer.append(line)

    flush_buffer()


# ---------------------------------------------------------------------------
# Page: Case Selection
# ---------------------------------------------------------------------------


def render_case_selection():
    st.markdown(
        '<div class="main-header">'
        "<h1>Case Study Practice</h1>"
        "<p>Sharpen your consulting problem-solving skills with structured case interviews</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("Select a case to begin your structured reasoning session.")

    all_cases = load_all_cases()

    # Filters
    col1, col2 = st.columns(2)
    categories = sorted({c.get("category", "unknown") for c in all_cases})
    difficulties = sorted(
        {c.get("difficulty", "unknown") for c in all_cases},
        key=lambda d: ["easy", "medium", "hard"].index(d) if d in ["easy", "medium", "hard"] else 99,
    )

    cat_labels = {c: _display_name(c) for c in categories}
    diff_labels = {d: d.capitalize() for d in difficulties}

    with col1:
        cat_display = st.selectbox("Category", ["All"] + [cat_labels[c] for c in categories])
        cat_filter = (
            next((k for k, v in cat_labels.items() if v == cat_display), None)
            if cat_display != "All"
            else None
        )
    with col2:
        diff_display = st.selectbox("Difficulty", ["All"] + [diff_labels[d] for d in difficulties])
        diff_filter = (
            next((k for k, v in diff_labels.items() if v == diff_display), None)
            if diff_display != "All"
            else None
        )

    filtered = all_cases
    if cat_filter:
        filtered = [c for c in filtered if c.get("category") == cat_filter]
    if diff_filter:
        filtered = [c for c in filtered if c.get("difficulty") == diff_filter]

    st.toggle("Enable Coach Mode", key="coach_enabled", value=st.session_state.get("coach_enabled", True))
    if st.session_state.get("coach_enabled") and coach.is_ai_enabled():
        st.caption("AI coaching active -- you must pass each stage to advance.")
    elif st.session_state.get("coach_enabled"):
        st.caption("Heuristic coaching (set GEMINI_API_KEY for AI-powered gating).")

    if not filtered:
        st.info("No cases match the selected filters.")
        return

    for case in filtered:
        diff = case.get("difficulty", "?")
        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(diff, "⚪")
        with st.expander(f"{diff_emoji} **{_display_name(case['id'])}** -- {case['prompt'][:80]}..."):
            st.markdown(
                f"**Category:** {_display_name(case.get('category', 'N/A'))}  |  **Difficulty:** {diff.capitalize()}"
            )
            st.markdown(f"**Prompt:** {case['prompt']}")
            if case.get("context"):
                st.markdown("**Context preview:**")
                _render_case_context(case["context"][:300] + ("..." if len(case.get("context", "")) > 300 else ""))
            if st.button("Start this case", key=f"start_{case['id']}"):
                sess = Session.new(case["id"])
                st.session_state.session = sess
                st.session_state.selected_case = case
                st.session_state.active_stage = 0
                st.session_state.page = "session"
                st.session_state.timer_start = time.time()
                # Initialize attempt counters
                for spec in STAGES:
                    st.session_state[f"attempts_{spec.name}"] = 1
                save_session()
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Session Review (post-completion report)
# ---------------------------------------------------------------------------


def render_session_review():
    """Show a full summary report after all 8 stages are complete."""
    sess = st.session_state.session
    case = st.session_state.selected_case

    st.markdown(
        '<div class="main-header">'
        "<h1>Session Complete</h1>"
        "<p>Review your full case study reasoning below</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Case info
    st.markdown(f"**Case:** {_display_name(sess.case_id)}")
    st.markdown(f"**Prompt:** {case['prompt']}")
    if st.session_state.get("timer_start"):
        elapsed = _format_elapsed(st.session_state.timer_start)
        st.markdown(f"**Total time:** {elapsed}")
    st.markdown("---")

    # Report: each stage
    for spec in STAGES:
        val = getattr(sess, spec.name)
        label = STAGE_LABELS[spec.name]

        st.markdown(
            f'<div class="report-section"><h4>{label}</h4>',
            unsafe_allow_html=True,
        )

        if isinstance(val, list):
            for j, item in enumerate(val, 1):
                st.markdown(f"{j}. {item}")
        else:
            st.markdown(val if val else "_No response_")

        # Show any stored coach feedback for this stage
        feedback_history_key = f"feedback_history_{spec.name}"
        if feedback_history_key in st.session_state:
            fb = st.session_state[feedback_history_key]
            st.markdown("**Coach Feedback:**")
            _render_feedback_display(fb)

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    st.balloons()

    if st.button("Start New Case", type="primary", use_container_width=True):
        _full_reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Page: Session Flow
# ---------------------------------------------------------------------------


def render_session():
    sess = st.session_state.session
    case = st.session_state.selected_case
    stage_idx = current_stage_index()

    # Header
    st.markdown(
        f'<div class="main-header">'
        f"<h1>Case: {_display_name(sess.case_id)}</h1>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Prompt:** {case['prompt']}")
    if case.get("context"):
        with st.expander("View full case context"):
            _render_case_context(case["context"])

    # Progress
    total = len(STAGES)
    st.progress(stage_idx / total, text=f"Progress: {stage_idx}/{total} stages complete")

    # Show completed stages (most recent one expanded)
    for i in range(stage_idx):
        spec = STAGES[i]
        val = getattr(sess, spec.name)
        is_most_recent = i == stage_idx - 1
        attempt_count = st.session_state.get(f"attempts_{spec.name}", 1)
        label = f"{STAGE_LABELS[spec.name]} (completed)"
        if attempt_count > 1:
            label += f"  -- Attempt {attempt_count}"
        with st.expander(label, expanded=is_most_recent):
            if isinstance(val, list):
                for j, item in enumerate(val, 1):
                    st.markdown(f"{j}. {item}")
            else:
                st.markdown(val)

    # All done?
    if stage_idx >= total:
        render_session_review()
        return

    # Current stage
    spec = STAGES[stage_idx]
    stage_name = spec.name

    # Stage header with attempt badge
    attempt_count = st.session_state.get(f"attempts_{stage_name}", 1)
    header_html = f'<span class="stage-header">{STAGE_LABELS[stage_name]}</span>'
    if attempt_count > 1:
        header_html += f' <span class="attempt-badge">Attempt {attempt_count}</span>'
    st.markdown(f"### {STAGE_LABELS[stage_name]}")
    if attempt_count > 1:
        st.markdown(
            f'<span class="attempt-badge">Attempt {attempt_count}</span>',
            unsafe_allow_html=True,
        )
    st.markdown(STAGE_DESCRIPTIONS[stage_name])

    # Frameworks reference for frame stage
    if spec.offer_frameworks:
        frameworks = load_frameworks()
        if frameworks:
            with st.expander("View available business frameworks"):
                for fw in frameworks:
                    st.markdown(f"**{fw['name']}** ({fw['full_name']})")
                    st.caption(fw["description"])
                    st.markdown(f"*Best for: {', '.join(_display_name(t) for t in fw.get('best_for', []))}*")
                    st.divider()

    # Input
    if spec.multi:
        _render_multi_input(stage_name, spec.item_name, stage_idx)
    else:
        _render_single_input(stage_name, stage_idx)


def _render_single_input(stage_name: str, stage_idx: int):
    """Render a text area for a single-response stage."""
    text_key = f"input_{stage_name}"
    response = st.text_area(
        f"Your {_display_name(stage_name)}:",
        key=text_key,
        height=200,
        placeholder="Type your response here...",
    )

    if st.button("Submit", key=f"submit_{stage_name}"):
        result = validation.validate_response(response)
        if not result.accepted:
            st.error(result.message)
            return
        if result.short:
            st.warning(f"{result.message} Consider expanding your reasoning for a stronger answer.")
        setattr(st.session_state.session, stage_name, response)
        save_session()
        _after_stage_submit(stage_name, response)


def _render_multi_input(stage_name: str, item_name: str, stage_idx: int):
    """Render an add-one-at-a-time interface for multi-item stages."""
    items_key = f"items_{stage_name}"
    if items_key not in st.session_state:
        st.session_state[items_key] = []

    # Counter for clearing text area after add
    add_counter_key = f"add_counter_{stage_name}"
    if add_counter_key not in st.session_state:
        st.session_state[add_counter_key] = 0

    # Show existing items
    items = st.session_state[items_key]
    if items:
        st.markdown("**Items added:**")
        for j, item in enumerate(items):
            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"{j + 1}. {item}")
            with col2:
                if st.button("X", key=f"remove_{stage_name}_{j}"):
                    st.session_state[items_key].pop(j)
                    st.rerun()

    # Add new item -- use counter in key to force fresh widget after add
    counter = st.session_state[add_counter_key]
    new_item_key = f"new_item_{stage_name}_{counter}"
    new_item = st.text_area(
        f"Add {item_name.lower()}:",
        key=new_item_key,
        height=100,
        placeholder=f"Type a new {item_name.lower()} here...",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"Add {item_name}", key=f"add_{stage_name}"):
            result = validation.validate_multi_item(new_item)
            if not result.accepted:
                st.error(result.message)
            else:
                if result.short:
                    st.warning(f"{result.message} Consider expanding for a stronger answer.")
                st.session_state[items_key].append(new_item)
                # Increment counter to generate fresh text area key
                st.session_state[add_counter_key] += 1
                st.rerun()

    with col2:
        if items and st.button(f"Done with {_display_name(stage_name)}", key=f"done_{stage_name}"):
            setattr(st.session_state.session, stage_name, list(items))
            save_session()
            _after_stage_submit(stage_name, items)
            # Clean up temp items
            st.session_state.pop(items_key, None)
            st.session_state.pop(add_counter_key, None)

    if not items:
        st.caption(f"Add at least one {item_name.lower()} before proceeding.")


def _after_stage_submit(stage_name: str, content):
    """Handle post-submission: show success and offer coach feedback."""
    st.session_state[f"submitted_{stage_name}"] = True
    st.session_state[f"content_{stage_name}"] = content
    st.rerun()


def _clear_stage_input_keys():
    """Remove transient input keys from session state."""
    keys_to_remove = [
        k
        for k in st.session_state
        if k.startswith(
            ("input_", "items_", "new_item_", "submitted_", "content_", "feedback_", "add_counter_")
        )
    ]
    for k in keys_to_remove:
        del st.session_state[k]


def _full_reset():
    """Clear all session-related keys for a fresh start."""
    for key in ["session", "selected_case", "active_stage", "page", "timer_start"]:
        st.session_state.pop(key, None)
    # Clear attempt counters
    for spec in STAGES:
        st.session_state.pop(f"attempts_{spec.name}", None)
        st.session_state.pop(f"feedback_history_{spec.name}", None)
    _clear_stage_input_keys()


def render_coach_feedback():
    """Check if any stage was just submitted and handle coach evaluation.

    When AI coaching is enabled, the coach acts as a gate: the user
    must pass before advancing.  If not passed, the stage is cleared
    so the user can revise.  With heuristic coaching (no API key) or
    coach disabled, the user always advances.
    """
    ai_gating = st.session_state.get("coach_enabled", False) and coach.is_ai_enabled()

    for spec in STAGES:
        submitted_key = f"submitted_{spec.name}"
        if not st.session_state.get(submitted_key):
            continue

        feedback_key = f"feedback_{spec.name}"
        coach_enabled = st.session_state.get("coach_enabled", False)

        # --- AI gating mode: auto-evaluate on submit ---
        if ai_gating:
            if feedback_key not in st.session_state:
                content = st.session_state[f"content_{spec.name}"]
                with st.spinner("Coach is evaluating your response..."):
                    fb = coach.provide_feedback(spec.name, content)
                st.session_state[feedback_key] = fb

            fb = st.session_state[feedback_key]
            _render_feedback_display(fb)

            if fb.passed:
                st.markdown(
                    '<div class="feedback-pass">You passed this stage!</div>',
                    unsafe_allow_html=True,
                )
                # Save feedback for report
                st.session_state[f"feedback_history_{spec.name}"] = fb
                if st.button("Continue to next stage", key=f"continue_{spec.name}"):
                    _clear_submitted(spec.name)
                    st.rerun()
            else:
                st.markdown(
                    '<div class="feedback-fail">Not yet -- revise your response and resubmit.</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Revise this stage", key=f"revise_{spec.name}"):
                    # Increment attempt counter
                    attempts_key = f"attempts_{spec.name}"
                    st.session_state[attempts_key] = st.session_state.get(attempts_key, 1) + 1
                    # Clear the stage value so the user can redo it
                    sess = st.session_state.session
                    if spec.multi:
                        setattr(sess, spec.name, [])
                    else:
                        setattr(sess, spec.name, None)
                    sess.save()
                    _clear_submitted(spec.name)
                    st.rerun()
            return True

        # --- Optional coach mode (heuristic or no API key) ---
        st.success(f"Stage '{_display_name(spec.name)}' saved.")
        if coach_enabled:
            if feedback_key not in st.session_state:
                if st.button("Get Coach Feedback", key=f"coach_btn_{spec.name}"):
                    content = st.session_state[f"content_{spec.name}"]
                    fb = coach.provide_feedback(spec.name, content)
                    st.session_state[feedback_key] = fb

            if feedback_key in st.session_state:
                fb = st.session_state[feedback_key]
                _render_feedback_display(fb)
                # Save feedback for report
                st.session_state[f"feedback_history_{spec.name}"] = fb

        if st.button("Continue to next stage", key=f"continue_{spec.name}"):
            _clear_submitted(spec.name)
            st.rerun()
        return True

    return False


def _render_feedback_display(fb: coach.CoachFeedback):
    """Render coach feedback in styled cards."""
    st.markdown("---")
    st.markdown("**Coach Feedback**")
    st.markdown(
        f'<div class="feedback-card feedback-strengths">'
        f"<strong>Strengths:</strong> {fb.strengths}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="feedback-card feedback-gaps">'
        f"<strong>Gaps:</strong> {fb.gaps}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="feedback-card feedback-questions">'
        f"<strong>Questions to consider:</strong> {fb.questions}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _clear_submitted(stage_name: str):
    """Remove submission-related keys for a stage."""
    for prefix in ("submitted_", "content_", "feedback_", "items_", "add_counter_"):
        st.session_state.pop(f"{prefix}{stage_name}", None)


# ---------------------------------------------------------------------------
# Sidebar: Session Management
# ---------------------------------------------------------------------------


def render_sidebar():
    with st.sidebar:
        st.header("Session Management")

        # Timer display
        if st.session_state.get("page") == "session" and st.session_state.get("timer_start"):
            elapsed_str = _format_elapsed(st.session_state.timer_start)
            st.markdown(
                f'<div class="timer-display">{elapsed_str} elapsed</div>',
                unsafe_allow_html=True,
            )

        if st.session_state.get("page") == "session":
            if st.button("Back to case selection"):
                _full_reset()
                st.rerun()

        st.divider()
        st.subheader("Previous Sessions")

        session_files = list_sessions()
        if not session_files:
            st.caption("No saved sessions yet.")
        else:
            # Use selectbox + load button instead of a long list of buttons
            session_labels = [_display_name(sf.stem) for sf in session_files[:20]]
            selected_label = st.selectbox(
                "Select a session",
                session_labels,
                index=0,
                key="session_selector",
            )
            selected_idx = session_labels.index(selected_label)
            if st.button("Load Session", use_container_width=True):
                _resume_session(session_files[selected_idx])


def _resume_session(filepath: Path):
    """Load a session file and switch to session view."""
    sess = Session.load(filepath)
    all_cases = load_all_cases()
    case = cases.get_case_by_id(sess.case_id, all_cases)
    if case is None:
        # Build a minimal case dict so the UI can still display
        case = {
            "id": sess.case_id,
            "prompt": f"Case {sess.case_id}",
            "context": "",
            "category": "unknown",
            "difficulty": "unknown",
        }
    st.session_state.session = sess
    st.session_state.selected_case = case
    st.session_state.active_stage = current_stage_index()
    st.session_state.page = "session"
    # Set timer start to now for resumed sessions
    st.session_state.timer_start = time.time()
    # Initialize attempt counters for resumed session
    for spec in STAGES:
        if f"attempts_{spec.name}" not in st.session_state:
            st.session_state[f"attempts_{spec.name}"] = 1
    _clear_stage_input_keys()
    st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Case Study Practice", page_icon="📋", layout="wide")

    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Initialize defaults
    if "page" not in st.session_state:
        st.session_state.page = "selection"
    if "coach_enabled" not in st.session_state:
        st.session_state.coach_enabled = True

    render_sidebar()

    if st.session_state.page == "session" and "session" in st.session_state:
        # Check if we need to show post-submission feedback before rendering the next stage
        if not render_coach_feedback():
            render_session()
    else:
        render_case_selection()


if __name__ == "__main__":
    main()
