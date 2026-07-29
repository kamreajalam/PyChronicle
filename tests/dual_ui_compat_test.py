"""Verify one database file serves both PyChronicle UI branches.

This checkout's UI reads events through named columns. The integrated branch
(PyChronicle-main, the AST variant) reads `SELECT *` rows positionally as

    (id, event, function, file, line, variables, timestamp)

and decodes `variables` with json.loads(). It also expects an `ast_summary`
table and calls create_ast_table() / get_all_ast_files().

This test reproduces both access patterns against the real database, so the
compatibility claim is checked rather than assumed.

    python tests/dual_ui_compat_test.py
"""

import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from config import get_db_path          # noqa: E402
from database import Database, EVENTS_PHYSICAL_ORDER  # noqa: E402

# Positional layout the integrated branch's app.py assumes.
LEGACY_POSITIONS = {
    "id": 0, "event": 1, "function": 2, "file": 3,
    "line": 4, "variables": 5, "timestamp": 6,
}

VALID_EVENT_TYPES = {"call", "line", "return", "exception", "opcode"}

failures = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    db_path = get_db_path()
    print("dual-UI compatibility check")
    print(f"database: {db_path}\n")

    print("1. physical layout")
    db = Database(db_path)
    db.create_table()
    physical = db.events_physical_columns()
    print(f"  on-disk order: {physical}")
    check("physical column order matches the declared layout",
          physical == EVENTS_PHYSICAL_ORDER)
    check("events table needs no further rebuild", not db.events_needs_rebuild())

    print("\n2. this checkout's access pattern (named columns)")
    sessions = db.get_all_sessions()
    events = db.get_events_by_session(sessions[0][0], limit=5)
    row = Database.row_to_dict(events[0])
    print(f"  sample: [{row['event']}] {row['function']}() line {row['line']}")
    check("named-column read returns a valid event type",
          row["event"] in VALID_EVENT_TYPES, row["event"])
    check("named-column read returns an integer line",
          isinstance(row["line"], int), repr(row["line"]))
    check("named-column read exposes session_id",
          row["session_id"] == sessions[0][0])
    db.close()

    print("\n3. integrated branch access pattern (SELECT * positional)")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events LIMIT 200")
    legacy_rows = cursor.fetchall()

    sample = legacy_rows[0]
    event_type = sample[LEGACY_POSITIONS["event"]]
    function = sample[LEGACY_POSITIONS["function"]]
    file_name = sample[LEGACY_POSITIONS["file"]]
    line = sample[LEGACY_POSITIONS["line"]]
    variables = sample[LEGACY_POSITIONS["variables"]]
    timestamp = sample[LEGACY_POSITIONS["timestamp"]]
    print(f"  label it would render: [{event_type}] {function}() line {line}")
    print(f"  timestamp it would show: {timestamp}")

    check("position 1 is the event type, not session_id",
          event_type in VALID_EVENT_TYPES, repr(event_type))
    check("position 2 is a function name", isinstance(function, str)
          and not function.isdigit(), repr(function)[:40])
    check("position 3 is a file path", isinstance(file_name, str)
          and file_name.endswith(".py"), str(file_name)[-40:])
    check("position 4 is an integer line", isinstance(line, int), repr(line))
    check("position 6 is an ISO timestamp",
          isinstance(timestamp, str) and timestamp[:4].isdigit()
          and "T" in timestamp, repr(timestamp))

    # The integrated UI decodes variables with json.loads().
    decoded = 0
    failed = 0
    for legacy_row in legacy_rows:
        raw = legacy_row[LEGACY_POSITIONS["variables"]]
        if not raw or raw == "{}":
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                decoded += 1
            else:
                failed += 1
        except (json.JSONDecodeError, TypeError):
            failed += 1
    print(f"  json.loads on variables: {decoded} ok, {failed} failed")
    check("variables decode with json.loads (as the integrated UI does)",
          failed == 0 and decoded > 0, f"{decoded} decoded, {failed} failed")

    # Its source viewer opens the traced file from disk. Events recorded on
    # this machine must resolve; the handful merged in from a teammate's old
    # database reference that machine's paths and cannot, which the UI handles
    # by showing "source not available".
    cursor.execute("""
        SELECT DISTINCT file FROM events
        WHERE file IS NOT NULL
    """)
    all_files = [r[0] for r in cursor.fetchall()]
    resolvable = [f for f in all_files if os.path.exists(f)]
    foreign = [f for f in all_files if not os.path.exists(f)]

    cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE file LIKE ? AND file NOT LIKE ?
    """, (f"{ROOT}%", "%DELL%"))
    local_events = cursor.fetchone()[0]

    print(f"  distinct traced files: {len(all_files)} "
          f"({len(resolvable)} resolvable, {len(foreign)} from other machines)")
    for path in foreign:
        print(f"    unresolvable: {path}")

    check("files traced from this project all resolve",
          all(os.path.exists(f) for f in all_files
              if f.startswith(ROOT)),
          f"{local_events:,} local events")
    check("unresolvable paths are confined to imported legacy rows",
          all(not f.startswith(ROOT) for f in foreign),
          f"{len(foreign)} foreign path(s)")

    # It also reads the AST table.
    cursor.execute("SELECT COUNT(*) FROM ast_summary")
    ast_count = cursor.fetchone()[0]
    cursor.execute("SELECT file FROM ast_summary")
    ast_files = [r[0] for r in cursor.fetchall()]
    print(f"  ast_summary rows: {ast_count}")
    check("ast_summary is populated for the AST counter",
          ast_count > 0, f"{ast_count} file(s)")
    check("AST rows point at files that exist",
          all(os.path.exists(f) for f in ast_files))

    cursor.execute("PRAGMA table_info(ast_summary)")
    ast_columns = [r[1] for r in cursor.fetchall()]
    expected_ast = ["id", "file", "imports", "variables", "functions",
                    "classes", "loops", "conditions", "returns",
                    "function_defs", "class_defs", "parsed_at"]
    check("ast_summary layout matches the integrated branch",
          ast_columns == expected_ast, f"{ast_columns}")

    conn.close()

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {failures}")
        return 1
    print("BOTH UI ACCESS PATTERNS READ THIS DATABASE CORRECTLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
