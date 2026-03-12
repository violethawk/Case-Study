"""
Case loading utilities.

Cases are stored in JSON files under the ``data/`` directory.  Each
case contains an identifier, a prompt, optional context and a
difficulty rating.  This module exposes functions to load all cases
and to select specific cases by identifier.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any


CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_cases.json"


def load_cases(path: Path = CASES_FILE) -> List[Dict[str, Any]]:
    """Load the list of case definitions from the given JSON file.

    Parameters
    ----------
    path : Path
        Path to a JSON file containing an array of case definitions.

    Returns
    -------
    list of dict
        The parsed list of case dictionaries.
    """
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_case_by_id(case_id: str, cases: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Return the case dictionary matching the given identifier or ``None`` if not found."""
    return next((c for c in cases if c.get("id") == case_id), None)