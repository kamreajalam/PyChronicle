"""Validate the PyChronicle database and write docs/validation_report.md.

    python tools/validate_db.py
    python tools/validate_db.py --db path/to/other.db

Checks structure (tables, columns, indexes, constraints), referential
integrity (orphan rows, foreign keys), and content sanity (nulls, duplicates,
timestamp validity and ordering, decodable variable snapshots and diffs,
session bookkeeping).

Exit status is 0 only when there are no failures.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from config import get_db_path          # noqa: E402
from database import Database, EVENT_COLUMNS, SESSION_COLUMNS  # noqa: E402

REPORT_PATH = os.path.join(ROOT, "docs", "validation_report.md")

EXPECTED_EVENT_TYPES = {"call", "line", "return", "exception", "opcode"}

# The review asks the timeline to show 10,000+ events. Lower this when
# validating a small development database: PYCHRONICLE_MIN_EVENTS=500
MIN_EVENTS = int(os.environ.get("PYCHRONICLE_MIN_EVENTS", "10000"))

# A three-year history should touch a good number of months. Below this the
# check warns rather than fails, since it describes data shape, not integrity.
MIN_MONTHS = int(os.environ.get("PYCHRONICLE_MIN_MONTHS", "12"))

EXPECTED_INDEXES = {
    "idx_events_event",
    "idx_events_function",
    "idx_events_file",
    "idx_events_line",
    "idx_events_session",
    "idx_events_session_id",
    "idx_events_timestamp",
    "idx_sessions_started",
}


class Results:
    """Collects check outcomes for both console output and the report."""

    def __init__(self):
        self.rows = []          # (section, name, status, detail)

    def add(self, section, name, ok, detail="", warn_only=False):
        status = "PASS" if ok else ("WARN" if warn_only else "FAIL")
        self.rows.append((section, name, status, str(detail)))
        marker = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[status]
        print(f"  [{marker}] {name}" + (f" — {detail}" if detail else ""))
        return ok

    @property
    def failures(self):
        return [r for r in self.rows if r[2] == "FAIL"]

    @property
    def warnings(self):
        return [r for r in self.rows if r[2] == "WARN"]

    @property
    def passes(self):
        return [r for r in self.rows if r[2] == "PASS"]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def check_structure(db, results):
    section = "Structure"
    print("\n1. structure")

    db.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = {row[0] for row in db.cursor.fetchall()}
    for expected in ("sessions", "events", "ast_summary"):
        results.add(section, f"table `{expected}` exists", expected in tables)

    db.cursor.execute("PRAGMA table_info(events)")
    event_cols = {row[1]: row[2] for row in db.cursor.fetchall()}
    missing = [c for c in EVENT_COLUMNS if c not in event_cols]
    results.add(section, "events has every canonical column",
                not missing, f"missing={missing}" if missing else
                f"{len(event_cols)} columns")

    # Datatypes: the UI and reports rely on line being numeric and the rest text.
    results.add(section, "events.id is INTEGER PRIMARY KEY",
                event_cols.get("id") == "INTEGER")
    results.add(section, "events.line is INTEGER", event_cols.get("line") == "INTEGER")
    results.add(section, "events.session_id is INTEGER",
                event_cols.get("session_id") == "INTEGER")
    text_columns = ["event", "function", "file", "variables", "var_diff", "timestamp"]
    wrong = [c for c in text_columns if event_cols.get(c) != "TEXT"]
    results.add(section, "events text columns are TEXT", not wrong, f"wrong={wrong}")

    db.cursor.execute("PRAGMA table_info(sessions)")
    session_cols = {row[1]: row[2] for row in db.cursor.fetchall()}
    missing = [c for c in SESSION_COLUMNS if c not in session_cols]
    results.add(section, "sessions has every expected column",
                not missing, f"missing={missing}" if missing else
                f"{len(session_cols)} columns")

    db.cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in db.cursor.fetchall()}
    missing_idx = sorted(EXPECTED_INDEXES - indexes)
    results.add(section, "all expected indexes present",
                not missing_idx, f"missing={missing_idx}" if missing_idx
                else f"{len(EXPECTED_INDEXES)} indexes")

    # Constraints: the events -> sessions foreign key and the ast_summary
    # uniqueness that stops one file being parsed into two rows.
    db.cursor.execute("PRAGMA foreign_key_list(events)")
    fks = db.cursor.fetchall()
    results.add(section, "events declares its sessions foreign key",
                any(fk[2] == "sessions" for fk in fks), f"{len(fks)} foreign key(s)")

    db.cursor.execute("PRAGMA index_list(ast_summary)")
    unique_indexes = [row for row in db.cursor.fetchall() if row[2] == 1]
    results.add(section, "ast_summary.file has a UNIQUE constraint",
                len(unique_indexes) > 0, f"{len(unique_indexes)} unique index(es)")

    return tables


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------

def check_integrity(db, results):
    section = "Integrity"
    print("\n2. integrity")

    db.cursor.execute("PRAGMA integrity_check")
    integrity = db.cursor.fetchone()[0]
    results.add(section, "PRAGMA integrity_check", integrity == "ok", integrity)

    db.cursor.execute("PRAGMA foreign_key_check")
    violations = db.cursor.fetchall()
    results.add(section, "PRAGMA foreign_key_check finds no violations",
                not violations, f"{len(violations)} violation(s)")

    db.cursor.execute("""
        SELECT COUNT(*) FROM events
        WHERE session_id IS NOT NULL
          AND session_id NOT IN (SELECT id FROM sessions)
    """)
    orphans = db.cursor.fetchone()[0]
    results.add(section, "no events point at a missing session", orphans == 0,
                f"{orphans} orphan(s)")

    db.cursor.execute("SELECT COUNT(*) FROM events WHERE session_id IS NULL")
    unassigned = db.cursor.fetchone()[0]
    results.add(section, "no events without a session", unassigned == 0,
                f"{unassigned} unassigned")

    db.cursor.execute("""
        SELECT COUNT(*) FROM sessions s
        WHERE NOT EXISTS (SELECT 1 FROM events e WHERE e.session_id = s.id)
    """)
    empty_sessions = db.cursor.fetchone()[0]
    results.add(section, "no empty sessions", empty_sessions == 0,
                f"{empty_sessions} empty")


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def check_content(db, results):
    section = "Content"
    print("\n3. content")

    total_events = db.get_event_count()
    total_sessions = len(db.get_all_sessions())
    results.add(section, "events table is populated", total_events > 0,
                f"{total_events:,} rows")
    results.add(section, "sessions table is populated", total_sessions > 0,
                f"{total_sessions:,} rows")
    results.add(section, f"event volume meets the {MIN_EVENTS:,} target",
                total_events >= MIN_EVENTS,
                f"{total_events:,} events "
                f"(override with PYCHRONICLE_MIN_EVENTS)")

    ast_files = db.get_all_ast_files()
    results.add(section, "ast_summary table is populated", len(ast_files) > 0,
                f"{len(ast_files)} file(s)")

    # NULLs in fields the UI reads positionally.
    for column in ("event", "function", "file", "line", "timestamp"):
        db.cursor.execute(f"SELECT COUNT(*) FROM events WHERE {column} IS NULL")
        nulls = db.cursor.fetchone()[0]
        results.add(section, f"events.{column} has no NULLs", nulls == 0,
                    f"{nulls} null(s)")

    db.cursor.execute("SELECT COUNT(*) FROM events WHERE line < 0")
    results.add(section, "no negative line numbers", db.cursor.fetchone()[0] == 0)

    db.cursor.execute("SELECT DISTINCT event FROM events")
    kinds = {row[0] for row in db.cursor.fetchall()}
    unexpected = kinds - EXPECTED_EVENT_TYPES
    results.add(section, "event types are all recognised", not unexpected,
                f"types={sorted(kinds)}")

    # Duplicate detection. Repeated (function, line) pairs are legitimate — a
    # loop body genuinely executes the same line many times — so the check is
    # for rows that are identical including their timestamp, which would mean
    # the same event was written twice.
    db.cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT session_id, event, function, line, timestamp, COUNT(*) AS n
            FROM events
            GROUP BY session_id, event, function, line, timestamp
            HAVING n > 1
        )
    """)
    dupes = db.cursor.fetchone()[0]
    results.add(section, "no double-inserted events", dupes == 0,
                f"{dupes} duplicate group(s)")

    db.cursor.execute("SELECT COUNT(*), COUNT(DISTINCT file) FROM ast_summary")
    ast_rows, ast_distinct = db.cursor.fetchone()
    results.add(section, "ast_summary holds one row per file",
                ast_rows == ast_distinct, f"{ast_rows} rows / {ast_distinct} files")


def check_timestamps(db, results):
    section = "Timestamps"
    print("\n4. timestamps")

    db.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
    earliest, latest = db.cursor.fetchone()

    invalid = 0
    db.cursor.execute("SELECT timestamp FROM events")
    for (value,) in db.cursor.fetchall():
        try:
            datetime.fromisoformat(value)
        except (TypeError, ValueError):
            invalid += 1
    results.add(section, "every timestamp parses as ISO-8601", invalid == 0,
                f"{invalid} invalid")

    now = datetime.now()
    try:
        earliest_dt = datetime.fromisoformat(earliest)
        latest_dt = datetime.fromisoformat(latest)
        span_days = (latest_dt - earliest_dt).days
        results.add(section, "no timestamps in the future", latest_dt <= now,
                    f"latest={latest}")
        results.add(section, "history spans at least 2 years", span_days >= 730,
                    f"{span_days} days ({earliest[:10]} .. {latest[:10]})",
                    warn_only=True)
    except (TypeError, ValueError):
        results.add(section, "timestamp range readable", False, "unparseable range")

    # Within a session, id order must equal time order, otherwise the timeline
    # would present steps out of sequence.
    db.cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT id, session_id, timestamp,
                   LAG(timestamp) OVER (PARTITION BY session_id ORDER BY id) AS prev
            FROM events
        ) WHERE prev IS NOT NULL AND timestamp < prev
    """)
    out_of_order = db.cursor.fetchone()[0]
    results.add(section, "events are chronological within each session",
                out_of_order == 0, f"{out_of_order} out of order")

    db.cursor.execute("""
        SELECT COUNT(*) FROM sessions
        WHERE ended_at IS NOT NULL AND started_at IS NOT NULL
          AND ended_at < started_at
    """)
    results.add(section, "no session ends before it starts",
                db.cursor.fetchone()[0] == 0)

    histogram = db.get_timeline_histogram("month")
    results.add(section, f"events spread across at least {MIN_MONTHS} months",
                len(histogram) >= MIN_MONTHS,
                f"{len(histogram)} distinct months", warn_only=True)


def check_payloads(db, results):
    section = "Payloads"
    print("\n5. payloads")

    undecodable_vars = 0
    bad_diffs = 0
    empty_vars = 0
    sizes = []

    db.cursor.execute("SELECT variables, var_diff FROM events")
    for variables, var_diff in db.cursor.fetchall():
        sizes.append(len(variables or "") + len(var_diff or ""))
        if not variables or variables == "{}":
            empty_vars += 1
        elif not Database.parse_variables(variables):
            undecodable_vars += 1
        if var_diff:
            try:
                parsed = json.loads(var_diff)
                if not isinstance(parsed, dict) or "added" not in parsed:
                    bad_diffs += 1
            except (json.JSONDecodeError, TypeError):
                bad_diffs += 1

    results.add(section, "variable snapshots all decode",
                undecodable_vars == 0, f"{undecodable_vars} undecodable")
    results.add(section, "variable diffs are well-formed JSON",
                bad_diffs == 0, f"{bad_diffs} malformed")
    results.add(section, "most events carry variables",
                empty_vars < len(sizes) * 0.5,
                f"{empty_vars:,} of {len(sizes):,} have no variables")

    average = sum(sizes) / len(sizes) if sizes else 0
    results.add(section, "payload size per event stays bounded",
                max(sizes or [0]) < 20000,
                f"avg={average:,.0f} B, max={max(sizes or [0]):,} B")

    # Session bookkeeping must agree with the rows that exist.
    mismatched = []
    for row in db.get_all_sessions():
        session = Database.row_to_dict(row, SESSION_COLUMNS)
        actual = db.count_events_in_session(session["id"])
        if actual != session["total_events"]:
            mismatched.append((session["id"], session["total_events"], actual))
    results.add(section, "sessions.total_events matches actual rows",
                not mismatched, f"{len(mismatched)} mismatch(es)")

    db.cursor.execute("SELECT COUNT(*) FROM sessions WHERE status != 'completed'")
    results.add(section, "no sessions left in a non-completed state",
                db.cursor.fetchone()[0] == 0)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def collect_inventory(db, db_path):
    """Facts about the database that belong in the report header."""
    db.cursor.execute("SELECT COUNT(*) FROM events")
    events = db.cursor.fetchone()[0]
    sessions = len(db.get_all_sessions())
    db.cursor.execute("SELECT COUNT(*) FROM ast_summary")
    ast_rows = db.cursor.fetchone()[0]
    db.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
    earliest, latest = db.cursor.fetchone()
    by_type = db.get_session_event_types  # noqa: F841  (kept for clarity)
    db.cursor.execute("SELECT event, COUNT(*) FROM events GROUP BY event "
                      "ORDER BY COUNT(*) DESC")
    type_counts = db.cursor.fetchall()
    db.cursor.execute("SELECT COUNT(DISTINCT function) FROM events")
    functions = db.cursor.fetchone()[0]
    db.cursor.execute("SELECT COUNT(DISTINCT file) FROM events")
    files = db.cursor.fetchone()[0]

    return {
        "path": db_path,
        "size": os.path.getsize(db_path),
        "events": events,
        "sessions": sessions,
        "ast_rows": ast_rows,
        "earliest": earliest,
        "latest": latest,
        "type_counts": type_counts,
        "functions": functions,
        "files": files,
        "months": len(db.get_timeline_histogram("month")),
    }


def write_report(results, inventory):
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    total = len(results.rows)
    passed = len(results.passes)
    failed = len(results.failures)
    warned = len(results.warnings)

    lines = []
    lines.append("# PyChronicle — Database Validation Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Database:** `{os.path.basename(inventory['path'])}` "
                 f"({inventory['size']:,} bytes)  ")
    lines.append("**Produced by:** `tools/validate_db.py`")
    lines.append("")
    lines.append("## Result")
    lines.append("")
    lines.append(f"| Checks | Passed | Warnings | Failed |")
    lines.append(f"|---|---|---|---|")
    lines.append(f"| {total} | {passed} | {warned} | {failed} |")
    lines.append("")
    verdict = ("All checks passed. The database is structurally sound, "
               "referentially consistent and populated."
               if failed == 0 else
               f"{failed} check(s) failed — see the table below.")
    lines.append(verdict)
    lines.append("")

    lines.append("## Inventory")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Trace events | {inventory['events']:,} |")
    lines.append(f"| Trace sessions | {inventory['sessions']:,} |")
    lines.append(f"| AST summaries (files parsed) | {inventory['ast_rows']} |")
    lines.append(f"| Distinct functions observed | {inventory['functions']} |")
    lines.append(f"| Distinct source files traced | {inventory['files']} |")
    lines.append(f"| Earliest event | {inventory['earliest']} |")
    lines.append(f"| Latest event | {inventory['latest']} |")
    lines.append(f"| Distinct months covered | {inventory['months']} |")
    lines.append("")
    lines.append("Event mix:")
    lines.append("")
    lines.append("| Event type | Count |")
    lines.append("|---|---|")
    for kind, count in inventory["type_counts"]:
        lines.append(f"| `{kind}` | {count:,} |")
    lines.append("")

    lines.append("## Checks")
    lines.append("")
    current = None
    for sectionname, name, status, detail in results.rows:
        if sectionname != current:
            current = sectionname
            lines.append(f"### {sectionname}")
            lines.append("")
            lines.append("| Check | Result | Detail |")
            lines.append("|---|---|---|")
        lines.append(f"| {name} | {status} | {detail or '—'} |")
        if sectionname != current:
            lines.append("")
    lines.append("")

    lines.append("## Notes on two checks that look surprising")
    lines.append("")
    lines.append("**Duplicate data.** Repeated `(function, line)` pairs are expected "
                 "in trace data: a loop body genuinely executes the same line many "
                 "times. The duplicate check therefore looks for rows identical "
                 "*including their timestamp*, which would indicate the same event "
                 "was written twice rather than executed twice.")
    lines.append("")
    lines.append("**Events with no variables.** A `call` event on a function with no "
                 "arguments has an empty local scope, so an empty `variables` value "
                 "is correct rather than missing data. The check only fails if most "
                 "rows are empty.")
    lines.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return REPORT_PATH


def main():
    parser = argparse.ArgumentParser(description="Validate the PyChronicle database.")
    parser.add_argument("--db", default=None, help="database path")
    args = parser.parse_args()

    db_path = args.db or get_db_path()
    if not os.path.exists(db_path):
        print(f"database not found: {db_path}")
        return 1

    print("PyChronicle database validation")
    print(f"database: {db_path}")

    db = Database(db_path)
    db.create_table()
    results = Results()

    check_structure(db, results)
    check_integrity(db, results)
    check_content(db, results)
    check_timestamps(db, results)
    check_payloads(db, results)

    inventory = collect_inventory(db, db_path)
    report = write_report(results, inventory)
    db.close()

    print("\n" + "=" * 64)
    print(f"{len(results.passes)} passed, {len(results.warnings)} warnings, "
          f"{len(results.failures)} failed")
    print(f"report written to {os.path.relpath(report, ROOT)}")
    print("=" * 64)

    return 1 if results.failures else 0


if __name__ == "__main__":
    sys.exit(main())
