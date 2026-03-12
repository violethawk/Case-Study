"""
Command line interface for Case‑Study.

This module defines the top level `main` function which parses
command line arguments and dispatches commands to the appropriate
handlers in the engine and session modules.  To see available commands
run ``python -m case_study --help``.
"""

from __future__ import annotations

import argparse

from . import engine
from .session import list_sessions


def main(argv: list[str] | None = None) -> None:
    """Entry point invoked by ``python -m case_study``.

    This function parses arguments and dispatches to the
    corresponding subcommand.  It exits with status code 0 on
    successful completion or non‑zero on error.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Case‑Study: practice structured reasoning for consulting‑style "
            "case interviews and strategic decision‑making."
        ),
        epilog=(
            "For more information see the project documentation in the README."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start
    start_parser = subparsers.add_parser(
        "start",
        help="Start a new case study session",
    )
    start_parser.add_argument(
        "--coach",
        action="store_true",
        help="Enable coach mode. If omitted you will be prompted at runtime.",
    )

    # resume
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a saved session",
    )
    resume_parser.add_argument(
        "session_file",
        type=str,
        help="Path to a saved session file (e.g. sessions/case_id_timestamp.json)",
    )
    resume_parser.add_argument(
        "--coach",
        action="store_true",
        help="Enable coach mode. If omitted you will be prompted at runtime.",
    )

    # list
    list_parser = subparsers.add_parser(
        "list",
        help="List saved sessions",
    )

    args = parser.parse_args(argv)

    if args.command == "start":
        # Determine coach flag; None means interactive prompt
        coach_flag = True if args.coach else None
        engine.start_session(coach_flag)
    elif args.command == "resume":
        coach_flag = True if args.coach else None
        engine.resume_session(args.session_file, coach_flag)
    elif args.command == "list":
        sess_files = list_sessions()
        if not sess_files:
            print("No sessions found.")
        else:
            print("Saved sessions:")
            for path in sess_files:
                print(f"  {path}")
    else:
        parser.print_help()