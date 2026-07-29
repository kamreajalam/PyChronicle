"""Shared configuration for PyChronicle.

The single most important thing this module does is give every part of the
project (tracer, UI, tools, tests) the SAME database file path, no matter
which directory the command was launched from.

Before this existed, `tracer.py` used the relative default "pychronicle.db"
(resolved against the current working directory) while `app.py` used a
hardcoded "src/tracer/pychronicle.db". Running the tracer from the project
root therefore wrote events into one file while the UI read a completely
different one, which is why the Trace Timeline showed 0 events.
"""

import os

DEFAULT_DB_FILENAME = "pychronicle.db"

# Set PYCHRONICLE_DB to point every component at a different database file.
ENV_DB_PATH = "PYCHRONICLE_DB"


def project_root() -> str:
    """Absolute path of the repository root (this file is <root>/src/tracer/config.py)."""
    here = os.path.dirname(os.path.abspath(__file__))          # <root>/src/tracer
    return os.path.dirname(os.path.dirname(here))              # <root>


def get_db_path() -> str:
    """Canonical database path used by the tracer and the UI.

    Resolution order:
      1. The PYCHRONICLE_DB environment variable, if set.
      2. <project_root>/pychronicle.db
    """
    override = os.environ.get(ENV_DB_PATH)
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(project_root(), DEFAULT_DB_FILENAME)


def legacy_db_paths() -> list:
    """Older database locations kept only so their data can be migrated."""
    return [
        os.path.join(project_root(), "src", "tracer", DEFAULT_DB_FILENAME),
    ]
