import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1])
)

import json
import sqlite3

from trace_loader import (
    DEMO_STEPS,
    format_vars,
    load_from_json,
    load_from_sqlite,
    load_tracer_data,
)


def test_format_vars_dict():
    data = {
        "x": 5,
        "y": 10,
        "total": 15,
    }

    result = format_vars(data)

    assert "x = 5" in result
    assert "y = 10" in result
    assert "total = 15" in result


def test_load_from_json(tmp_path):
    json_file = tmp_path / "trace.json"

    data = {
        "step1": {
            "code": "x = 5",
            "vars": "x = 5",
            "event": "initialized",
        }
    }

    json_file.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    result = load_from_json(str(json_file))

    assert result == data


def test_load_from_json_missing_file(tmp_path):
    json_file = tmp_path / "missing.json"

    result = load_from_json(str(json_file))

    assert result is None


def test_load_from_sqlite_execution_steps(tmp_path):
    db_file = tmp_path / "test.db"

    conn = sqlite3.connect(db_file)

    conn.execute(
        """
        CREATE TABLE execution_steps (
            id INTEGER PRIMARY KEY,
            step_id TEXT,
            code TEXT,
            vars TEXT,
            event TEXT
        )
        """
    )

    conn.execute(
        """
        INSERT INTO execution_steps
        (step_id, code, vars, event)
        VALUES (?, ?, ?, ?)
        """,
        (
            "step1",
            "x = 5",
            "x = 5",
            "initialized",
        ),
    )

    conn.commit()
    conn.close()

    result = load_from_sqlite(str(db_file))

    assert result is not None
    assert "step1" in result
    assert result["step1"]["code"] == "x = 5"


def test_load_tracer_data_json_priority(tmp_path):
    json_file = tmp_path / "trace.json"

    data = {
        "step1": {
            "code": "x = 5",
            "vars": "x = 5",
            "event": "initialized",
        }
    }

    json_file.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    result, source = load_tracer_data(
        json_path=str(json_file),
        db_path=str(tmp_path / "missing.db"),
    )

    assert result == data
    assert source == "json"


def test_load_tracer_data_demo_fallback(tmp_path):
    result, source = load_tracer_data(
        json_path=str(tmp_path / "missing.json"),
        db_path=str(tmp_path / "missing.db"),
    )

    assert result == DEMO_STEPS
    assert source == "demo"