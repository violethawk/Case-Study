"""
Portfolio analytics for case study sessions.

Aggregates performance metrics across completed sessions to help
candidates track progress and identify areas for improvement.
"""

from __future__ import annotations

from pathlib import Path

from .session import Session, list_sessions, SESSIONS_DIR


def load_completed_sessions(directory: Path = SESSIONS_DIR) -> list[Session]:
    """Load all sessions that have a completed_at timestamp."""
    sessions = []
    for path in list_sessions(directory):
        try:
            sess = Session.load(path)
            if sess.completed_at:
                sessions.append(sess)
        except Exception:
            continue
    return sessions


def compute_portfolio_stats(sessions: list[Session]) -> dict:
    """Aggregate statistics across completed sessions."""
    if not sessions:
        return {
            "total_sessions": 0,
            "avg_time_seconds": 0,
            "avg_first_attempt_rate": 0,
            "by_category": {},
            "by_difficulty": {},
        }

    total = len(sessions)
    times = [s.total_time_seconds for s in sessions if s.total_time_seconds > 0]
    avg_time = sum(times) / len(times) if times else 0

    # First-attempt rate: stages passed on first try / total stages
    first_attempt_rates = []
    for s in sessions:
        if s.stage_attempts:
            first = sum(1 for v in s.stage_attempts.values() if v == 1)
            rate = first / len(s.stage_attempts) if s.stage_attempts else 0
            first_attempt_rates.append(rate)
    avg_first_attempt = (
        sum(first_attempt_rates) / len(first_attempt_rates)
        if first_attempt_rates
        else 0
    )

    # By category
    by_category: dict[str, dict] = {}
    for s in sessions:
        cat = s.category or "unknown"
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total_time": 0}
        by_category[cat]["count"] += 1
        by_category[cat]["total_time"] += s.total_time_seconds
    for cat, data in by_category.items():
        data["avg_time"] = data["total_time"] / data["count"] if data["count"] else 0

    # By difficulty
    by_difficulty: dict[str, int] = {}
    for s in sessions:
        diff = s.difficulty or "unknown"
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1

    return {
        "total_sessions": total,
        "avg_time_seconds": avg_time,
        "avg_first_attempt_rate": avg_first_attempt,
        "by_category": by_category,
        "by_difficulty": by_difficulty,
    }


def compute_stage_performance(sessions: list[Session]) -> list[dict]:
    """Compute average time and first-attempt rate per stage across sessions."""
    stage_data: dict[str, dict] = {}

    for s in sessions:
        for stage_name, elapsed in s.stage_times.items():
            if stage_name not in stage_data:
                stage_data[stage_name] = {"times": [], "first_attempts": 0, "total": 0}
            stage_data[stage_name]["times"].append(elapsed)
            stage_data[stage_name]["total"] += 1
            attempts = s.stage_attempts.get(stage_name, 1)
            if attempts == 1:
                stage_data[stage_name]["first_attempts"] += 1

    result = []
    for name, data in stage_data.items():
        avg_time = sum(data["times"]) / len(data["times"]) if data["times"] else 0
        first_rate = data["first_attempts"] / data["total"] if data["total"] else 0
        result.append({
            "stage": name,
            "avg_time_seconds": round(avg_time, 1),
            "first_attempt_rate": round(first_rate, 2),
            "sample_size": data["total"],
        })

    return result


def compute_improvement_trends(sessions: list[Session]) -> dict:
    """Compare first-half vs second-half performance to show improvement.

    Returns a dict with overall and per-stage trend data.
    """
    if len(sessions) < 2:
        return {"enough_data": False}

    # Sort by completed_at chronologically
    sorted_sessions = sorted(sessions, key=lambda s: s.completed_at or "")
    mid = len(sorted_sessions) // 2
    first_half = sorted_sessions[:mid]
    second_half = sorted_sessions[mid:]

    def _half_stats(half: list[Session]) -> dict:
        times = [s.total_time_seconds for s in half if s.total_time_seconds > 0]
        avg_time = sum(times) / len(times) if times else 0
        first_rates = []
        for s in half:
            if s.stage_attempts:
                first = sum(1 for v in s.stage_attempts.values() if v == 1)
                first_rates.append(first / len(s.stage_attempts))
        avg_rate = sum(first_rates) / len(first_rates) if first_rates else 0
        return {"avg_time": avg_time, "avg_first_attempt_rate": avg_rate, "count": len(half)}

    first_stats = _half_stats(first_half)
    second_stats = _half_stats(second_half)

    # Per-stage trends
    stage_trends: dict[str, dict] = {}
    for label, half in [("early", first_half), ("recent", second_half)]:
        for s in half:
            for stage_name, elapsed in s.stage_times.items():
                if stage_name not in stage_trends:
                    stage_trends[stage_name] = {"early_times": [], "recent_times": []}
                stage_trends[stage_name][f"{label}_times"].append(elapsed)

    stage_improvements = []
    for stage_name, data in stage_trends.items():
        early_avg = sum(data["early_times"]) / len(data["early_times"]) if data["early_times"] else 0
        recent_avg = sum(data["recent_times"]) / len(data["recent_times"]) if data["recent_times"] else 0
        if early_avg > 0:
            change_pct = ((recent_avg - early_avg) / early_avg) * 100
        else:
            change_pct = 0
        stage_improvements.append({
            "stage": stage_name,
            "early_avg": round(early_avg, 1),
            "recent_avg": round(recent_avg, 1),
            "change_pct": round(change_pct, 1),
        })

    # Difficulty progression
    difficulty_order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    recent_difficulties = [
        difficulty_order.get(s.difficulty or "beginner", 0)
        for s in sorted_sessions[-min(5, len(sorted_sessions)):]
    ]
    avg_recent_diff = sum(recent_difficulties) / len(recent_difficulties) if recent_difficulties else 0

    return {
        "enough_data": True,
        "first_half": first_stats,
        "second_half": second_stats,
        "time_change_pct": round(
            ((second_stats["avg_time"] - first_stats["avg_time"]) / first_stats["avg_time"] * 100)
            if first_stats["avg_time"] > 0 else 0, 1
        ),
        "rate_change_pct": round(
            ((second_stats["avg_first_attempt_rate"] - first_stats["avg_first_attempt_rate"])
             / first_stats["avg_first_attempt_rate"] * 100)
            if first_stats["avg_first_attempt_rate"] > 0 else 0, 1
        ),
        "stage_improvements": stage_improvements,
        "avg_recent_difficulty": avg_recent_diff,
        "recommended_next": (
            "advanced" if avg_recent_diff >= 1.5
            else "intermediate" if avg_recent_diff >= 0.5
            else "beginner"
        ),
    }


def compute_recent_sessions(sessions: list[Session], limit: int = 10) -> list[dict]:
    """Return summary dicts for the most recent completed sessions."""
    # Sort by completed_at descending
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.completed_at or "",
        reverse=True,
    )

    result = []
    for s in sorted_sessions[:limit]:
        total_stages = len(s.stage_attempts) if s.stage_attempts else 0
        first_attempt = (
            sum(1 for v in s.stage_attempts.values() if v == 1)
            if s.stage_attempts
            else 0
        )
        minutes = s.total_time_seconds / 60 if s.total_time_seconds else 0
        result.append({
            "case_id": s.case_id,
            "category": s.category,
            "difficulty": s.difficulty or "unknown",
            "completed_at": s.completed_at or "",
            "total_minutes": round(minutes, 1),
            "first_attempt_rate": (
                round(first_attempt / total_stages, 2) if total_stages else 0
            ),
        })

    return result
