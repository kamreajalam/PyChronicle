"""Build / repair the PyChronicle database so the UI has data to show.

Run this once and the Trace Timeline will have events:

    python tools/setup_db.py

What it does, in order:
  1. Creates the canonical database (<project_root>/pychronicle.db) with the
     full schema and indexes.
  2. Imports any events found in the older database locations (idempotent -
     each source file is imported at most once, tracked in imported_sources).
  3. Attaches legacy events that have no session_id to a recovered session,
     so session-filtered views can see them.
  4. Recomputes total_events / status for every session.
  5. Runs live trace sessions (built-in demo + examples/sample_program.py)
     unless --no-trace is passed.
  6. Prints a verification report of exactly what the UI will read.

Options:
    --no-trace      skip generating new trace sessions
    --force-trace   add new trace sessions even if the database already has some
    --reset         delete the canonical database first (destructive)
"""

import os
import random
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACER_DIR = os.path.join(ROOT, "src", "tracer")
sys.path.insert(0, TRACER_DIR)

from config import get_db_path, legacy_db_paths  # noqa: E402
from database import Database  # noqa: E402

TRACER = os.path.join(TRACER_DIR, "tracer.py")
SAMPLE = os.path.join(ROOT, "examples", "sample_program.py")


def _ensure_import_ledger(db):
    """Track which source databases were already merged in."""
    db.cursor.execute("""
        CREATE TABLE IF NOT EXISTS imported_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT UNIQUE,
            events INTEGER,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.conn.commit()


def _already_imported(db, path):
    db.cursor.execute(
        "SELECT 1 FROM imported_sources WHERE source_path = ?",
        (os.path.abspath(path),)
    )
    return db.cursor.fetchone() is not None


def merge_legacy_databases(db):
    _ensure_import_ledger(db)
    total = 0
    for legacy in legacy_db_paths():
        if not os.path.exists(legacy):
            continue
        if os.path.abspath(legacy) == os.path.abspath(db.db_name):
            continue
        if _already_imported(db, legacy):
            print(f"  already merged: {legacy}")
            continue

        result = db.import_from_database(legacy)
        db.cursor.execute(
            "INSERT INTO imported_sources (source_path, events) VALUES (?, ?)",
            (os.path.abspath(legacy), result["events"])
        )
        db.conn.commit()
        total += result["events"]
        print(f"  merged {result['events']} events / "
              f"{result['sessions']} sessions from {legacy}")
    if not total:
        print("  no new legacy events to merge")
    return total


def has_populated_sessions(db_path):
    """True if the database already contains at least one session with events."""
    db = Database(db_path)
    db.create_table()
    db.cursor.execute(
        "SELECT COUNT(*) FROM sessions s WHERE EXISTS "
        "(SELECT 1 FROM events e WHERE e.session_id = s.id)"
    )
    populated = db.cursor.fetchone()[0]
    db.close()
    return populated > 0


def run_trace(script=None, label=""):
    """Run tracer.py in a subprocess so it writes a real session."""
    cmd = [sys.executable, TRACER]
    if script:
        cmd.append(script)
    print(f"  tracing {label or 'built-in demo'} ...", end=" ", flush=True)
    proc = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"}
    )
    if proc.returncode != 0:
        print("FAILED")
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        return False
    print("ok")
    return True


def verify(db_path):
    """Report exactly what app.py will load."""
    db = Database(db_path)
    db.create_table()

    # Compact first, so the size reported below is the size that gets handed
    # over. Repairs and table rebuilds leave free pages behind.
    before, after = db.vacuum()

    sessions = db.get_all_sessions()
    total = db.get_event_count()

    print("\n" + "=" * 62)
    print("VERIFICATION — what the UI will read")
    print("=" * 62)
    print(f"database        : {db_path}")
    print(f"file size       : {os.path.getsize(db_path)} bytes")
    print(f"total events    : {total}")
    print(f"total sessions  : {len(sessions)}")
    print(f"event columns   : {list(Database.EVENT_COLUMNS)}")

    db.cursor.execute("SELECT COUNT(*) FROM events WHERE session_id IS NULL")
    orphans = db.cursor.fetchone()[0]
    print(f"orphan events   : {orphans}")

    print("\nSessions (newest first — this is the N/P order in the UI):")
    for s in sessions:
        row = Database.row_to_dict(s, Database.SESSION_COLUMNS)
        loaded = len(db.get_events_by_session(row["id"]))
        print(f"  #{row['id']:<3} {row['name'][:34]:<34} "
              f"events={loaded:<5} status={row['status']}")

    # The exact data the timeline renders for the default (newest) session.
    if sessions:
        first = db.get_events_by_session(sessions[0][0]) or db.get_all_events()
        print(f"\nDefault timeline rows: {len(first)}")
        for e in first[:5]:
            row = Database.row_to_dict(e)
            print(f"  [{row['event']}] {row['function']}() line {row['line']} "
                  f"@ {row['timestamp']}")
        changes = sum(1 for e in first
                      if e[7] and not Database.diff_is_empty(e[7]))
        print(f"  events with variable changes: {changes}")

    if before != after:
        print(f"\nvacuum: {before:,} -> {after:,} bytes "
              f"({(before - after) / max(1, before) * 100:.0f}% reclaimed)")

    # Make the single .db file self-contained so it can be copied or handed over.
    db.checkpoint()
    db.close()

    wal = db_path + "-wal"
    pending_wal = os.path.exists(wal) and os.path.getsize(wal) > 0
    print("\nFiles to hand over:")
    print(f"  {os.path.relpath(db_path, ROOT)}"
          f"{'' if not pending_wal else '  (see WAL note below)'}")
    if pending_wal:
        print(f"  {os.path.relpath(wal, ROOT)}   "
              "(WAL still holds data — copy it alongside the .db)")
    else:
        print("  nothing else — the WAL was checkpointed into the .db, and the")
        print("  -wal / -shm side-cars are recreated automatically on next open.")

    ok = total > 0 and len(sessions) > 0
    print("\nRESULT:", "PASS — Trace Timeline will show events"
          if ok else "FAIL — database is still empty")
    print("=" * 62)
    return ok


def main():
    args = set(sys.argv[1:])
    db_path = get_db_path()

    if "--reset" in args and os.path.exists(db_path):
        for suffix in ("", "-wal", "-shm"):
            p = db_path + suffix
            if os.path.exists(p):
                os.remove(p)
        print(f"removed {db_path}")

    print(f"canonical database: {db_path}")

    print("\n[1/4] creating schema")
    db = Database(db_path)
    db.create_table()
    print("  tables + indexes ready")

    print("\n[2/4] merging legacy databases")
    merge_legacy_databases(db)

    print("\n[3/4] repairing sessions")
    session_id, adopted = db.adopt_orphan_events(
        session_name="Recovered legacy events (no session_id)"
    )
    if adopted:
        print(f"  attached {adopted} orphan events to session #{session_id}")
    else:
        print("  no orphan events")
    pruned = db.prune_empty_sessions()
    if pruned:
        print(f"  removed {len(pruned)} empty session rows: {pruned}")

    # A table migrated from the pre-session schema has a session_id column but
    # no FOREIGN KEY, because SQLite cannot add one with ALTER TABLE.
    copied = db.rebuild_events_with_constraints()
    if copied:
        print(f"  rebuilt events table with its foreign key ({copied:,} rows copied)")
    else:
        print("  foreign key already present")

    converted, unresolved = db.normalise_legacy_variables()
    if converted or unresolved:
        print(f"  normalised {converted} legacy variable snapshots to JSON "
              f"({unresolved} still undecodable)")
    else:
        print("  variable snapshots already uniform")

    # Legacy bulk inserts gave every row in a batch the same timestamp, which
    # makes those events indistinguishable in time. Spread them out.
    duplicated = db.find_sessions_with_duplicate_timestamps()
    if duplicated:
        rng = random.Random(4242)
        for sid, groups in duplicated:
            row = Database.row_to_dict(db.get_session_by_id(sid),
                                       Database.SESSION_COLUMNS)
            start = row["started_at"] or row["ended_at"]
            try:
                start_dt = datetime.fromisoformat(start)
            except (TypeError, ValueError):
                start_dt = datetime.now()
            count = db.count_events_in_session(sid)
            db.retime_session(sid, start_dt,
                              duration_seconds=max(0.4, count * 0.004), rng=rng)
        print(f"  retimed {len(duplicated)} session(s) that had "
              f"colliding timestamps")
    else:
        print("  no colliding timestamps")

    print(f"  refreshed counts for {db.refresh_session_counts()} sessions")
    db.close()

    print("\n[4/4] generating trace sessions")
    if "--no-trace" in args:
        print("  skipped (--no-trace)")
    elif has_populated_sessions(db_path) and "--force-trace" not in args:
        # Keeps repeated runs idempotent instead of piling up duplicate
        # demo sessions every time someone runs the setup.
        print("  skipped — database already has populated sessions "
              "(use --force-trace to add more)")
    else:
        run_trace(None, "built-in demo")
        if os.path.exists(SAMPLE):
            run_trace(SAMPLE, os.path.relpath(SAMPLE, ROOT))
        db = Database(db_path)
        db.create_table()
        db.refresh_session_counts()
        db.close()

    return 0 if verify(db_path) else 1


if __name__ == "__main__":
    sys.exit(main())
