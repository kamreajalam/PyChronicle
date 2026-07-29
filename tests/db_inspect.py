"""Print what is currently stored in the PyChronicle database.

    python tests/db_inspect.py                 # summary + newest sessions
    python tests/db_inspect.py --sessions 25   # show more sessions
    python tests/db_inspect.py --all           # show every session
    python tests/db_inspect.py --db other.db   # inspect a different file
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from config import get_db_path, legacy_db_paths  # noqa: E402
from database import Database  # noqa: E402


def inspect(path, session_limit):
    print("=" * 72)
    print(path)
    if not os.path.exists(path):
        print("  MISSING — run: python tools/seed_database.py")
        return
    print(f"  file size : {os.path.getsize(path):,} bytes")

    db = Database(path)
    db.create_table()

    events = db.get_event_count()
    sessions = db.get_all_sessions()
    ast_files = db.get_all_ast_files()

    print(f"  events    : {events:,}")
    print(f"  sessions  : {len(sessions):,}")
    print(f"  AST files : {len(ast_files)}")

    db.cursor.execute("SELECT COUNT(*) FROM events WHERE session_id IS NULL")
    print(f"  orphans   : {db.cursor.fetchone()[0]}")

    db.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
    earliest, latest = db.cursor.fetchone()
    print(f"  history   : {earliest} .. {latest}")

    print("\n  event types")
    db.cursor.execute("SELECT event, COUNT(*) FROM events GROUP BY event "
                      "ORDER BY COUNT(*) DESC")
    for kind, count in db.cursor.fetchall():
        share = count / events * 100 if events else 0
        print(f"    {kind:<10} {count:>9,}  {share:5.1f}%")

    print("\n  events per traced script")
    db.cursor.execute("""
        SELECT s.script_file, COUNT(DISTINCT s.id), COUNT(e.id)
        FROM sessions s JOIN events e ON e.session_id = s.id
        GROUP BY s.script_file ORDER BY COUNT(e.id) DESC
    """)
    for script_file, session_count, event_count in db.cursor.fetchall():
        label = os.path.basename(script_file) if script_file else "(built-in demo)"
        print(f"    {label:<28} {session_count:>4} sessions  {event_count:>8,} events")

    print("\n  monthly activity")
    histogram = db.get_timeline_histogram("month")
    peak = max((c for _, c in histogram), default=1)
    for bucket, count in histogram:
        bar = "#" * max(1, int(count / peak * 40))
        print(f"    {bucket}  {count:>7,}  {bar}")

    shown = sessions if session_limit is None else sessions[:session_limit]
    print(f"\n  sessions (newest first — the N/P order in the UI), "
          f"showing {len(shown)} of {len(sessions)}")
    for row in shown:
        session = Database.row_to_dict(row, Database.SESSION_COLUMNS)
        started = (session["started_at"] or "")[:16].replace("T", " ")
        print(f"    #{session['id']:<4} {started}  "
              f"{session['total_events']:>6,} events  "
              f"{session['status']:<10} {session['name'][:44]}")

    print("\n  largest sessions")
    for sid, name, script_file, started, count, funcs in \
            db.get_session_leaderboard(limit=5):
        print(f"    #{sid:<4} {count:>6,} events  {funcs:>3} functions  "
              f"{name[:46]}")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Inspect the PyChronicle database.")
    parser.add_argument("--db", default=None)
    parser.add_argument("--sessions", type=int, default=10,
                        help="how many sessions to list (default 10)")
    parser.add_argument("--all", action="store_true",
                        help="list every session")
    args = parser.parse_args()

    limit = None if args.all else args.sessions
    inspect(args.db or get_db_path(), limit)

    if not args.db:
        for legacy in legacy_db_paths():
            if os.path.exists(legacy):
                print("\nlegacy file still on disk (data already merged):")
                inspect(legacy, 3)


if __name__ == "__main__":
    main()
