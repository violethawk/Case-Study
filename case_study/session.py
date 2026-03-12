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
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from zoneinfo import ZoneInfo


SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"


@dataclass
class Session:
    """Represents a reasoning session for a single case study."""

    case_id: str
    timestamp: str
    restatement: Optional[str] = None
    frame: Optional[str] = None
    assumptions: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    analyses: List[str] = field(default_factory=list)
    updates: List[str] = field(default_factory=list)
    conclusion: Optional[str] = None
    additional_insights: Optional[str] = None

    @classmethod
    def new(cls, case_id: str) -> "Session":
        """Create a new session instance for the given case.

        The timestamp is generated in the user's local timezone.
        """
        tz = ZoneInfo("America/Chicago")
        timestamp = datetime.now(tz).strftime("%Y-%m-%d_%H-%M-%S")
        return cls(case_id=case_id, timestamp=timestamp)

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
            restatement=data.get("restatement"),
            frame=data.get("frame"),
            assumptions=data.get("assumptions", []),
            hypotheses=data.get("hypotheses", []),
            analyses=data.get("analyses", []),
            updates=data.get("updates", []),
            conclusion=data.get("conclusion"),
            additional_insights=data.get("additional_insights"),
        )


def list_sessions(directory: Path = SESSIONS_DIR) -> List[Path]:
    """Return a list of session file paths sorted by modification time.

    The directory is created if it does not already exist.  Only files
    ending with ``.json`` are included.
    """
    directory.mkdir(parents=True, exist_ok=True)
    sessions = [p for p in directory.iterdir() if p.suffix == ".json"]
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions