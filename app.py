"""
Streamlit web UI for the Case-Study project.

Provides a browser-based interface for the full case study session flow,
reusing the existing backend modules (cases, coach, validation, session).
"""

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
# Helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Page: Case Selection
# ---------------------------------------------------------------------------


def render_case_selection():
    st.title("Case Study Practice")
    st.markdown("Select a case to begin your structured reasoning session.")

    all_cases = load_all_cases()

    # Filters
    col1, col2 = st.columns(2)
    categories = sorted({c.get("category", "unknown") for c in all_cases})
    difficulties = sorted({c.get("difficulty", "unknown") for c in all_cases}, key=lambda d: ["easy", "medium", "hard"].index(d) if d in ["easy", "medium", "hard"] else 99)

    with col1:
        cat_filter = st.selectbox("Category", ["All"] + categories)
    with col2:
        diff_filter = st.selectbox("Difficulty", ["All"] + difficulties)

    filtered = all_cases
    if cat_filter != "All":
        filtered = [c for c in filtered if c.get("category") == cat_filter]
    if diff_filter != "All":
        filtered = [c for c in filtered if c.get("difficulty") == diff_filter]

    st.toggle("Enable Coach Mode", key="coach_enabled", value=st.session_state.get("coach_enabled", True))

    if not filtered:
        st.info("No cases match the selected filters.")
        return

    for case in filtered:
        diff = case.get("difficulty", "?")
        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(diff, "⚪")
        with st.expander(f"{diff_emoji} **{case['id']}** — {case['prompt'][:80]}..."):
            st.markdown(f"**Category:** {case.get('category', 'N/A')}  |  **Difficulty:** {diff}")
            st.markdown(f"**Prompt:** {case['prompt']}")
            if case.get("context"):
                st.markdown(f"**Context:** {case['context'][:300]}{'...' if len(case.get('context', '')) > 300 else ''}")
            if st.button("Start this case", key=f"start_{case['id']}"):
                sess = Session.new(case["id"])
                st.session_state.session = sess
                st.session_state.selected_case = case
                st.session_state.active_stage = 0
                st.session_state.page = "session"
                save_session()
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Session Flow
# ---------------------------------------------------------------------------


def render_session():
    sess = st.session_state.session
    case = st.session_state.selected_case
    stage_idx = current_stage_index()

    # Header
    st.title(f"Case: {sess.case_id}")
    st.markdown(f"**Prompt:** {case['prompt']}")
    if case.get("context"):
        with st.expander("View full case context"):
            st.markdown(case["context"])

    # Progress
    total = len(STAGES)
    st.progress(stage_idx / total, text=f"Progress: {stage_idx}/{total} stages complete")

    # Show completed stages
    for i in range(stage_idx):
        spec = STAGES[i]
        val = getattr(sess, spec.name)
        with st.expander(f"{STAGE_LABELS[spec.name]} (completed)"):
            if isinstance(val, list):
                for j, item in enumerate(val, 1):
                    st.markdown(f"{j}. {item}")
            else:
                st.markdown(val)

    # All done?
    if stage_idx >= total:
        st.success("Session complete! Your reasoning has been saved.")
        st.balloons()
        if st.button("Start a new case"):
            for key in ["session", "selected_case", "active_stage", "page"]:
                st.session_state.pop(key, None)
            _clear_stage_input_keys()
            st.rerun()
        return

    # Current stage
    spec = STAGES[stage_idx]
    stage_name = spec.name

    st.subheader(STAGE_LABELS[stage_name])
    st.markdown(STAGE_DESCRIPTIONS[stage_name])

    # Frameworks reference for frame stage
    if spec.offer_frameworks:
        frameworks = load_frameworks()
        if frameworks:
            with st.expander("View available business frameworks"):
                for fw in frameworks:
                    st.markdown(f"**{fw['name']}** ({fw['full_name']})")
                    st.caption(fw["description"])
                    st.markdown(f"*Best for: {', '.join(fw.get('best_for', []))}*")
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
        f"Your {stage_name.replace('_', ' ')}:",
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

    # Add new item
    new_item_key = f"new_item_{stage_name}"
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
                st.rerun()

    with col2:
        if items and st.button(f"Done with {stage_name.replace('_', ' ')}", key=f"done_{stage_name}"):
            setattr(st.session_state.session, stage_name, list(items))
            save_session()
            _after_stage_submit(stage_name, items)
            # Clean up temp items
            st.session_state.pop(items_key, None)

    if not items:
        st.caption(f"Add at least one {item_name.lower()} before proceeding.")


def _after_stage_submit(stage_name: str, content):
    """Handle post-submission: show success and offer coach feedback."""
    st.session_state[f"submitted_{stage_name}"] = True
    st.session_state[f"content_{stage_name}"] = content
    st.rerun()


def _clear_stage_input_keys():
    """Remove transient input keys from session state."""
    keys_to_remove = [k for k in st.session_state if k.startswith(("input_", "items_", "new_item_", "submitted_", "content_", "feedback_"))]
    for k in keys_to_remove:
        del st.session_state[k]


def render_coach_feedback():
    """Check if any stage was just submitted and offer coach feedback."""
    for spec in STAGES:
        submitted_key = f"submitted_{spec.name}"
        if st.session_state.get(submitted_key):
            st.success(f"Stage '{spec.name.replace('_', ' ')}' saved.")
            if st.session_state.get("coach_enabled", False):
                feedback_key = f"feedback_{spec.name}"
                if feedback_key not in st.session_state:
                    if st.button("Get Coach Feedback", key=f"coach_btn_{spec.name}"):
                        content = st.session_state[f"content_{spec.name}"]
                        fb = coach.provide_feedback(spec.name, content)
                        st.session_state[feedback_key] = fb

                if feedback_key in st.session_state:
                    fb = st.session_state[feedback_key]
                    st.markdown("---")
                    st.markdown("**Coach Feedback**")
                    st.success(f"**Strengths:** {fb.strengths}")
                    st.warning(f"**Gaps:** {fb.gaps}")
                    st.info(f"**Questions to consider:** {fb.questions}")

                if st.button("Continue to next stage", key=f"continue_{spec.name}"):
                    st.session_state.pop(submitted_key, None)
                    st.session_state.pop(f"content_{spec.name}", None)
                    st.session_state.pop(f"feedback_{spec.name}", None)
                    st.rerun()
            else:
                if st.button("Continue to next stage", key=f"continue_{spec.name}"):
                    st.session_state.pop(submitted_key, None)
                    st.session_state.pop(f"content_{spec.name}", None)
                    st.rerun()
            return True
    return False


# ---------------------------------------------------------------------------
# Sidebar: Session Management
# ---------------------------------------------------------------------------


def render_sidebar():
    with st.sidebar:
        st.header("Session Management")

        if st.session_state.get("page") == "session":
            if st.button("Back to case selection"):
                for key in ["session", "selected_case", "active_stage", "page"]:
                    st.session_state.pop(key, None)
                _clear_stage_input_keys()
                st.rerun()

        st.divider()
        st.subheader("Previous Sessions")

        session_files = list_sessions()
        if not session_files:
            st.caption("No saved sessions yet.")
        else:
            for sf in session_files[:20]:
                if st.button(sf.stem, key=f"load_{sf.stem}", use_container_width=True):
                    _resume_session(sf)


def _resume_session(filepath: Path):
    """Load a session file and switch to session view."""
    sess = Session.load(filepath)
    all_cases = load_all_cases()
    case = cases.get_case_by_id(sess.case_id, all_cases)
    if case is None:
        # Build a minimal case dict so the UI can still display
        case = {"id": sess.case_id, "prompt": f"Case {sess.case_id}", "context": "", "category": "unknown", "difficulty": "unknown"}
    st.session_state.session = sess
    st.session_state.selected_case = case
    st.session_state.active_stage = current_stage_index()
    st.session_state.page = "session"
    _clear_stage_input_keys()
    st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Case Study Practice", page_icon="📋", layout="wide")

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
