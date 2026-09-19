"""Logging setup for scripts and the application.

Library modules call ``logging.getLogger(__name__)`` and never configure
handlers; only entry points (scripts, the Streamlit app, tests that want output)
call :func:`configure_logging`. That keeps import side effects out of the library
and leaves the caller in control of where messages go.
"""

from __future__ import annotations

import logging
import sys

DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def configure_logging(level: int | str = logging.INFO, stream=sys.stderr) -> None:
    """Configure root logging once, idempotently.

    Args:
        level: logging level, as a level constant or its name.
        stream: destination; defaults to stderr so piped stdout stays parseable.
    """
    root = logging.getLogger()
    if any(getattr(h, "_edupro", False) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt="%H:%M:%S"))
    handler._edupro = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
