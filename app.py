"""
Streamlit web UI for the Case-Study project.

Provides a browser-based interface for the full case study session flow,
reusing the existing backend modules (cases, coach, validation, session).
"""

import time
from datetime import datetime

import streamlit as st
from pathlib import Path

from case_study import cases, coach, validation, analytics, mental_math
from case_study.coach import DIFFICULTY_LEVELS, STAGE_HINTS, MBB_PRO_TIPS
from case_study.session import Session, list_sessions
from case_study.engine import (
    STAGES_BY_CATEGORY,
    STAGE_TIME_LIMITS,
    TOTAL_CASE_TIME_LIMIT,
    StageSpec,
    get_stages_for_category,
    get_stages_with_exhibit,
    get_stage_time_limit,
    format_time_warning,
    check_time_expired,
    load_frameworks,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Display names for all stages across all categories
STAGE_DISPLAY_NAMES: dict[str, str] = {
    "restatement": "Restatement",
    "clarifying_questions": "Clarifying Questions",
    "framework": "Framework Selection",
    "frame": "Frame",
    "assumptions": "Assumptions",
    "equation": "Equation",
    "hypotheses": "Hypotheses",
    "analyses": "Analyses",
    "updates": "Updates",
    "conclusion": "Conclusion",
    "additional_insights": "Additional Insights",
    "structure": "Structure",
    "setup": "Setup",
    "calculation": "Calculation",
    "sanity_check": "Sanity Check",
    "sensitivity": "Sensitivity",
    "exhibit_interpretation": "Exhibit Interpretation",
}

STAGE_DESCRIPTIONS: dict[str, str] = {
    "restatement": "Restate the problem in your own words. This confirms your understanding and highlights any clarifying questions.",
    "framework": "Select a framework to structure your analysis. Choose the one that best fits this problem type.",
    "frame": "How will you apply your chosen framework? Outline the key areas you'll analyze and why they matter.",
    "assumptions": "State and justify your key assumptions before proceeding. e.g., 'I assume US population of 330M'.",
    "equation": "Break the problem into a quantitative equation (e.g., Revenue = Price x Volume). Identify which variables you need to estimate.",
    "hypotheses": "Enter possible explanations or strategic paths.",
    "analyses": "What analyses would you perform to test your hypotheses?",
    "updates": "How do your hypotheses change based on your analysis?",
    "conclusion": "What is your recommendation?",
    "additional_insights": "Go beyond the case: what additional considerations, risks, or opportunities should the client think about?",
    "structure": "Break the problem into logical components. Choose a top-down or bottom-up approach and outline the key segments.",
    "setup": "Set up the problem: what are you solving for, what are the key variables, and what is your calculation approach?",
    "calculation": "Work through your calculations step by step, showing your work clearly.",
    "sanity_check": "Sanity-check your estimate. Does it pass the smell test? Try an alternative approach to verify.",
    "sensitivity": "Which assumptions most affect your answer? How sensitive is the result to changes in key inputs?",
    "clarifying_questions": "What clarifying questions would you ask the interviewer before structuring? Good questions narrow the problem scope.",
    "exhibit_interpretation": "The interviewer has shared a data exhibit. State the headline insight — lead with the 'so what.'",
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

/* Score card */
.score-card {
    text-align: center;
    padding: 1.5rem;
    border-radius: 10px;
    margin-bottom: 1.5rem;
}
.score-card .score-number {
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 0.3rem;
}
.score-card .score-label {
    font-size: 1rem;
    opacity: 0.85;
}
.score-high { background: linear-gradient(135deg, #e8f5e9, #c8e6c9); color: #1b5e20; }
.score-high .score-number { color: #2e7d32; }
.score-mid { background: linear-gradient(135deg, #fff8e1, #ffecb3); color: #e65100; }
.score-mid .score-number { color: #f57f17; }
.score-low { background: linear-gradient(135deg, #ffebee, #ffcdd2); color: #b71c1c; }
.score-low .score-number { color: #c62828; }

/* Stage result indicators */
.stage-result-good { color: #2e7d32; }
.stage-result-ok { color: #f57f17; }
.stage-result-weak { color: #c62828; }

/* Interviewer reveal card */
.interviewer-card {
    background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%);
    border-left: 4px solid #6a1b9a;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 1rem 0;
    color: #4a148c;
}
.interviewer-card .interviewer-label {
    font-weight: 700;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.5rem;
    color: #6a1b9a;
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


_ACRONYMS = {"ai", "ev", "us", "saas", "roi", "ngo", "reit", "mbb", "jpmorgan"}

def _display_name(raw: str) -> str:
    """Convert an underscore-separated ID into a readable title.

    Handles acronyms (AI, EV, SaaS, etc.) and hyphens in category names.

    e.g. 'bank_growth' -> 'Bank Growth'
         'ai_operations' -> 'AI Operations'
         'market-sizing' -> 'Market Sizing'
    """
    # Normalize hyphens to spaces
    cleaned = raw.replace("_", " ").replace("-", " ")
    words = cleaned.split()
    result = []
    for w in words:
        if w.lower() in _ACRONYMS:
            result.append(w.upper())
        else:
            result.append(w.capitalize())
    return " ".join(result)


def _get_active_stages() -> tuple[StageSpec, ...]:
    """Return the stages tuple for the current session's category."""
    case = st.session_state.get("selected_case")
    if case:
        category = case.get("category", "strategy")
        return get_stages_with_exhibit(category, case)
    sess = st.session_state.get("session")
    category = getattr(sess, "category", "strategy") if sess else "strategy"
    return get_stages_for_category(category)


def _stage_label(stage_name: str, stages: tuple[StageSpec, ...] | None = None) -> str:
    """Return a numbered label like '1. Restatement' for the given stage."""
    if stages is None:
        stages = _get_active_stages()
    for i, s in enumerate(stages):
        if s.name == stage_name:
            return f"{i + 1}. {STAGE_DISPLAY_NAMES.get(stage_name, _display_name(stage_name))}"
    return STAGE_DISPLAY_NAMES.get(stage_name, _display_name(stage_name))


def get_stage_spec(name: str) -> StageSpec:
    """Return the StageSpec for the given stage name."""
    return next(s for s in _get_active_stages() if s.name == name)


def current_stage_index() -> int:
    """Return the index of the first incomplete stage, or total if all done."""
    sess = st.session_state.session
    stages = _get_active_stages()
    for i, spec in enumerate(stages):
        val = getattr(sess, spec.name)
        if val is None or val == "" or val == []:
            return i
    return len(stages)


def save_session():
    """Persist the current session to disk."""
    st.session_state.session.save()


def load_all_cases():
    """Load and cache all cases."""
    return cases.load_cases()


def _format_session_label(stem: str) -> str:
    """Format a session filename stem into a readable label.

    e.g. 'bank_growth_2026-03-12_22-43-56' -> 'Bank Growth — Mar 12, 2026'
         'bank_growth_001_2026-03-12_13-38-16' -> 'Bank Growth — Mar 12, 2026'
    """
    import re
    # Try to extract a date from the stem
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})_\d{2}-\d{2}-\d{2}$", stem)
    if match:
        # Everything before the date is the case name
        date_start = match.start()
        name_part = stem[:date_start].rstrip("_")
        # Strip trailing _001 style suffixes
        name_part = re.sub(r"_\d{3}$", "", name_part)
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{month_names[month - 1]} {day}, {year}"
        return f"{_display_name(name_part)} — {date_str}"
    return _display_name(stem)


def _format_elapsed(start_time: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    elapsed = int(time.time() - start_time)
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _escape_markdown(text: str) -> str:
    """Escape characters that Streamlit's markdown would misinterpret.

    - ``$`` triggers LaTeX math rendering
    - ``<`` / ``>`` are parsed as HTML tags
    """
    return text.replace("$", "&#36;").replace("<", "&lt;").replace(">", "&gt;")


def _md(text: str, **kwargs):
    """Render markdown with automatic escaping of dollar signs and angle brackets."""
    st.markdown(_escape_markdown(text), **kwargs)


def _render_case_context(context_text: str):
    """Render case context with visual structure: headers, bullets, tables, and prose."""
    if not context_text:
        return

    import re

    lines = context_text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            i += 1
            continue

        # Detect table rows (pipe-delimited or separator lines)
        is_table_line = "|" in stripped and (
            stripped.startswith("|") or stripped.count("|") >= 2
        )
        is_separator = bool(stripped) and all(c in "-+| " for c in stripped) and len(stripped) > 3

        if is_table_line or is_separator:
            # Collect contiguous table lines
            table_lines = []
            while i < len(lines):
                s = lines[i].strip()
                is_tl = "|" in s and (s.startswith("|") or s.count("|") >= 2)
                is_sep = bool(s) and all(c in "-+| " for c in s) and len(s) > 3
                if is_tl or is_sep:
                    table_lines.append(lines[i])
                    i += 1
                elif not s:
                    i += 1  # skip blank lines within table area
                else:
                    break
            st.code("\n".join(table_lines), language=None)
            continue

        # Detect section headers: lines ending with ":" that are short-ish
        # e.g. "Current challenges:", "Financial snapshot:", "Customer segments:"
        if stripped.endswith(":") and len(stripped) < 80 and not stripped.startswith("-"):
            st.markdown(f"**{_escape_markdown(stripped)}**")
            i += 1
            continue

        # Detect indented key-value lines (e.g. "  Mass market (<$100K): 78% of customers")
        # These often appear under section headers as structured data
        if re.match(r"^\s{2,}\S", line) and ":" in stripped and not stripped.startswith("-"):
            # Collect contiguous indented lines
            indented_lines = []
            while i < len(lines):
                s = lines[i]
                if s.strip() and (re.match(r"^\s{2,}\S", s) or not s.strip()):
                    if s.strip():
                        indented_lines.append(f"- {_escape_markdown(s.strip())}")
                    i += 1
                else:
                    break
            if indented_lines:
                st.markdown("\n".join(indented_lines))
            continue

        # Detect bullet lists (lines starting with -)
        if stripped.startswith("- "):
            bullet_lines = []
            while i < len(lines):
                s = lines[i].strip()
                if s.startswith("- "):
                    bullet_lines.append(f"- {_escape_markdown(s[2:])}")
                    i += 1
                elif not s:
                    i += 1
                    break
                else:
                    break
            st.markdown("\n".join(bullet_lines))
            continue

        # Regular prose paragraph — collect until blank line or structural element
        para_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                i += 1
                break
            # Stop if next line looks like a header, bullet, table, or indented data
            if (s.endswith(":") and len(s) < 80 and not s.startswith("-")):
                break
            if s.startswith("- "):
                break
            if "|" in s and (s.startswith("|") or s.count("|") >= 2):
                break
            if re.match(r"^\s{2,}\S", lines[i]) and ":" in s:
                break
            para_lines.append(_escape_markdown(s))
            i += 1
        if para_lines:
            st.markdown(" ".join(para_lines))


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
        diff_display = st.selectbox("Case Difficulty", ["All"] + [diff_labels[d] for d in difficulties])
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

    if not filtered:
        st.info("No cases match the selected filters.")
        return

    is_filtered = cat_filter is not None or diff_filter is not None
    if is_filtered:
        st.caption(f"Showing {len(filtered)} of {len(all_cases)} cases")

    # Group cases by category
    from collections import OrderedDict
    grouped: dict[str, list] = OrderedDict()
    for case in filtered:
        cat = case.get("category", "unknown")
        grouped.setdefault(cat, []).append(case)

    _CAT_ICONS = {"strategy": "♟️", "market-sizing": "📐", "quantitative": "📊"}

    _DIFF_ORDER = {"easy": 0, "medium": 1, "hard": 2}

    for cat, cat_cases in grouped.items():
        cat_icon = _CAT_ICONS.get(cat, "📁")
        cat_cases.sort(key=lambda c: _DIFF_ORDER.get(c.get("difficulty", ""), 99))
        st.subheader(f"{cat_icon} {_display_name(cat)} ({len(cat_cases)})")
        for case in cat_cases:
            diff = case.get("difficulty", "?")
            diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(diff, "⚪")
            col_name, col_btn = st.columns([5, 1])
            with col_name:
                st.markdown(f"{diff_emoji} **{_display_name(case['id'])}**")
            with col_btn:
                if st.button("Start", key=f"start_{case['id']}", type="primary"):
                    category = case.get("category", "strategy")
                    sess = Session.new(case["id"], category=category)
                    st.session_state.session = sess
                    st.session_state.selected_case = case
                    st.session_state.active_stage = 0
                    st.session_state.page = "session"
                    st.session_state.timer_start = time.time()
                    stages = get_stages_for_category(category)
                    for spec in stages:
                        st.session_state[f"attempts_{spec.name}"] = 1
                    save_session()
                    st.rerun()


# ---------------------------------------------------------------------------
# Page: Session Review (post-completion report)
# ---------------------------------------------------------------------------


def render_session_review():
    """Show a full summary report after all stages are complete."""
    sess = st.session_state.session
    case = st.session_state.selected_case
    stages = _get_active_stages()

    # Save analytics data on completion
    if not sess.completed_at:
        sess.completed_at = datetime.now().astimezone().isoformat()
        if st.session_state.get("timer_start"):
            sess.total_time_seconds = time.time() - st.session_state.timer_start
        sess.stage_attempts = {
            spec.name: st.session_state.get(f"attempts_{spec.name}", 1)
            for spec in stages
        }
        sess.difficulty = st.session_state.get("difficulty", "intermediate")
        sess.coach_enabled = st.session_state.get("coach_enabled", False)
        save_session()

    # --- Compute overall score ---
    total_stages = len(stages)
    first_attempt_count = 0
    total_attempts = 0
    passed_count = 0
    stage_scores: dict[str, dict] = {}

    for spec in stages:
        attempts = sess.stage_attempts.get(spec.name, 1) if sess.stage_attempts else 1
        total_attempts += attempts
        if attempts == 1:
            first_attempt_count += 1

        fb_key = f"feedback_history_{spec.name}"
        fb = st.session_state.get(fb_key)
        did_pass = fb.passed if fb else True
        if did_pass:
            passed_count += 1

        # Per-stage score: start at 100, -15 per extra attempt, -20 if failed
        stage_score = max(0, 100 - (attempts - 1) * 15 - (0 if did_pass else 20))
        # Rating: good / ok / weak
        if stage_score >= 80:
            rating = "good"
        elif stage_score >= 50:
            rating = "ok"
        else:
            rating = "weak"
        stage_scores[spec.name] = {"score": stage_score, "rating": rating, "attempts": attempts, "passed": did_pass}

    # Time bonus/penalty
    time_target = TOTAL_CASE_TIME_LIMIT.get(sess.category, 1800)
    actual_time = sess.total_time_seconds or 0
    time_ratio = actual_time / time_target if time_target else 1
    if time_ratio <= 1.0:
        time_modifier = 5  # finished within time
    elif time_ratio <= 1.3:
        time_modifier = 0
    else:
        time_modifier = -10

    overall_score = int(
        sum(s["score"] for s in stage_scores.values()) / total_stages
        + time_modifier
    )
    overall_score = max(0, min(100, overall_score))

    # Score tier
    if overall_score >= 75:
        score_tier = "score-high"
        score_verdict = "Strong performance"
    elif overall_score >= 50:
        score_tier = "score-mid"
        score_verdict = "Developing — review the gaps below"
    else:
        score_tier = "score-low"
        score_verdict = "Needs work — focus on the weak stages"

    # --- Render header with score ---
    st.markdown(
        '<div class="main-header">'
        "<h1>Session Complete</h1>"
        f"<p>{_display_name(sess.case_id)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Forced conclusion notice
    if sess.forced_conclusion:
        st.warning(
            "This session was time-expired. Some stages were skipped. "
            "In a real interview, managing time is critical."
        )

    # --- Score card + key metrics ---
    col_score, col_metrics = st.columns([1, 2])
    with col_score:
        st.markdown(
            f'<div class="score-card {score_tier}">'
            f'<div class="score-number">{overall_score}</div>'
            f'<div class="score-label">{score_verdict}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_metrics:
        m1, m2, m3 = st.columns(3)
        with m1:
            if actual_time:
                minutes = int(actual_time // 60)
                seconds = int(actual_time % 60)
                st.metric("Total Time", f"{minutes}m {seconds}s")
            elif st.session_state.get("timer_start"):
                st.metric("Total Time", _format_elapsed(st.session_state.timer_start))
        with m2:
            pct = int(first_attempt_count / total_stages * 100) if total_stages else 0
            st.metric("First-Try Pass", f"{first_attempt_count}/{total_stages}", delta=f"{pct}%")
        with m3:
            avg_attempts = total_attempts / total_stages if total_stages else 0
            st.metric("Avg Attempts", f"{avg_attempts:.1f}")

    # --- Biggest strength & area to improve ---
    sorted_stages = sorted(stage_scores.items(), key=lambda x: x[1]["score"])
    weakest = sorted_stages[0]
    strongest = sorted_stages[-1]
    weak_label = STAGE_DISPLAY_NAMES.get(weakest[0], _display_name(weakest[0]))
    strong_label = STAGE_DISPLAY_NAMES.get(strongest[0], _display_name(strongest[0]))

    col_s, col_w = st.columns(2)
    with col_s:
        st.success(f"Strongest: **{strong_label}** — passed on attempt {strongest[1]['attempts']}")
    with col_w:
        weak_detail = f"took {weakest[1]['attempts']} attempts" if weakest[1]["attempts"] > 1 else "review feedback below"
        st.warning(f"Focus area: **{weak_label}** — {weak_detail}")

    st.markdown("---")

    # --- Stage-by-stage review (collapsed by default) ---
    for spec in stages:
        val = getattr(sess, spec.name)
        label = _stage_label(spec.name, stages)
        info = stage_scores[spec.name]

        # Color indicator
        indicator = {"good": "🟢", "ok": "🟡", "weak": "🔴"}[info["rating"]]
        attempt_note = f" — attempt {info['attempts']}" if info["attempts"] > 1 else ""
        expander_label = f"{indicator} {label}{attempt_note}"

        with st.expander(expander_label):
            if isinstance(val, list):
                for j, item in enumerate(val, 1):
                    _md(f"{j}. {item}")
            else:
                _md(val if val else "_No response_")

            # Show any stored coach feedback for this stage
            feedback_history_key = f"feedback_history_{spec.name}"
            if feedback_history_key in st.session_state:
                fb = st.session_state[feedback_history_key]
                _render_feedback_display(fb)

            # Show any data reveal for this stage
            _render_data_reveal(spec.name)

    st.markdown("---")

    # Learning progression recommendation
    all_sessions = analytics.load_completed_sessions()
    if len(all_sessions) >= 2:
        trends = analytics.compute_improvement_trends(all_sessions)
        if trends["enough_data"]:
            st.subheader("Your Learning Progress")
            col1, col2 = st.columns(2)
            with col1:
                time_delta = trends["time_change_pct"]
                time_label = "faster" if time_delta < 0 else "slower"
                st.metric(
                    "Avg Time (recent vs early)",
                    f"{abs(time_delta):.0f}% {time_label}",
                    delta=f"{-time_delta:.0f}%",
                )
            with col2:
                rate_delta = trends["rate_change_pct"]
                st.metric(
                    "First-Attempt Rate Change",
                    f"{rate_delta:+.0f}%",
                    delta=f"{rate_delta:.0f}%",
                )

            # Next difficulty recommendation
            current_diff = st.session_state.get("difficulty", "intermediate")
            recommended = trends["recommended_next"]
            diff_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
            if diff_order.get(recommended, 0) > diff_order.get(current_diff, 0):
                st.success(
                    f"Based on your progress, you're ready to move up to **{recommended}** difficulty. "
                    "Challenge yourself with tighter coaching and less hand-holding."
                )
            elif recommended == current_diff:
                st.info(
                    f"You're performing well at **{current_diff}** level. "
                    "Keep practicing to build consistency before moving up."
                )
            else:
                st.info(
                    f"Consider solidifying your skills at **{recommended}** level before advancing."
                )
            st.markdown("---")

    st.balloons()

    if st.button("Start New Case", type="primary", use_container_width=True):
        _full_reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Page: Session Flow
# ---------------------------------------------------------------------------


def _render_session_chrome():
    """Render the session header, prompt, progress bar, and stage stepper.

    Always called so users have full context regardless of whether
    coach feedback is being shown.
    """
    sess = st.session_state.session
    case = st.session_state.selected_case
    stages = _get_active_stages()
    stage_idx = current_stage_index()

    # Header
    st.markdown(
        f'<div class="main-header">'
        f"<h1>Case: {_display_name(sess.case_id)}</h1>"
        f"</div>",
        unsafe_allow_html=True,
    )
    _md(f"**Prompt:** {case['prompt']}")
    if case.get("context"):
        with st.expander("View full case context"):
            _render_case_context(case["context"])

    # Progress
    total = len(stages)
    st.progress(stage_idx / total, text=f"Progress: {stage_idx}/{total} stages complete")

    # Stage stepper breadcrumb
    stepper_parts = []
    for i, s in enumerate(stages):
        name = STAGE_DISPLAY_NAMES.get(s.name, _display_name(s.name))
        if i < stage_idx:
            stepper_parts.append(f'<span style="color:#2e7d32;font-weight:600;">{i+1}. {name}</span>')
        elif i == stage_idx:
            stepper_parts.append(
                f'<span style="background:#1a237e;color:white;padding:2px 8px;border-radius:10px;'
                f'font-weight:700;">{i+1}. {name}</span>'
            )
        else:
            stepper_parts.append(f'<span style="color:#9e9e9e;">{i+1}. {name}</span>')
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:6px 14px;font-size:0.82rem;'
        'line-height:1.8;">'
        + " ".join(stepper_parts)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.divider()


def render_session():
    sess = st.session_state.session
    case = st.session_state.selected_case
    stages = _get_active_stages()
    stage_idx = current_stage_index()

    total = len(stages)

    # Show completed stages (most recent one expanded)
    for i in range(stage_idx):
        spec = stages[i]
        val = getattr(sess, spec.name)
        is_most_recent = i == stage_idx - 1
        attempt_count = st.session_state.get(f"attempts_{spec.name}", 1)
        label = f"{_stage_label(spec.name, stages)} (completed)"
        if attempt_count > 1:
            label += f"  -- Attempt {attempt_count}"
        with st.expander(label, expanded=is_most_recent):
            if isinstance(val, list):
                for j, item in enumerate(val, 1):
                    _md(f"{j}. {item}")
            else:
                _md(val)

    # Hard time pressure at advanced: force to conclusion
    difficulty = st.session_state.get("difficulty", "intermediate")
    if difficulty == "advanced" and st.session_state.get("timer_start"):
        elapsed_total = time.time() - st.session_state.timer_start
        case_limit = TOTAL_CASE_TIME_LIMIT.get(sess.category, 1500)
        conclusion_idx = next(
            (i for i, s in enumerate(stages) if s.name == "conclusion"), total - 1
        )
        if elapsed_total > case_limit and stage_idx < conclusion_idx:
            st.error(
                "**TIME'S UP** — In a real MBB interview, you'd need to wrap up now. "
                "Jumping to your conclusion."
            )
            sess.time_expired = True
            sess.forced_conclusion = True
            for skip_spec in stages[stage_idx:conclusion_idx]:
                val = getattr(sess, skip_spec.name)
                if val is None or val == "" or val == []:
                    setattr(
                        sess, skip_spec.name,
                        ["[Time expired]"] if skip_spec.multi else "[Time expired]",
                    )
            save_session()
            stage_idx = conclusion_idx

    # All done?
    if stage_idx >= total:
        render_session_review()
        return

    # Current stage
    spec = stages[stage_idx]
    stage_name = spec.name

    # Show any data reveal from the previous stage
    if stage_idx > 0:
        prev_stage = stages[stage_idx - 1].name
        _render_data_reveal(prev_stage)

    # Show exhibit data before exhibit_interpretation stage
    if stage_name == "exhibit_interpretation":
        exhibit = case.get("exhibit", {}) if case else {}
        if exhibit:
            st.markdown(
                f'<div class="interviewer-card">'
                f'<div class="interviewer-label">Exhibit: {_escape_markdown(exhibit.get("title", "Data"))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.code(exhibit.get("data", ""), language=None)

    # Start stage timer (only set once per stage)
    start_key = f"stage_start_{stage_name}"
    if start_key not in st.session_state:
        st.session_state[start_key] = time.time()

    # Stage header with attempt badge
    attempt_count = st.session_state.get(f"attempts_{stage_name}", 1)
    display = STAGE_DISPLAY_NAMES.get(stage_name, _display_name(stage_name))
    if attempt_count > 1:
        st.markdown(
            f'### {display} <span class="attempt-badge">Attempt {attempt_count}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"### {display}")
    st.markdown(STAGE_DESCRIPTIONS.get(stage_name, ""))

    # Framework selection for frame/structure stages
    if spec.offer_frameworks:
        _render_framework_input(stage_name)
    elif spec.multi:
        _render_multi_input(stage_name, spec.item_name, stage_idx)
    else:
        _render_single_input(stage_name, stage_idx)


def _render_previous_response(stage_name: str):
    """Show the user's previous response if revising a stage."""
    prev_key = f"previous_response_{stage_name}"
    prev = st.session_state.get(prev_key)
    if prev:
        with st.expander("Your previous response", expanded=True):
            if isinstance(prev, list):
                for j, item in enumerate(prev, 1):
                    _md(f"{j}. {item}")
            else:
                _md(prev)
            # Also show the feedback that prompted revision
            fb_key = f"feedback_history_{stage_name}"
            fb = st.session_state.get(fb_key)
            if fb:
                st.markdown("**Coach feedback on this response:**")
                _render_feedback_display(fb)


def _render_framework_input(stage_name: str):
    """Render framework selection + explanation for frame/structure stages."""
    _render_previous_response(stage_name)
    _render_stage_hints(stage_name)
    frameworks = load_frameworks()

    selected = None
    if frameworks:
        fw_options = [f"{fw['name']} — {fw['full_name']}" for fw in frameworks]
        selected = st.selectbox(
            "Select a framework:",
            options=[None] + fw_options,
            key=f"fw_select_{stage_name}",
            format_func=lambda x: "Choose a framework..." if x is None else x,
        )

        # Show description for selected framework
        if selected:
            fw_name = selected.split(" — ")[0]
            fw = next((f for f in frameworks if f["name"] == fw_name), None)
            if fw:
                st.caption(f"**{fw['name']}:** {_escape_markdown(fw['description'])}")

    explanation = st.text_area(
        "Explain how you'll apply this framework to the problem:",
        key=f"fw_explain_{stage_name}",
        height=150,
        placeholder="Why did you choose this framework? What are the key areas you'll analyze?",
    )

    if st.button("Submit", key=f"submit_{stage_name}"):
        if not selected:
            st.error("Please select a framework.")
            return
        if not explanation or len(explanation.strip()) < 10:
            st.error("Please explain how you'll apply the framework.")
            return

        # Build the combined response
        fw_name = selected.split(" — ")[0]
        response = f"Framework: {fw_name}\n\n{explanation.strip()}"

        setattr(st.session_state.session, stage_name, response)
        save_session()
        _after_stage_submit(stage_name, response)


def _render_stage_hints(stage_name: str):
    """Show hint, structure, MBB context, examples, and pro tips based on difficulty."""
    difficulty = st.session_state.get("difficulty", "intermediate")
    hints = STAGE_HINTS.get(stage_name)
    if not hints:
        return

    if difficulty == "beginner":
        # Beginner: single collapsed expander to avoid wall of text
        with st.expander("Help me get started"):
            st.info(hints["hint"])
            st.markdown("**Suggested structure:**")
            st.markdown(hints["structure"])
            if hints.get("mbb_context"):
                st.markdown("---")
                st.markdown(f"**Why this stage matters in MBB interviews:** {hints['mbb_context']}")
            if hints.get("example_standard") and hints.get("example_elite"):
                st.markdown("---")
                st.markdown("**Standard response** (adequate but won't stand out):")
                st.markdown(f"> {_escape_markdown(hints['example_standard'])}")
                st.markdown("**Elite response** (what top candidates do):")
                st.markdown(f"> {_escape_markdown(hints['example_elite'])}")

    elif difficulty == "intermediate":
        # Intermediate: single collapsed expander, pro tip as standalone nudge
        with st.expander("Need a hint?"):
            st.info(hints["hint"])
            st.markdown(hints["structure"])
            if hints.get("mbb_context"):
                st.markdown("---")
                st.markdown(f"**MBB Context:** {hints['mbb_context']}")
            if hints.get("example_standard") and hints.get("example_elite"):
                st.markdown("---")
                st.markdown("**Standard:**")
                st.markdown(f"> {_escape_markdown(hints['example_standard'])}")
                st.markdown("**Elite:**")
                st.markdown(f"> {_escape_markdown(hints['example_elite'])}")
        pro_tip = MBB_PRO_TIPS.get(stage_name)
        if pro_tip:
            st.info(pro_tip)

    else:
        # Advanced: no hints, but show pro tips as a brief nudge
        pro_tip = MBB_PRO_TIPS.get(stage_name)
        if pro_tip:
            with st.expander("Pro tip"):
                st.markdown(pro_tip)


def _render_single_input(stage_name: str, stage_idx: int):
    """Render a text area for a single-response stage."""
    _render_previous_response(stage_name)
    _render_stage_hints(stage_name)
    text_key = f"input_{stage_name}"
    response = st.text_area(
        "Your response:",
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
    _render_previous_response(stage_name)
    _render_stage_hints(stage_name)
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
                _md(f"{j + 1}. {item}")
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
        display = STAGE_DISPLAY_NAMES.get(stage_name, _display_name(stage_name))
        if items and st.button(f"Done with {display}", key=f"done_{stage_name}"):
            setattr(st.session_state.session, stage_name, list(items))
            save_session()
            _after_stage_submit(stage_name, items)
            # Clean up temp items
            st.session_state.pop(items_key, None)
            st.session_state.pop(add_counter_key, None)

    if not items:
        st.caption(f"Add at least one {item_name.lower()} before proceeding.")


def _after_stage_submit(stage_name: str, content):
    """Handle post-submission: record timing, show success and offer coach feedback."""
    st.session_state[f"submitted_{stage_name}"] = True
    st.session_state[f"content_{stage_name}"] = content
    # Record stage timing
    start_key = f"stage_start_{stage_name}"
    if start_key in st.session_state:
        elapsed = time.time() - st.session_state[start_key]
        st.session_state.session.stage_times[stage_name] = elapsed
    st.rerun()


def _clear_stage_input_keys():
    """Remove transient input keys from session state."""
    keys_to_remove = [
        k
        for k in st.session_state
        if k.startswith(
            ("input_", "items_", "new_item_", "submitted_", "content_", "feedback_",
             "add_counter_", "previous_response_", "data_reveal_", "stage_start_",
             "probe_", "probe_done_", "probe_input_", "clarifying_answers_")
        )
    ]
    for k in keys_to_remove:
        del st.session_state[k]


def _full_reset():
    """Clear all session-related keys for a fresh start."""
    for key in ["session", "selected_case", "active_stage", "page", "timer_start"]:
        st.session_state.pop(key, None)
    # Clear attempt counters, feedback, and stage timers for ALL possible stages
    for stage_name in STAGE_DISPLAY_NAMES:
        st.session_state.pop(f"attempts_{stage_name}", None)
        st.session_state.pop(f"feedback_history_{stage_name}", None)
    _clear_stage_input_keys()


def _get_case_context_text() -> str:
    """Return the case prompt + context as a single string for the AI coach."""
    case = st.session_state.get("selected_case", {})
    parts = []
    if case.get("prompt"):
        parts.append(case["prompt"])
    if case.get("context"):
        parts.append(case["context"])
    return "\n\n".join(parts)


def _render_data_reveal(stage_name: str):
    """Show any interviewer data reveal stored for this stage."""
    reveal_key = f"data_reveal_{stage_name}"
    reveal = st.session_state.get(reveal_key)
    if reveal:
        type_labels = {"data": "New Data", "constraint": "New Constraint", "curveball": "Curveball"}
        type_label = type_labels.get(reveal.reveal_type, "Interviewer")
        st.markdown(
            f'<div class="interviewer-card">'
            f'<div class="interviewer-label">Interviewer — {_escape_markdown(type_label)}</div>'
            f'{_escape_markdown(reveal.reveal)}'
            f'</div>',
            unsafe_allow_html=True,
        )


def _handle_revise(spec):
    """Render revise button and handle stage reset on click."""
    if st.button("Revise this stage", key=f"revise_{spec.name}"):
        attempts_key = f"attempts_{spec.name}"
        st.session_state[attempts_key] = st.session_state.get(attempts_key, 1) + 1
        prev_key = f"previous_response_{spec.name}"
        content = st.session_state.get(f"content_{spec.name}")
        if content:
            st.session_state[prev_key] = content
        sess = st.session_state.session
        if spec.multi:
            setattr(sess, spec.name, [])
        else:
            setattr(sess, spec.name, None)
        sess.save()
        _clear_submitted(spec.name)
        st.rerun()


def _handle_probe(spec, case_context: str, difficulty: str) -> bool:
    """Render multi-turn probe question. Returns True if blocking on probe input."""
    if difficulty == "beginner":
        return False
    probe_key = f"probe_{spec.name}"
    probe_done_key = f"probe_done_{spec.name}"
    if st.session_state.get(probe_done_key):
        return False
    if probe_key not in st.session_state:
        content = st.session_state.get(f"content_{spec.name}", "")
        probe_q = coach.generate_probe_question(spec.name, content, case_context, difficulty)
        if probe_q:
            st.session_state[probe_key] = probe_q
    if probe_key not in st.session_state:
        return False
    st.markdown("---")
    st.markdown(
        f'<div class="interviewer-card">'
        f'<div class="interviewer-label">Interviewer Follow-Up</div>'
        f'{_escape_markdown(st.session_state[probe_key])}'
        f'</div>',
        unsafe_allow_html=True,
    )
    probe_response = st.text_area(
        "Your response:",
        key=f"probe_input_{spec.name}",
        height=100,
        placeholder="Answer the follow-up question...",
    )
    if st.button("Submit follow-up", key=f"probe_submit_{spec.name}"):
        if probe_response and probe_response.strip():
            st.session_state.session.probe_responses[spec.name] = probe_response
            st.session_state[probe_done_key] = True
            save_session()
            st.rerun()
        else:
            st.error("Please provide a response to the follow-up question.")
    return True


def _handle_clarifying_answers(spec, case_context: str):
    """Render interviewer answers to clarifying questions."""
    if spec.name != "clarifying_questions":
        return
    answers_key = f"clarifying_answers_{spec.name}"
    if answers_key not in st.session_state:
        content = st.session_state.get(f"content_{spec.name}", [])
        if content:
            answers = coach.answer_clarifying_questions(
                content if isinstance(content, list) else [content],
                case_context,
            )
            st.session_state[answers_key] = answers
    answers = st.session_state.get(answers_key, [])
    if not answers:
        return
    content = st.session_state.get(f"content_{spec.name}", [])
    questions = content if isinstance(content, list) else [content]
    st.markdown("---")
    st.markdown(
        '<div class="interviewer-card">'
        '<div class="interviewer-label">Interviewer Answers</div>',
        unsafe_allow_html=True,
    )
    for q, a in zip(questions, answers):
        st.markdown(f"**Q:** {_escape_markdown(q)}")
        st.markdown(f"**A:** {_escape_markdown(a)}")
        st.markdown("")
    st.markdown("</div>", unsafe_allow_html=True)


def _handle_data_reveal(spec, case_context: str, difficulty: str, show_spinner: bool = False):
    """Generate and render data reveal for a stage."""
    reveal_key = f"data_reveal_{spec.name}"
    if reveal_key not in st.session_state:
        content = st.session_state.get(f"content_{spec.name}", "")
        case_data = st.session_state.get("selected_case")
        if show_spinner:
            with st.spinner("Interviewer is preparing new information..."):
                reveal = coach.generate_data_reveal(
                    spec.name, content, case_context, difficulty, case_data=case_data,
                )
        else:
            reveal = coach.generate_data_reveal(
                spec.name, content, case_context, difficulty, case_data=case_data,
            )
        if reveal and reveal.reveal:
            st.session_state[reveal_key] = reveal
    _render_data_reveal(spec.name)


def render_coach_feedback():
    """Check if any stage was just submitted and handle coach evaluation.

    When AI coaching is enabled, the coach acts as a gate: the user
    must pass before advancing.  If not passed, the stage is cleared
    so the user can revise.  With heuristic coaching (no API key) or
    coach disabled, the user always advances.
    """
    ai_gating = st.session_state.get("coach_enabled", False) and coach.is_ai_enabled()
    stages = _get_active_stages()
    case_context = _get_case_context_text()
    difficulty = st.session_state.get("difficulty", "intermediate")

    for spec in stages:
        submitted_key = f"submitted_{spec.name}"
        if not st.session_state.get(submitted_key):
            continue

        feedback_key = f"feedback_{spec.name}"
        coach_enabled = st.session_state.get("coach_enabled", False)

        # Show previously completed stages (collapsed)
        sess = st.session_state.session
        for i, s in enumerate(stages):
            if s.name == spec.name:
                break
            val = getattr(sess, s.name)
            if val is not None and val != "" and val != []:
                with st.expander(f"{_stage_label(s.name, stages)} (completed)"):
                    if isinstance(val, list):
                        for j, item in enumerate(val, 1):
                            _md(f"{j}. {item}")
                    else:
                        _md(val)

        # Show stage header and user's response for context
        display = STAGE_DISPLAY_NAMES.get(spec.name, _display_name(spec.name))
        st.markdown(f"### {display}")
        content = st.session_state.get(f"content_{spec.name}")
        if content:
            with st.expander("Your response", expanded=True):
                if isinstance(content, list):
                    for j, item in enumerate(content, 1):
                        _md(f"{j}. {item}")
                else:
                    _md(content)

        # --- Evaluate feedback (shared for both paths) ---
        if ai_gating or coach_enabled:
            if feedback_key not in st.session_state:
                with st.spinner("Interviewer is evaluating your response..."):
                    fb = coach.provide_feedback(spec.name, content, case_context, difficulty)
                st.session_state[feedback_key] = fb

        # --- AI gating mode ---
        if ai_gating:
            fb = st.session_state[feedback_key]
            _render_feedback_display(fb)

            if fb.passed:
                st.markdown(
                    '<div class="feedback-pass">You passed this stage!</div>',
                    unsafe_allow_html=True,
                )
                _render_time_warning(spec.name)
                st.session_state[f"feedback_history_{spec.name}"] = fb
                if _handle_probe(spec, case_context, difficulty):
                    return True
                _handle_clarifying_answers(spec, case_context)
                _handle_data_reveal(spec, case_context, difficulty, show_spinner=True)
                if st.button("Continue to next stage", key=f"continue_{spec.name}"):
                    _clear_submitted(spec.name, clear_previous=True)
                    st.rerun()
            else:
                st.markdown(
                    '<div class="feedback-fail">Not yet -- revise your response and resubmit.</div>',
                    unsafe_allow_html=True,
                )
                _handle_revise(spec)
            return True

        # --- Optional coach mode (heuristic or no API key) ---
        st.success("Stage saved.")
        _render_time_warning(spec.name)

        if coach_enabled and feedback_key in st.session_state:
            fb = st.session_state[feedback_key]
            _render_feedback_display(fb)
            st.session_state[f"feedback_history_{spec.name}"] = fb
            if not fb.passed:
                st.markdown(
                    '<div class="feedback-fail">Not yet -- revise your response and resubmit.</div>',
                    unsafe_allow_html=True,
                )
                _handle_revise(spec)
                return True

        if _handle_probe(spec, case_context, difficulty):
            return True
        _handle_clarifying_answers(spec, case_context)
        _handle_data_reveal(spec, case_context, difficulty)

        if st.button("Continue to next stage", key=f"continue_{spec.name}"):
            _clear_submitted(spec.name, clear_previous=True)
            st.rerun()
        return True

    return False


def _render_feedback_display(fb: coach.CoachFeedback):
    """Render coach feedback in styled cards."""
    st.markdown("---")
    st.markdown("**Coach Feedback**")
    st.markdown(
        f'<div class="feedback-card feedback-strengths">'
        f"<strong>Strengths:</strong> {_escape_markdown(fb.strengths)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="feedback-card feedback-gaps">'
        f"<strong>Gaps:</strong> {_escape_markdown(fb.gaps)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="feedback-card feedback-questions">'
        f"<strong>Questions to consider:</strong> {_escape_markdown(fb.questions)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_time_warning(stage_name: str):
    """Show a time warning if the stage took longer than target."""
    sess = st.session_state.session
    elapsed = sess.stage_times.get(stage_name)
    if elapsed is None:
        return
    target = get_stage_time_limit(sess.category, stage_name)
    warning = format_time_warning(elapsed, target)
    if warning:
        if "WARNING" in warning:
            st.warning(warning)
        else:
            st.info(warning)


def _clear_submitted(stage_name: str, clear_previous: bool = False):
    """Remove submission-related keys for a stage."""
    for prefix in ("submitted_", "content_", "feedback_", "items_", "add_counter_"):
        st.session_state.pop(f"{prefix}{stage_name}", None)
    if clear_previous:
        st.session_state.pop(f"previous_response_{stage_name}", None)


# ---------------------------------------------------------------------------
# Page: Mental Math Drills
# ---------------------------------------------------------------------------


def _parse_user_number(text: str) -> float | None:
    """Parse a user-entered number, handling common formats like 28.8M, 5K, $, commas."""
    if not text:
        return None
    s = text.strip().replace(",", "").replace("$", "").replace(" ", "")
    multiplier = 1
    s_upper = s.upper()
    if s_upper.endswith("B"):
        multiplier = 1_000_000_000
        s = s[:-1]
    elif s_upper.endswith("M"):
        multiplier = 1_000_000
        s = s[:-1]
    elif s_upper.endswith("K"):
        multiplier = 1_000
        s = s[:-1]
    elif s_upper.endswith("%"):
        s = s[:-1]
    try:
        return float(s) * multiplier
    except ValueError:
        return None


def render_equations():
    """Reference page listing common case interview equations by frequency."""
    st.markdown(
        '<div class="main-header">'
        "<h1>Equations Cheat Sheet</h1>"
        "<p>The formulas that come up most often in case interviews, ranked by frequency</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    equations = [
        {
            "name": "Profit",
            "formula": "Profit = Revenue − Costs",
            "detail": "Revenue = Price × Quantity. Costs = Fixed Costs + Variable Costs. The single most common equation in casing.",
            "freq": "Almost every case",
        },
        {
            "name": "Revenue",
            "formula": "Revenue = Price × Volume",
            "detail": "Volume can be broken into # of customers × units per customer, or market size × market share.",
            "freq": "Almost every case",
        },
        {
            "name": "Total Costs",
            "formula": "Total Costs = Fixed Costs + (Variable Cost per Unit × Volume)",
            "detail": "Fixed costs don't change with volume (rent, salaries, depreciation). Variable costs scale with output (materials, commissions, shipping). Always split costs into these two buckets first.",
            "freq": "Almost every case",
        },
        {
            "name": "Market Size (Top-Down)",
            "formula": "Market Size = Population × % Applicable × Adoption Rate × Price",
            "detail": "Start from a large known number and narrow down with successive filters. Classic for market-sizing cases.",
            "freq": "Very high — every market-sizing case",
        },
        {
            "name": "Market Size (Bottom-Up)",
            "formula": "Market Size = # of Locations × Capacity per Location × Utilization × Price",
            "detail": "Build up from individual units of supply. Use when the supply side is easier to estimate.",
            "freq": "Very high — every market-sizing case",
        },
        {
            "name": "Break-Even Volume",
            "formula": "Break-Even Volume = Fixed Costs ÷ (Price − Variable Cost per Unit)",
            "detail": "The number of units you need to sell to cover all fixed costs. Contribution margin = Price − VC.",
            "freq": "High — profitability & new-venture cases",
        },
        {
            "name": "Break-Even Time (Payback Period)",
            "formula": "Payback Period = Initial Investment ÷ Annual Net Cash Flow",
            "detail": "How many years until the investment pays for itself. Quick proxy when NPV isn't asked for.",
            "freq": "High — investment & expansion cases",
        },
        {
            "name": "ROI / Return on Investment",
            "formula": "ROI = (Gain − Cost) ÷ Cost",
            "detail": "Express as a percentage. Use to compare investment alternatives on an apples-to-apples basis.",
            "freq": "High",
        },
        {
            "name": "Growth Rate / CAGR",
            "formula": "CAGR = (End Value ÷ Start Value)^(1/n) − 1",
            "detail": "In interviews, often approximated: ~7% CAGR ≈ doubling every 10 years. Use the Rule of 72.",
            "freq": "High",
        },
        {
            "name": "Customer Lifetime Value (CLV)",
            "formula": "CLV = Avg Revenue per Customer × Avg Customer Lifespan − Acquisition Cost",
            "detail": "Simplified version; compare to Customer Acquisition Cost (CAC). Healthy businesses: CLV > 3× CAC.",
            "freq": "Medium-High — pricing & growth strategy cases",
        },
        {
            "name": "Market Share",
            "formula": "Market Share = Company Revenue ÷ Total Market Revenue",
            "detail": "Can also be measured in units. Useful for competitive positioning analysis.",
            "freq": "Medium-High",
        },
        {
            "name": "Capacity Utilization",
            "formula": "Utilization = Actual Output ÷ Maximum Possible Output",
            "detail": "Key in operations cases. Low utilization → fix demand or cut capacity; high utilization → bottleneck risk.",
            "freq": "Medium — operations & supply-chain cases",
        },
        {
            "name": "Gross / Operating / Net Margin",
            "formula": "Margin = (Revenue − Relevant Costs) ÷ Revenue",
            "detail": "Gross excludes SG&A; Operating excludes interest/tax; Net is bottom-line. Know typical ranges by industry.",
            "freq": "Medium",
        },
        {
            "name": "NPV (Simplified)",
            "formula": "NPV = Σ [Cash Flow_t ÷ (1 + r)^t] − Initial Investment",
            "detail": "Rarely need to compute fully in an interview, but know the concept. Positive NPV = value-creating.",
            "freq": "Medium — investment cases",
        },
        {
            "name": "Contribution Margin",
            "formula": "Contribution Margin = Price − Variable Cost per Unit",
            "detail": "What each unit contributes toward covering fixed costs. Foundation of break-even analysis.",
            "freq": "Medium",
        },
        {
            "name": "Productivity / Efficiency",
            "formula": "Productivity = Output ÷ Input (e.g., Revenue per Employee)",
            "detail": "Use to benchmark against competitors. Common inputs: labor hours, FTEs, capital deployed.",
            "freq": "Medium — operations cases",
        },
        {
            "name": "Price Elasticity of Demand",
            "formula": "Elasticity = % Change in Quantity Demanded ÷ % Change in Price",
            "detail": "|E| > 1 = elastic (price-sensitive); |E| < 1 = inelastic. Guides pricing decisions.",
            "freq": "Low-Medium — pricing cases",
        },
    ]

    for i, eq in enumerate(equations):
        with st.expander(f"**{i + 1}. {eq['name']}** — _{eq['freq']}_", expanded=(i < 3)):
            st.markdown(f"##### `{eq['formula']}`")
            st.caption(eq["detail"])

    st.info("**Tip:** In an interview, always state the equation *before* plugging in numbers — it shows structured thinking and lets the interviewer course-correct early.")


def render_rules_of_thumb():
    """Reference page listing numerical rules of thumb by frequency."""
    st.markdown(
        '<div class="main-header">'
        "<h1>Rules of Thumb</h1>"
        "<p>Quick numerical benchmarks that save you time in market-sizing and estimation cases</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    categories = [
        {
            "title": "Demographics & Population",
            "icon": "👥",
            "rules": [
                ("US population", "~330 million", "Almost every US market-sizing case"),
                ("World population", "~8 billion", "Global market-sizing cases"),
                ("US households", "~130 million (~2.5 people/household)", "Consumer-product & housing cases"),
                ("US life expectancy", "~78 years", "Healthcare, insurance, pension cases"),
                ("US median age", "~38 years", "Demographic segmentation"),
                ("US median household income", "~$75K", "Consumer spending & pricing cases"),
                ("China / India population", "~1.4B each", "Emerging-market cases"),
                ("EU population", "~450 million", "European market-sizing"),
                ("Urban vs. rural (US)", "~83% urban", "Location-strategy cases"),
            ],
        },
        {
            "title": "Math Shortcuts",
            "icon": "🔢",
            "rules": [
                ("Rule of 72", "72 ÷ growth rate % ≈ doubling time in years", "CAGR & compounding questions"),
                ("Percentage shortcuts", "10% is easy; 5% = half of 10%; 1% = move decimal", "Every mental-math moment"),
                ("Multiply by 5", "Multiply by 10, divide by 2", "Speeds up estimation arithmetic"),
                ("Quick squaring", "Use (a+b)(a−b) = a²−b². e.g., 48² = 50×46 + 4 = 2304", "Rare but impressive"),
                ("Seconds in a year", "~30 million (π × 10⁷)", "Throughput & capacity problems"),
                ("Minutes in a day", "~1,440", "Operations & scheduling problems"),
                ("Hours in a year", "~8,760 (~9,000 for easy math)", "Utilization & capacity"),
            ],
        },
        {
            "title": "Business & Economics",
            "icon": "💼",
            "rules": [
                ("US GDP", "~$27 trillion", "Macro-level market-sizing"),
                ("S&P 500 average return", "~10% nominal / ~7% real", "Investment-case benchmarks"),
                ("Typical gross margin (product co.)", "40–60%", "Profitability sanity checks"),
                ("Typical gross margin (software/SaaS)", "70–85%", "Tech industry cases"),
                ("Typical net margin (healthy company)", "10–20%", "Profitability sanity checks"),
                ("Restaurant net margin", "3–9%", "Restaurant & food-service cases"),
                ("Grocery net margin", "1–3%", "Retail cases"),
                ("CLV-to-CAC ratio (healthy)", "> 3:1", "Growth strategy & marketing spend"),
                ("SaaS churn (good)", "< 5% annual for enterprise", "Subscription-business cases"),
            ],
        },
        {
            "title": "Consumer & Retail",
            "icon": "🛒",
            "rules": [
                ("US cars on the road", "~280 million", "Automotive & transportation cases"),
                ("US new-car sales/year", "~15–16 million", "Auto industry sizing"),
                ("Average car lifespan", "~12 years / 200K miles", "Replacement-cycle calculations"),
                ("US smartphone penetration", "~85%+ of adults", "Mobile/app market sizing"),
                ("Average US consumer spending", "~$65K/year per household", "Consumer-market cases"),
                ("US restaurant meals/week per person", "~4–5", "Food-service market sizing"),
                ("US flights per year", "~900 million passenger trips", "Airline & travel cases"),
            ],
        },
        {
            "title": "Operations & Infrastructure",
            "icon": "🏗️",
            "rules": [
                ("US airports (commercial)", "~500 (top 30 handle ~70% of traffic)", "Aviation & logistics cases"),
                ("US hospitals", "~6,000", "Healthcare operations cases"),
                ("US gas stations", "~150,000", "Energy & convenience-retail cases"),
                ("US Starbucks locations", "~16,000", "Retail density benchmarks"),
                ("US McDonald's locations", "~13,500", "QSR benchmarks"),
                ("US Walmart stores", "~4,700", "Big-box retail benchmarks"),
                ("Semi truck capacity", "~45,000 lbs / ~20 tons", "Logistics & freight cases"),
                ("Standard shipping container", "~20 or 40 ft, ~50K lbs max", "Supply-chain cases"),
            ],
        },
    ]

    for cat in categories:
        st.subheader(f"{cat['icon']}  {cat['title']}")
        for rule_name, value, context in cat["rules"]:
            st.markdown(f"- **{rule_name}:** {value} — _{context}_")
        st.markdown("")

    st.info("**Tip:** You don't need to memorize every number — focus on the top 10–15 you reach for most often. In an interview, state your assumption explicitly: *\"I'll assume US population of roughly 330 million\"* — the interviewer will redirect if needed.")


def render_mental_math():
    """Mental math drill page — timed problems across five categories."""
    st.markdown(
        '<div class="main-header">'
        "<h1>Mental Math Drills</h1>"
        "<p>Build the speed that separates good candidates from great ones</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # State keys
    if "mm_phase" not in st.session_state:
        st.session_state.mm_phase = "select"  # select | drill | results

    phase = st.session_state.mm_phase

    # ------------------------------------------------------------------
    # Phase 1: Category & difficulty selection
    # ------------------------------------------------------------------
    if phase == "select":
        st.markdown("### Choose a drill")
        st.markdown(
            "Each drill is **10 timed problems**. Target: **30 seconds each**. "
            "Accuracy and speed are both scored."
        )

        col1, col2 = st.columns(2)
        with col1:
            cat_options = list(mental_math.DRILL_CATEGORIES.keys()) + ["mixed"]
            cat_labels = {**mental_math.DRILL_CATEGORIES, "mixed": "Mixed (All Categories)"}
            selected_cat = st.selectbox(
                "Category",
                cat_options,
                format_func=lambda c: cat_labels[c],
                key="mm_cat_select",
            )
        with col2:
            difficulty = st.session_state.get("difficulty", "intermediate")
            st.markdown(f"**Difficulty:** {difficulty.capitalize()}")
            st.caption("Matches your coaching difficulty setting.")

        # Show category description
        if selected_cat != "mixed":
            st.info(mental_math.CATEGORY_DESCRIPTIONS[selected_cat])
        else:
            st.info("A random mix of problems from all five categories — just like a real interview.")

        st.markdown("")
        if st.button("Start Drill", type="primary", use_container_width=True):
            difficulty = st.session_state.get("difficulty", "intermediate")
            if selected_cat == "mixed":
                drills = mental_math.generate_mixed_set(10, difficulty)
            else:
                drills = mental_math.generate_drill_set(selected_cat, 10, difficulty)
            st.session_state.mm_drills = drills
            st.session_state.mm_index = 0
            st.session_state.mm_results = []
            st.session_state.mm_drill_start = time.time()
            st.session_state.mm_phase = "drill"
            st.session_state.mm_category = selected_cat
            st.rerun()

        st.markdown("---")
        st.markdown("### What gets tested")
        cats = list(mental_math.DRILL_CATEGORIES.items())
        row1 = st.columns(3)
        row2 = st.columns(2)
        all_cols = row1 + row2
        for col, (cat_key, cat_name) in zip(all_cols, cats):
            with col:
                st.markdown(f"**{cat_name}**")
                st.caption(mental_math.CATEGORY_DESCRIPTIONS[cat_key])

        if st.button("Back to cases"):
            st.session_state.page = "selection"
            st.rerun()

    # ------------------------------------------------------------------
    # Phase 2: Active drill
    # ------------------------------------------------------------------
    elif phase == "drill":
        drills = st.session_state.mm_drills
        idx = st.session_state.mm_index
        results = st.session_state.mm_results

        if idx >= len(drills):
            # All done — move to results
            st.session_state.mm_phase = "results"
            st.rerun()
            return

        drill = drills[idx]
        total = len(drills)

        # Progress
        st.progress((idx) / total, text=f"Problem {idx + 1} of {total}")

        # Category badge
        cat_name = mental_math.DRILL_CATEGORIES.get(drill.category, drill.category)
        st.caption(f"Category: {cat_name}")

        # Question
        st.markdown(f"### {drill.question}")

        # Timer for this problem
        problem_start = st.session_state.get("mm_problem_start")
        if problem_start is None:
            st.session_state.mm_problem_start = time.time()
            problem_start = st.session_state.mm_problem_start

        # Hint expander
        if drill.hint:
            with st.expander("Hint"):
                st.markdown(drill.hint)

        # Answer input
        answer_text = st.text_input(
            "Your answer:",
            key=f"mm_answer_{idx}",
            placeholder="e.g. 28.8M, 14.5%, 50000",
        )

        col_submit, col_skip = st.columns([3, 1])
        with col_submit:
            submitted = st.button("Submit", type="primary", use_container_width=True)
        with col_skip:
            skipped = st.button("Skip", use_container_width=True)

        if submitted or skipped:
            elapsed = time.time() - problem_start
            if skipped:
                user_val = None
                correct = False
            else:
                user_val = _parse_user_number(answer_text)
                if user_val is None:
                    st.error("Could not parse your answer. Use numbers like 28.8M, 14.5, 50000, etc.")
                    return
                correct = drill.check(user_val)

            result = mental_math.DrillResult(
                drill=drill,
                user_answer=user_val,
                correct=correct,
                time_seconds=elapsed,
            )
            results.append(result)

            # Show immediate feedback
            formatted_answer = mental_math.format_answer(drill.answer)
            if drill.unit and drill.unit != "$":
                formatted_answer += f" {drill.unit}"

            if correct:
                st.success(f"Correct! Answer: {formatted_answer} ({elapsed:.1f}s)")
            elif skipped:
                st.warning(f"Skipped. Answer: {formatted_answer}")
            else:
                user_formatted = mental_math.format_answer(user_val) if user_val is not None else "N/A"
                st.error(f"Not quite. You said {user_formatted} — answer: {formatted_answer} ({elapsed:.1f}s)")

            # Advance
            st.session_state.mm_index = idx + 1
            st.session_state.mm_problem_start = None
            time.sleep(1.2)
            st.rerun()

    # ------------------------------------------------------------------
    # Phase 3: Results
    # ------------------------------------------------------------------
    elif phase == "results":
        results = st.session_state.get("mm_results", [])
        if not results:
            st.session_state.mm_phase = "select"
            st.rerun()
            return

        # Build session for scoring
        category = st.session_state.get("mm_category", "mixed")
        difficulty = st.session_state.get("difficulty", "intermediate")
        drill_session = mental_math.DrillSession(
            category=category,
            difficulty=difficulty,
            results=results,
        )

        # Score card
        score = drill_session.score
        if score >= 70:
            score_class = "score-high"
        elif score >= 40:
            score_class = "score-mid"
        else:
            score_class = "score-low"

        st.markdown(
            f'<div class="score-card {score_class}">'
            f'<div class="score-number">{score}</div>'
            f'<div class="score-label">Mental Math Score</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Correct", f"{drill_session.total_correct}/{drill_session.total_count}")
        with col2:
            st.metric("Accuracy", f"{drill_session.accuracy * 100:.0f}%")
        with col3:
            st.metric("Avg Time", f"{drill_session.avg_time:.1f}s")
        with col4:
            target_label = "On pace" if drill_session.avg_time <= mental_math.TARGET_TIME else "Too slow"
            st.metric("Speed", target_label)

        st.markdown("---")

        # Problem-by-problem breakdown
        st.markdown("### Problem Breakdown")
        for i, r in enumerate(results, 1):
            formatted_answer = mental_math.format_answer(r.drill.answer)
            if r.drill.unit and r.drill.unit != "$":
                formatted_answer += f" {r.drill.unit}"

            if r.correct:
                icon = "&#9989;"
                color_class = "stage-result-good"
            else:
                icon = "&#10060;"
                color_class = "stage-result-weak"

            user_str = mental_math.format_answer(r.user_answer) if r.user_answer is not None else "Skipped"
            time_str = f"{r.time_seconds:.1f}s"
            speed_icon = "" if r.time_seconds <= mental_math.TARGET_TIME else " (slow)"

            with st.expander(f"{icon} Problem {i}: {r.drill.question[:60]}... — {time_str}{speed_icon}"):
                st.markdown(f"**Your answer:** {user_str}")
                st.markdown(f"**Correct answer:** {formatted_answer}")
                st.markdown(f"**Time:** {time_str}")
                if r.drill.hint:
                    st.markdown(f"**Tip:** {r.drill.hint}")

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Try Again", type="primary", use_container_width=True):
                st.session_state.mm_phase = "select"
                st.session_state.pop("mm_results", None)
                st.session_state.pop("mm_drills", None)
                st.rerun()
        with col2:
            if st.button("Back to cases", use_container_width=True):
                st.session_state.mm_phase = "select"
                st.session_state.page = "selection"
                st.rerun()


# ---------------------------------------------------------------------------
# Page: Portfolio Analytics
# ---------------------------------------------------------------------------


def render_portfolio():
    """Show portfolio analytics across completed sessions."""
    st.markdown(
        '<div class="main-header">'
        "<h1>Portfolio Analytics</h1>"
        "<p>Track your progress across case study sessions</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    sessions = analytics.load_completed_sessions()
    if not sessions:
        st.info("No completed sessions yet. Finish a case to see your analytics here.")
        if st.button("Back to cases"):
            st.session_state.page = "selection"
            st.rerun()
        return

    stats = analytics.compute_portfolio_stats(sessions)

    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Sessions Completed", stats["total_sessions"])
    with col2:
        avg_min = stats["avg_time_seconds"] / 60 if stats["avg_time_seconds"] else 0
        st.metric("Avg Time", f"{avg_min:.1f} min")
    with col3:
        rate = stats["avg_first_attempt_rate"] * 100
        st.metric("First-Attempt Pass Rate", f"{rate:.0f}%")
    with col4:
        most_cat = max(stats["by_category"], key=lambda c: stats["by_category"][c]["count"]) if stats["by_category"] else "N/A"
        st.metric("Most Practiced", _display_name(most_cat))

    st.markdown("---")

    # Category breakdown
    if stats["by_category"]:
        st.subheader("By Category")
        for cat, data in stats["by_category"].items():
            avg_cat_min = data["avg_time"] / 60 if data["avg_time"] else 0
            st.markdown(f"- **{_display_name(cat)}:** {data['count']} sessions, avg {avg_cat_min:.1f} min")

    # Difficulty breakdown
    if stats["by_difficulty"]:
        st.subheader("By Difficulty")
        for diff, count in sorted(stats["by_difficulty"].items()):
            st.markdown(f"- **{diff.capitalize()}:** {count} sessions")

    st.markdown("---")

    # Stage performance
    stage_perf = analytics.compute_stage_performance(sessions)
    if stage_perf:
        st.subheader("Stage Performance")
        for sp in stage_perf:
            avg_min = sp["avg_time_seconds"] / 60
            rate = sp["first_attempt_rate"] * 100
            label = STAGE_DISPLAY_NAMES.get(sp["stage"], _display_name(sp["stage"]))
            st.markdown(f"- **{label}:** avg {avg_min:.1f} min, {rate:.0f}% first-attempt pass ({sp['sample_size']} samples)")

    st.markdown("---")

    # Improvement trends
    trends = analytics.compute_improvement_trends(sessions)
    if trends.get("enough_data"):
        st.subheader("Improvement Trends")
        col1, col2, col3 = st.columns(3)
        with col1:
            time_delta = trends["time_change_pct"]
            time_label = "faster" if time_delta < 0 else "slower"
            st.metric(
                "Time Trend",
                f"{abs(time_delta):.0f}% {time_label}",
                delta=f"{-time_delta:.0f}%",
            )
        with col2:
            rate_delta = trends["rate_change_pct"]
            st.metric(
                "First-Attempt Trend",
                f"{rate_delta:+.0f}%",
                delta=f"{rate_delta:.0f}%",
            )
        with col3:
            rec = trends["recommended_next"]
            st.metric("Recommended Level", rec.capitalize())

        # Per-stage improvement details
        stage_imps = trends.get("stage_improvements", [])
        if stage_imps:
            with st.expander("Stage-by-stage trends"):
                for si in stage_imps:
                    label = STAGE_DISPLAY_NAMES.get(si["stage"], _display_name(si["stage"]))
                    early_min = si["early_avg"] / 60
                    recent_min = si["recent_avg"] / 60
                    arrow = "faster" if si["change_pct"] < 0 else "slower"
                    st.markdown(
                        f"- **{label}:** {early_min:.1f} min → {recent_min:.1f} min "
                        f"({abs(si['change_pct']):.0f}% {arrow})"
                    )

        st.markdown("---")

    # Recent sessions
    recent = analytics.compute_recent_sessions(sessions)
    if recent:
        st.subheader("Recent Sessions")
        for r in recent:
            rate = r["first_attempt_rate"] * 100
            st.markdown(
                f"- **{_display_name(r['case_id'])}** ({_display_name(r['category'])}, {r['difficulty']}) "
                f"-- {r['total_minutes']} min, {rate:.0f}% first-attempt"
            )

    if st.button("Back to cases", type="primary"):
        st.session_state.page = "selection"
        st.rerun()


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

        if st.button("Rules of Thumb", use_container_width=True):
            st.session_state.page = "rules_of_thumb"
            st.rerun()

        if st.button("Equations Cheat Sheet", use_container_width=True):
            st.session_state.page = "equations"
            st.rerun()

        if st.button("Mental Math Drills", use_container_width=True):
            st.session_state.page = "mental_math"
            st.rerun()

        if st.button("Portfolio Analytics", use_container_width=True):
            st.session_state.page = "portfolio"
            st.rerun()

        # Coach & difficulty settings
        st.divider()
        st.subheader("Settings")

        st.toggle(
            "Enable Coach Mode",
            key="coach_enabled",
            help="When enabled, you receive feedback after each stage and must pass before advancing.",
        )
        if st.session_state.get("coach_enabled") and coach.is_ai_enabled():
            st.caption("AI coaching active — you must pass each stage to advance.")
        elif st.session_state.get("coach_enabled"):
            st.caption("Heuristic coaching (set GEMINI_API_KEY for AI).")

        difficulty_labels = {
            "beginner": "Beginner",
            "intermediate": "Intermediate",
            "advanced": "Advanced",
        }
        current_diff = st.session_state.get("difficulty", "intermediate")
        selected_diff = st.radio(
            "Coaching Difficulty",
            options=list(DIFFICULTY_LEVELS),
            index=list(DIFFICULTY_LEVELS).index(current_diff),
            format_func=lambda d: difficulty_labels[d],
            key="difficulty_radio",
        )
        st.session_state.difficulty = selected_diff

        st.divider()
        st.subheader("Previous Sessions")

        session_files = list_sessions()
        if not session_files:
            st.caption("No saved sessions yet.")
        else:
            # Use selectbox + load button instead of a long list of buttons
            session_labels = [_format_session_label(sf.stem) for sf in session_files[:20]]
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
            "category": getattr(sess, "category", "strategy"),
            "difficulty": "unknown",
        }
    st.session_state.session = sess
    st.session_state.selected_case = case
    st.session_state.active_stage = current_stage_index()
    st.session_state.page = "session"
    # Set timer start to now for resumed sessions
    st.session_state.timer_start = time.time()
    # Initialize attempt counters for this category's stages
    stages = _get_active_stages()
    for spec in stages:
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
    if "difficulty" not in st.session_state:
        st.session_state.difficulty = "intermediate"

    render_sidebar()

    if st.session_state.page == "portfolio":
        render_portfolio()
    elif st.session_state.page == "mental_math":
        render_mental_math()
    elif st.session_state.page == "equations":
        render_equations()
    elif st.session_state.page == "rules_of_thumb":
        render_rules_of_thumb()
    elif st.session_state.page == "session" and "session" in st.session_state:
        _render_session_chrome()
        # Check if we need to show post-submission feedback before rendering the next stage
        if not render_coach_feedback():
            render_session()
    else:
        render_case_selection()


if __name__ == "__main__":
    main()
