"""Regression checks for the database fixes behind the empty-timeline bug.

    python tests/db_regression_test.py

Covers:
  1. A legacy database (pre-session schema, columns added by ALTER TABLE)
     still returns events in the canonical column order.
  2. Orphan events (session_id IS NULL) can be adopted into a session.
  3. Empty session rows are pruned and session counts are recomputed.
  4. Merging one database into another preserves events and session links.
  5. Batch inserts, JSON export and WAL-safe backup behave correctly.
"""

import json
import os
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from database import Database, EVENT_COLUMNS  # noqa: E402

failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def make_legacy_db(path):
    """Build a database with the ORIGINAL pre-session schema."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            function TEXT,
            file TEXT,
            line INTEGER,
            variables TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO events(event, function, file, line, variables) "
        "VALUES (?, ?, ?, ?, ?)",
        [("call", "main", "old.py", 10, "{'x': 1}"),
         ("line", "main", "old.py", 11, "{'x': 2}"),
         ("return", "main", "old.py", 12, "{'x': 2}")]
    )
    conn.commit()
    conn.close()


def test_legacy_migration(tmp):
    print("\n1. legacy schema migration + column order")
    path = os.path.join(tmp, "legacy.db")
    make_legacy_db(path)

    db = Database(path)
    db.create_table()          # triggers _migrate_schema

    db.cursor.execute("PRAGMA table_info(events)")
    physical = [c[1] for c in db.cursor.fetchall()]
    check("physical column order differs from canonical (ALTER TABLE appends)",
          physical != list(EVENT_COLUMNS), f"physical={physical}")

    events = db.get_all_events()
    check("all 3 legacy events readable", len(events) == 3)

    row = Database.row_to_dict(events[0])
    check("event type in canonical position", row["event"] == "call",
          f"got {row['event']!r}")
    check("function in canonical position", row["function"] == "main",
          f"got {row['function']!r}")
    check("line in canonical position", row["line"] == 10, f"got {row['line']!r}")
    check("timestamp column backfilled, not missing",
          row["timestamp"] is not None, f"got {row['timestamp']!r}")
    check("row has exactly 9 canonical fields", len(events[0]) == 9)

    # This is what app.py does — index 8 used to raise IndexError.
    try:
        _ = events[0][8]
        indexable = True
    except IndexError:
        indexable = False
    check("UI can read index 8 (timestamp) without IndexError", indexable)

    db.close()
    return path


def test_orphans_and_sessions(tmp):
    print("\n2. orphan adoption, pruning and count refresh")
    path = os.path.join(tmp, "orphans.db")
    db = Database(path)
    db.create_table()

    # 2 orphan events + 1 empty session + 1 real session with events
    db.insert_event("call", "orphan_fn", "a.py", 1, "{}")
    db.insert_event("line", "orphan_fn", "a.py", 2, "{}")
    empty_session = db.create_session(name="interrupted run")
    real_session = db.create_session(name="real run")
    db.insert_event("call", "real_fn", "b.py", 5, "{}", session_id=real_session)

    check("orphans invisible to session filter before repair",
          db.get_events_by_session(empty_session) == [])

    session_id, adopted = db.adopt_orphan_events()
    check("2 orphans adopted", adopted == 2, f"adopted={adopted}")
    check("adopted events now visible in their session",
          len(db.get_events_by_session(session_id)) == 2)
    db.cursor.execute("SELECT COUNT(*) FROM events WHERE session_id IS NULL")
    check("no orphans left", db.cursor.fetchone()[0] == 0)

    pruned = db.prune_empty_sessions()
    check("empty session pruned", empty_session in pruned, f"pruned={pruned}")
    check("session holding events kept",
          db.get_session_by_id(real_session) is not None)

    db.refresh_session_counts()
    row = Database.row_to_dict(db.get_session_by_id(real_session),
                               Database.SESSION_COLUMNS)
    check("total_events resynced", row["total_events"] == 1,
          f"total_events={row['total_events']}")
    check("status no longer stuck on 'running'", row["status"] == "completed",
          f"status={row['status']}")

    db.close()
    return path


def test_merge(tmp, legacy_path):
    print("\n3. merging databases")
    target = os.path.join(tmp, "merged.db")
    db = Database(target)
    db.create_table()
    db.insert_event("call", "existing", "c.py", 1, "{}")

    result = db.import_from_database(legacy_path)
    check("3 events imported", result["events"] == 3, f"result={result}")
    check("total is existing + imported", db.get_event_count() == 4)

    functions = set(db.get_unique_functions())
    check("imported function present", "main" in functions, f"{functions}")

    same = db.import_from_database(target)
    check("importing a database into itself is a no-op", same["events"] == 0)

    db.close()
    return target


def test_batch_export_backup(tmp):
    print("\n4. batch insert, export and backup")
    path = os.path.join(tmp, "batch.db")
    db = Database(path)
    db.create_table()
    session_id = db.create_session(name="batch run")

    db.begin_batch()
    for i in range(50):
        db.insert_event_with_diff(
            "line", "loop", "d.py", i,
            f"{{'i': {i}}}",
            {"added": {}, "changed": {"i": {"old": str(i - 1), "new": str(i)}},
             "removed": []},
            session_id=session_id
        )
    check("buffered rows not yet committed", db.get_event_count() == 0)
    db.end_batch()
    check("50 rows committed on end_batch", db.get_event_count() == 50)

    db.end_session(session_id)
    row = Database.row_to_dict(db.get_session_by_id(session_id),
                               Database.SESSION_COLUMNS)
    check("end_session recorded the real count", row["total_events"] == 50,
          f"total_events={row['total_events']}")

    export_path = os.path.join(tmp, "export.json")
    db.export_to_json(export_path)
    with open(export_path, encoding="utf-8") as f:
        data = json.load(f)
    check("export has all rows", len(data) == 50)
    check("export keyed by canonical names",
          set(data[0]) == set(EVENT_COLUMNS), f"keys={sorted(data[0])}")
    check("export keeps session link", data[0]["session_id"] == session_id)

    reimported = Database(os.path.join(tmp, "reimport.db"))
    reimported.create_table()
    reimported.import_from_json(export_path)
    check("re-import round-trips", reimported.get_event_count() == 50)
    reimported.close()

    history = db.get_variable_history("i")
    check("variable history returns rows", len(history) == 50)
    check("variable history has a timestamp",
          history[0]["timestamp"] is not None)

    backup_path = os.path.join(tmp, "backup.db")
    db.backup_database(backup_path)
    check("backup file created", os.path.exists(backup_path))
    verify = Database(backup_path)
    verify.create_table()
    check("backup contains every row (WAL-safe)",
          verify.get_event_count() == 50, f"got {verify.get_event_count()}")
    verify.close()

    changes = db.get_variable_changes_in_session(session_id, "i")
    check("diff query finds the changed variable", len(changes) == 50)

    db.close()


def main():
    print("PyChronicle database regression checks")
    with tempfile.TemporaryDirectory() as tmp:
        legacy_path = test_legacy_migration(tmp)
        test_orphans_and_sessions(tmp)
        test_merge(tmp, legacy_path)
        test_batch_export_backup(tmp)

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
