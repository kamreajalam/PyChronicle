"""
trace_loader.py

Integration/support module for PyChronicle.

This module isolates the trace-data loading and formatting logic that
previously lived inline inside app.py's PyChronicleApp class. Pulling it
out makes the loading behavior independently testable (no Textual event
loop required) and gives the JSON / SQLite / demo-data code paths a single,
well-defined integration point that both the TUI and any future front-end
(e.g. a web viewer, or a CLI export command) can reuse.

No behavioral change was made to the original loading logic - this is a
straight extraction plus two small, additive fixes:
  * SQLite rows are now returned as dicts with the same "code"/"vars"/"event"
    keys the JSON path produces, so both sources are shaped identically for
    any consumer.
  * Corrupt/partial JSON or DB rows no longer crash the loader - they are
    skipped/handled and the loader falls through to the next source instead
    of raising all the way up to the caller.
"""

import copy
import json
import os
import sqlite3

# Fallback demo data used only when neither a JSON trace file nor a SQLite
# trace database can be found. Kept identical to the original app.py content.
DEMO_STEPS = {
    "step1": {
        "code": "# Step 1: Initialize values\nx = 5\ny = 10\ntotal = 0",
        "vars": "x = 5\ny = 10\ntotal = 0",
        "event": "System initialized variables in local scope memory workspace.",
    },
    "step2": {
        "code": "# Step 2: Add values together\nx = 5\ny = 10\ntotal = x + y",
        "vars": "x = 5\ny = 10\ntotal = 15",
        "event": "Executed addition operator. Variable 'total' updated to 15.",
    },
}


def format_vars(vars_data):
    """
    Normalize a step's "vars" value into a display-ready string.

    Historically "vars" has been stored as a preformatted string
    ("x = 5\\ny = 10"), but some tracers emit a real dict
    ({"x": 5, "y": 10}). This function accepts either and always returns
    a string, so callers never need to branch on the input type.
    """
    if isinstance(vars_data, dict):
        return "\n".join(f"{k} = {v}" for k, v in vars_data.items())
    if vars_data is None:
        return ""
    return str(vars_data)


def load_from_json(json_path="trace_output.json"):
    """
    Attempt to load trace steps from a JSON file.
    Returns a dict of steps on success, or None if the file is missing,
    empty, or invalid.
    """
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        if data:
            return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading JSON trace '{json_path}': {e}")
    return None


def load_from_sqlite(db_path="pychronicle.db"):
    """
    Attempt to load trace steps from a SQLite database.
    Returns a dict of steps on success, or None if the file is missing,
    empty, or the query fails.
    """
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT step_id, code, vars, event FROM execution_steps ORDER BY id ASC"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
        if rows:
            return {
                row[0]: {"code": row[1], "vars": row[2], "event": row[3]}
                for row in rows
            }
    except sqlite3.Error as e:
        print(f"Error reading SQLite trace '{db_path}': {e}")
    return None


def load_tracer_data(json_path="trace_output.json", db_path="pychronicle.db"):
    """
    Load execution trace steps, trying (in order):
      1. A JSON trace file (json_path)
      2. A SQLite trace database (db_path)
      3. Built-in demo data, if neither source is available

    Returns a tuple: (steps_dict, source) where source is one of
    "json", "sqlite", or "demo" so callers/tests can tell which path
    was actually used.
    """
    data = load_from_json(json_path)
    if data:
        return data, "json"

    data = load_from_sqlite(db_path)
    if data:
        return data, "sqlite"

    # Deep copy so callers can safely mutate the returned dict (e.g. the
    # per-step "vars" formatting the app does) without corrupting the
    # shared DEMO_STEPS constant for later calls/tests.
    return copy.deepcopy(DEMO_STEPS), "demo"
