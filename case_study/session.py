"""
Session management for Case‑Study.

This module provides utilities to create, persist and retrieve
reasoning sessions.  A session encapsulates the user’s reasoning
trace for a particular case study: the framing, list of hypotheses,
analytical steps, updated hypotheses and the final conclusion.  Sessions
are serialised to JSON in the ``sessions/`` directory for later
resumption or review.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"


@dataclass
class Session:
    """Represents a reasoning session for a single case study."""

    case_id: str
    timestamp: str
    category: str = "strategy"
    restatement: str | None = None
    framework: str | None = None
    frame: str | None = None
    assumptions: list[str] = field(default_factory=list)
    equation: str | None = None
    hypotheses: list[str] = field(default_factory=list)
    analyses: list[str] = field(default_factory=list)
    updates: list[str] = field(default_factory=list)
    conclusion: str | None = None
    additional_insights: str | None = None
    structure: str | None = None
    setup: str | None = None
    calculation: list[str] = field(default_factory=list)
    sanity_check: str | None = None
    sensitivity: str | None = None
    # Analytics fields
    stage_times: dict[str, float] = field(default_factory=dict)
    total_time_seconds: float = 0.0
    completed_at: str | None = None
    stage_attempts: dict[str, int] = field(default_factory=dict)
    difficulty: str | None = None
    coach_enabled: bool = False

    @classmethod
    def new(cls, case_id: str, category: str = "strategy") -> "Session":
        """Create a new session instance for the given case.

        The timestamp is generated in the user's local timezone.
        """
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        return cls(case_id=case_id, timestamp=timestamp, category=category)

    @property
    def filename(self) -> str:
        """Return a suggested filename for storing this session."""
        return f"{self.case_id}_{self.timestamp}.json"

    def save(self, directory: Path = SESSIONS_DIR) -> None:
        """Persist the session to a JSON file in the given directory."""
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / self.filename
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "Session":
        """Load a session from a JSON file."""
        path = Path(filepath)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(
            case_id=data.get("case_id"),
            timestamp=data.get("timestamp"),
            category=data.get("category", "strategy"),
            restatement=data.get("restatement"),
            framework=data.get("framework"),
            frame=data.get("frame"),
            assumptions=data.get("assumptions", []),
            equation=data.get("equation"),
            hypotheses=data.get("hypotheses", []),
            analyses=data.get("analyses", []),
            updates=data.get("updates", []),
            conclusion=data.get("conclusion"),
            additional_insights=data.get("additional_insights"),
            structure=data.get("structure"),
            setup=data.get("setup"),
            calculation=data.get("calculation", []),
            sanity_check=data.get("sanity_check"),
            sensitivity=data.get("sensitivity"),
            stage_times=data.get("stage_times", {}),
            total_time_seconds=data.get("total_time_seconds", 0.0),
            completed_at=data.get("completed_at"),
            stage_attempts=data.get("stage_attempts", {}),
            difficulty=data.get("difficulty"),
            coach_enabled=data.get("coach_enabled", False),
        )


def list_sessions(directory: Path = SESSIONS_DIR) -> list[Path]:
    """Return a list of session file paths sorted by modification time (newest first).

    The directory is created if it does not already exist.  Only files
    ending with ``.json`` are included.
    """
    directory.mkdir(parents=True, exist_ok=True)
    sessions = [p for p in directory.iterdir() if p.suffix == ".json"]
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions