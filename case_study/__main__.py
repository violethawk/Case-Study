"""
Entrypoint for the Case‑Study CLI.

Invoking ``python -m case_study`` will call the ``main`` function in
the :mod:`cli` module.  See the documentation in that module for
details about available commands.
"""

from .cli import main


if __name__ == "__main__":  # pragma: no cover
    main()