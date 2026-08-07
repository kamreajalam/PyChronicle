"""
Unit tests for trace_loader.py.

Covers the three data-source integration paths (JSON file, SQLite database,
built-in demo fallback), their priority order, and the vars-formatting
helper that the TUI depends on.
"""

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trace_loader import (
    DEMO_STEPS,
    format_vars,
    load_from_json,
    load_from_sqlite,
    load_tracer_data,
)


# ---------------------------------------------------------------------------
# format_vars
# ---------------------------------------------------------------------------

def test_format_vars_with_string_passthrough():
    assert format_vars("x = 5\ny = 10") == "x = 5\ny = 10"


def test_format_vars_with_dict_converts_to_readable_lines():
    result = format_vars({"x": 5, "y": 10})
    assert result == "x = 5\ny = 10"


def test_format_vars_with_none_returns_empty_string():
    assert format_vars(None) == ""


def test_format_vars_with_non_string_scalar_is_stringified():
    assert format_vars(42) == "42"


# ---------------------------------------------------------------------------
# load_from_json
# ---------------------------------------------------------------------------

def test_load_from_json_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    assert load_from_json(str(missing)) is None


def test_load_from_json_valid_file_returns_data(tmp_path):
    trace_file = tmp_path / "trace_output.json"
    payload = {"step1": {"code": "x = 1", "vars": "x = 1", "event": "init"}}
    trace_file.write_text(json.dumps(payload))

    result = load_from_json(str(trace_file))
    assert result == payload


def test_load_from_json_empty_object_returns_none(tmp_path):
    trace_file = tmp_path / "trace_output.json"
    trace_file.write_text("{}")

    assert load_from_json(str(trace_file)) is None


def test_load_from_json_malformed_file_does_not_raise(tmp_path):
    trace_file = tmp_path / "trace_output.json"
    trace_file.write_text("{not valid json,,,")

    # Should not raise; should degrade gracefully to None so the loader
    # can fall through to the next data source.
    assert load_from_json(str(trace_file)) is None


# ---------------------------------------------------------------------------
# load_from_sqlite
# ---------------------------------------------------------------------------

def _make_sqlite_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE execution_steps (id INTEGER PRIMARY KEY, step_id TEXT, code TEXT, vars TEXT, event TEXT)"
    )
    conn.executemany(
        "INSERT INTO execution_steps (step_id, code, vars, event) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_load_from_sqlite_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does_not_exist.db"
    assert load_from_sqlite(str(missing)) is None


def test_load_from_sqlite_valid_db_returns_ordered_steps(tmp_path):
    db_path = tmp_path / "pychronicle.db"
    _make_sqlite_db(
        str(db_path),
        [
            ("step1", "x = 1", "x = 1", "init"),
            ("step2", "x = 2", "x = 2", "increment"),
        ],
    )

    result = load_from_sqlite(str(db_path))
    assert list(result.keys()) == ["step1", "step2"]
    assert result["step1"] == {"code": "x = 1", "vars": "x = 1", "event": "init"}


def test_load_from_sqlite_missing_table_does_not_raise(tmp_path):
    db_path = tmp_path / "pychronicle.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()

    assert load_from_sqlite(str(db_path)) is None


# ---------------------------------------------------------------------------
# load_tracer_data (integration: source priority + fallback)
# ---------------------------------------------------------------------------

def test_load_tracer_data_prefers_json_over_sqlite(tmp_path):
    json_path = tmp_path / "trace_output.json"
    db_path = tmp_path / "pychronicle.db"

    json_path.write_text(json.dumps({"step1": {"code": "a", "vars": "a", "event": "a"}}))
    _make_sqlite_db(str(db_path), [("stepA", "b", "b", "b")])

    data, source = load_tracer_data(str(json_path), str(db_path))
    assert source == "json"
    assert "step1" in data


def test_load_tracer_data_falls_back_to_sqlite_when_no_json(tmp_path):
    json_path = tmp_path / "trace_output.json"  # does not exist
    db_path = tmp_path / "pychronicle.db"
    _make_sqlite_db(str(db_path), [("stepA", "b", "b", "b")])

    data, source = load_tracer_data(str(json_path), str(db_path))
    assert source == "sqlite"
    assert "stepA" in data


def test_load_tracer_data_falls_back_to_demo_when_nothing_available(tmp_path):
    json_path = tmp_path / "trace_output.json"
    db_path = tmp_path / "pychronicle.db"

    data, source = load_tracer_data(str(json_path), str(db_path))
    assert source == "demo"
    assert data == DEMO_STEPS


def test_load_tracer_data_returns_a_copy_of_demo_steps(tmp_path):
    """Callers must not be able to mutate the shared DEMO_STEPS constant."""
    json_path = tmp_path / "trace_output.json"
    db_path = tmp_path / "pychronicle.db"

    data, _ = load_tracer_data(str(json_path), str(db_path))
    data["step1"]["event"] = "mutated"

    assert DEMO_STEPS["step1"]["event"] != "mutated"
