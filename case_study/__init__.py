"""
Case‑Study package initialization.

This package provides a command line tool for guiding users through a
structured reasoning process for business case studies.  See
``python -m case_study --help`` for usage information.

Modules
-------

- :mod:`cli` – top level command line interface.
- :mod:`engine` – orchestrates the reasoning workflow.
- :mod:`session` – maintains and persists session state.
- :mod:`cases` – loads case definitions from JSON files.
- :mod:`coach` – optional AI coach for feedback (stubbed by default).
- :mod:`validation` – input validation utilities.

"""

__all__ = [
    "cli",
    "engine",
    "session",
    "cases",
    "coach",
    "validation",
]