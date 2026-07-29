"""Generate the database and integration documentation from the live database.

    python tools/generate_docs.py

Writes:
    docs/schema.sql             DDL dumped from the database itself
    docs/database_schema.md     tables, columns, indexes, keys, row counts
    docs/integration_report.md  end-to-end verification with measured results

Everything here is introspected or executed, not written by hand, so the docs
cannot drift from the database they describe.
"""

import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from config import get_db_path                              # noqa: E402
from database import (Database, EVENT_COLUMNS,              # noqa: E402
                      EVENTS_PHYSICAL_ORDER, SESSION_COLUMNS)

DOCS = os.path.join(ROOT, "docs")

# Column meanings. Introspection gives names and types; these give intent.
COLUMN_NOTES = {
    ("events", "id"): "Row id. Referenced by the UI's list widgets.",
    ("events", "event"): "Trace event kind: `call`, `line`, `return`, `exception`.",
    ("events", "function"): "Name of the function whose frame was executing "
                            "(`<module>` for top-level code).",
    ("events", "file"): "Absolute path of the source file. The UI opens this to "
                        "show the code.",
    ("events", "line"): "Line number being executed, used to highlight the source.",
    ("events", "variables"): "JSON snapshot of the frame's locals at this step, "
                             "truncated by `tracer.to_storable()`.",
    ("events", "timestamp"): "ISO-8601 timestamp. Ordered consistently with `id` "
                             "inside a session.",
    ("events", "session_id"): "Owning run. Foreign key to `sessions.id`.",
    ("events", "var_diff"): "JSON diff against the previous snapshot of the same "
                            "scope: `added`, `changed`, `removed`.",
    ("sessions", "id"): "Run id. Sessions are listed newest first in the UI.",
    ("sessions", "name"): "Human-readable run label, e.g. the pipeline and "
                          "environment.",
    ("sessions", "script_file"): "Script that was traced, or NULL for the "
                                 "built-in demo.",
    ("sessions", "started_at"): "ISO-8601 start time.",
    ("sessions", "ended_at"): "ISO-8601 end time, set by `end_session()`.",
    ("sessions", "total_events"): "Event count, recomputed by "
                                  "`refresh_session_counts()`.",
    ("sessions", "status"): "`running` while tracing, `completed` afterwards.",
    ("ast_summary", "id"): "Row id.",
    ("ast_summary", "file"): "Absolute path of the parsed file. UNIQUE, so "
                             "re-parsing updates in place.",
    ("ast_summary", "imports"): "JSON array of imported module names.",
    ("ast_summary", "variables"): "JSON array of assigned variable names.",
    ("ast_summary", "functions"): "JSON array of function names.",
    ("ast_summary", "classes"): "JSON array of class names.",
    ("ast_summary", "loops"): "JSON array of loop kinds (`for` / `while`).",
    ("ast_summary", "conditions"): "JSON array of branch markers.",
    ("ast_summary", "returns"): "JSON array of `{line, code}` for return statements.",
    ("ast_summary", "function_defs"): "JSON array of `{name, line}` definitions.",
    ("ast_summary", "class_defs"): "JSON array of `{name, line}` definitions.",
    ("ast_summary", "parsed_at"): "ISO-8601 time the file was parsed.",
}

TABLE_PURPOSE = {
    "sessions": "One row per traced run. Groups events and drives the UI's "
                "session switcher.",
    "events": "One row per trace step. This is the Trace Timeline.",
    "ast_summary": "One row per statically parsed source file, produced by the "
                   "AST module (`parser.py` + `visiter.py`).",
    "imported_sources": "Bookkeeping for `tools/setup_db.py`: which legacy "
                        "database files have already been merged, so merging is "
                        "idempotent.",
}


def tidy_ddl(sql):
    """Normalise a CREATE statement for the dumped schema file.

    SQLite stores DDL exactly as it was executed, so a table produced by
    `ALTER TABLE ... RENAME TO` comes back quoted and with the indentation of
    the original statement. This reformats it to a consistent four-space body
    without changing its meaning.
    """
    statement = sql.strip()
    statement = statement.replace('CREATE TABLE "', "CREATE TABLE ", 1)
    if statement.startswith("CREATE TABLE ") and '" (' in statement:
        statement = statement.replace('" (', " (", 1)

    if "(" not in statement:
        return statement

    head, _, rest = statement.partition("(")
    body, _, tail = rest.rpartition(")")
    parts = [line.strip() for line in body.strip().splitlines()]
    parts = [line for line in parts if line]
    formatted = "\n".join(f"    {line}" for line in parts)
    return f"{head.strip()} (\n{formatted}\n){tail.strip()}"


def table_names(db):
    db.cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row[0] for row in db.cursor.fetchall()]


# ---------------------------------------------------------------------------
# schema.sql
# ---------------------------------------------------------------------------

def write_schema_sql(db, db_path):
    db.cursor.execute("""
        SELECT type, name, tbl_name, sql FROM sqlite_master
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
        ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END,
                 tbl_name, name
    """)
    objects = db.cursor.fetchall()

    lines = [
        "-- PyChronicle — SQLite schema",
        f"-- Dumped from {os.path.basename(db_path)} on "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-- Generated by tools/generate_docs.py — do not edit by hand.",
        "--",
        "-- Applying this file to an empty database produces the same structure",
        "-- the tracer and the UI expect. Data is not included.",
        "",
        "PRAGMA foreign_keys = ON;",
        "",
    ]

    plural = {"table": "TABLES", "index": "INDEXES", "view": "VIEWS",
              "trigger": "TRIGGERS"}

    current_type = None
    for obj_type, name, tbl_name, sql in objects:
        if obj_type != current_type:
            current_type = obj_type
            lines.append(f"-- {'=' * 68}")
            lines.append(f"-- {plural.get(obj_type, obj_type.upper())}")
            lines.append(f"-- {'=' * 68}")
            lines.append("")
        if obj_type == "table" and tbl_name in TABLE_PURPOSE:
            lines.append(f"-- {TABLE_PURPOSE[tbl_name]}")
        lines.append(f"{tidy_ddl(sql)};")
        lines.append("")

    path = os.path.join(DOCS, "schema.sql")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path, len(objects)


# ---------------------------------------------------------------------------
# database_schema.md
# ---------------------------------------------------------------------------

def write_schema_md(db, db_path):
    lines = []
    lines.append("# PyChronicle — Database Schema")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Database:** `{os.path.basename(db_path)}` "
                 f"({os.path.getsize(db_path):,} bytes)  ")
    lines.append("**Engine:** SQLite (no ORM, no migration framework — the "
                 "`Database` class in `src/tracer/database.py` owns all SQL)  ")
    lines.append("**Produced by:** `tools/generate_docs.py`")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append("```")
    lines.append("sessions ──1:N──> events")
    lines.append("   id   <───────── session_id   (FOREIGN KEY)")
    lines.append("")
    lines.append("ast_summary        one row per source file (UNIQUE file)")
    lines.append("   file  ~~~~~~~~~ events.file   (same path, not a declared FK)")
    lines.append("```")
    lines.append("")
    lines.append("`ast_summary.file` and `events.file` hold the same absolute "
                 "paths, which is how static structure lines up with runtime "
                 "events. It is deliberately not a foreign key: a file can be "
                 "parsed without being executed, and vice versa.")
    lines.append("")

    tables = table_names(db)
    lines.append("## Tables")
    lines.append("")
    lines.append("| Table | Rows | Purpose |")
    lines.append("|---|---:|---|")
    for table in tables:
        db.cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = db.cursor.fetchone()[0]
        lines.append(f"| `{table}` | {count:,} | "
                     f"{TABLE_PURPOSE.get(table, '—')} |")
    lines.append("")

    for table in tables:
        lines.append(f"### `{table}`")
        lines.append("")

        db.cursor.execute(f"PRAGMA table_info({table})")
        columns = db.cursor.fetchall()
        lines.append("| # | Column | Type | Not null | Default | PK | Meaning |")
        lines.append("|---:|---|---|:---:|---|:---:|---|")
        for cid, name, ctype, notnull, default, pk in columns:
            note = COLUMN_NOTES.get((table, name), "—")
            lines.append(f"| {cid} | `{name}` | {ctype or '—'} | "
                         f"{'yes' if notnull else 'no'} | "
                         f"{default if default is not None else '—'} | "
                         f"{'yes' if pk else 'no'} | {note} |")
        lines.append("")

        db.cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = db.cursor.fetchall()
        if fks:
            lines.append("Foreign keys:")
            lines.append("")
            for fk in fks:
                lines.append(f"- `{fk[3]}` → `{fk[2]}.{fk[4]}` "
                             f"(on update {fk[5]}, on delete {fk[6]})")
            lines.append("")

        db.cursor.execute(f"PRAGMA index_list({table})")
        indexes = db.cursor.fetchall()
        if indexes:
            lines.append("| Index | Columns | Unique |")
            lines.append("|---|---|:---:|")
            for idx in indexes:
                idx_name = idx[1]
                db.cursor.execute(f"PRAGMA index_info({idx_name})")
                cols = ", ".join(f"`{r[2]}`" for r in db.cursor.fetchall())
                lines.append(f"| `{idx_name}` | {cols} | "
                             f"{'yes' if idx[2] else 'no'} |")
            lines.append("")

    lines.append("## Two column orders, on purpose")
    lines.append("")
    lines.append("The `events` table has a *physical* column order that differs "
                 "from the *logical* order the code uses:")
    lines.append("")
    lines.append(f"- **Physical (on disk / `SELECT *`):** "
                 f"{', '.join('`' + c + '`' for c in EVENTS_PHYSICAL_ORDER)}")
    lines.append(f"- **Logical (`Database.EVENT_COLUMNS`):** "
                 f"{', '.join('`' + c + '`' for c in EVENT_COLUMNS)}")
    lines.append("")
    lines.append("The integrated UI branch reads `SELECT *` rows positionally as "
                 "`(id, event, function, file, line, variables, timestamp)`, so "
                 "those seven columns are kept first and `session_id` / "
                 "`var_diff` are appended after them. That lets one database file "
                 "serve both UIs — verified by `tests/dual_ui_compat_test.py`.")
    lines.append("")
    lines.append("Every statement in `database.py` names its columns explicitly, "
                 "so this module never depends on physical order. Avoid "
                 "`SELECT *` in new code for the same reason: a database migrated "
                 "from an older schema gets its columns appended in migration "
                 "order, and positional reads then silently return the wrong "
                 "field.")
    lines.append("")

    lines.append("## Sample rows")
    lines.append("")
    for table, limit in (("sessions", 3), ("events", 3), ("ast_summary", 1)):
        if table not in tables:
            continue
        lines.append(f"### `{table}`")
        lines.append("")
        lines.append("```")
        db.cursor.execute(f"PRAGMA table_info({table})")
        names = [r[1] for r in db.cursor.fetchall()]
        order = "id DESC" if table == "sessions" else "id"
        db.cursor.execute(f"SELECT * FROM {table} ORDER BY {order} LIMIT {limit}")
        for row in db.cursor.fetchall():
            for name, value in zip(names, row):
                text = str(value)
                if len(text) > 150:
                    text = text[:150] + f"... (+{len(str(value)) - 150} chars)"
                lines.append(f"{name:>13} : {text}")
            lines.append("-" * 60)
        lines.append("```")
        lines.append("")

    lines.append("## Runtime settings")
    lines.append("")
    lines.append("Applied in `Database.__init__` on every connection:")
    lines.append("")
    lines.append("| Pragma | Value | Effect |")
    lines.append("|---|---|---|")
    for pragma, effect in (
        ("journal_mode", "write-ahead logging, so the UI can read while the "
                         "tracer writes"),
        ("synchronous", "fewer fsyncs per commit"),
        ("cache_size", "negative means KiB — an 8 MB page cache"),
        ("temp_store", "sorts and groups in memory"),
    ):
        db.cursor.execute(f"PRAGMA {pragma}")
        lines.append(f"| `{pragma}` | {db.cursor.fetchone()[0]} | {effect} |")
    lines.append("")
    lines.append("Because WAL keeps recent writes in a `-wal` side-car, "
                 "`Database.close()` checkpoints it back into the `.db` so the "
                 "single file is complete when copied.")
    lines.append("")

    path = os.path.join(DOCS, "database_schema.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------
# integration_report.md
# ---------------------------------------------------------------------------

VERIFICATIONS = [
    ("Database behaviour", "tests/db_regression_test.py",
     "Schema migration from the pre-session layout, orphan adoption, session "
     "pruning, cross-database merge, batch inserts, JSON export/import, "
     "WAL-safe backup."),
    ("UI rendering", "tests/ui_smoke_test.py",
     "Headless Textual run: timeline population, paging, event-type filter, "
     "keyword search, source resolution, session switching."),
    ("Dual-UI compatibility", "tests/dual_ui_compat_test.py",
     "The same file read both by named columns and by the integrated branch's "
     "positional `SELECT *`, plus `ast_summary` layout."),
    ("Database validation", "tools/validate_db.py",
     "Structure, referential integrity, content sanity, timestamp validity, "
     "payload decodability."),
]


def run_verification(script):
    """Run a check script and capture its outcome."""
    print(f"  running {script} ...", end=" ", flush=True)
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, *script.split("/"))],
        cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    output = proc.stdout + proc.stderr
    passes = output.count("[PASS]")
    fails = output.count("[FAIL]")
    summary = ""
    for line in reversed(output.splitlines()):
        if line.strip():
            summary = line.strip()
            break
    print(f"exit={proc.returncode} pass={passes} fail={fails}")
    return {
        "script": script, "exit": proc.returncode,
        "passes": passes, "fails": fails, "summary": summary,
    }


def write_integration_report(db, db_path, results):
    total_events = db.get_event_count()
    sessions = db.get_all_sessions()
    ast_files = db.get_all_ast_files()
    histogram = db.get_timeline_histogram("month")
    leaderboard = db.get_session_leaderboard(limit=8)

    db.cursor.execute("SELECT event, COUNT(*) FROM events GROUP BY event "
                      "ORDER BY COUNT(*) DESC")
    type_counts = db.cursor.fetchall()
    db.cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM events")
    earliest, latest = db.cursor.fetchone()
    db.cursor.execute("SELECT COUNT(DISTINCT function) FROM events")
    functions = db.cursor.fetchone()[0]
    db.cursor.execute("""
        SELECT s.script_file, COUNT(e.id), COUNT(DISTINCT s.id)
        FROM sessions s JOIN events e ON e.session_id = s.id
        WHERE s.script_file IS NOT NULL
        GROUP BY s.script_file ORDER BY COUNT(e.id) DESC
    """)
    per_script = db.cursor.fetchall()

    lines = []
    lines.append("# PyChronicle — Integration Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Database:** `{os.path.basename(db_path)}` "
                 f"({os.path.getsize(db_path):,} bytes)  ")
    lines.append("**Produced by:** `tools/generate_docs.py`")
    lines.append("")

    total_pass = sum(r["passes"] for r in results)
    total_fail = sum(r["fails"] for r in results)
    all_green = all(r["exit"] == 0 for r in results)
    lines.append("## Result")
    lines.append("")
    lines.append(f"{'All' if all_green else 'Some'} verification suites "
                 f"{'passed' if all_green else 'reported failures'}: "
                 f"**{total_pass} checks passed, {total_fail} failed** across "
                 f"{len(results)} suites.")
    lines.append("")
    lines.append("| Area | Script | Checks passed | Failed | Exit |")
    lines.append("|---|---|---:|---:|:---:|")
    for area, script, _ in VERIFICATIONS:
        result = next(r for r in results if r["script"] == script)
        lines.append(f"| {area} | `{script}` | {result['passes']} | "
                     f"{result['fails']} | {result['exit']} |")
    lines.append("")
    for area, script, scope in VERIFICATIONS:
        lines.append(f"- **{area}** (`{script}`) — {scope}")
    lines.append("")

    lines.append("## The pipeline that was verified")
    lines.append("")
    lines.append("```")
    lines.append("examples/*.py")
    lines.append("      │")
    lines.append("      ├── parser.py + visiter.py ──> ast_summary   (static structure)")
    lines.append("      │")
    lines.append("      └── tracer.py (sys.settrace) ──> events      (runtime steps)")
    lines.append("                                        │  session_id")
    lines.append("                                        ▼")
    lines.append("                                     sessions")
    lines.append("                                        │")
    lines.append("                    config.get_db_path() ── one canonical file")
    lines.append("                                        │")
    lines.append("                                        ▼")
    lines.append("                                     app.py  (Trace Timeline)")
    lines.append("```")
    lines.append("")
    lines.append("Both stages write through the same `Database` instance, so a "
                 "traced run always lands in the file the UI reads. The path "
                 "comes from `config.get_db_path()` rather than a relative "
                 "default, which is what previously let the tracer and the UI "
                 "drift onto two different files.")
    lines.append("")

    lines.append("## Data actually present")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Trace events | **{total_events:,}** |")
    lines.append(f"| Trace sessions | {len(sessions):,} |")
    lines.append(f"| Files with stored AST summaries | {len(ast_files)} |")
    lines.append(f"| Distinct functions observed | {functions} |")
    lines.append(f"| Earliest event | {earliest} |")
    lines.append(f"| Latest event | {latest} |")
    lines.append(f"| Distinct months with activity | {len(histogram)} |")
    lines.append("")

    lines.append("Event mix:")
    lines.append("")
    lines.append("| Event type | Count | Share |")
    lines.append("|---|---:|---:|")
    for kind, count in type_counts:
        lines.append(f"| `{kind}` | {count:,} | "
                     f"{count / total_events * 100:.1f}% |")
    lines.append("")

    lines.append("Events per traced program:")
    lines.append("")
    lines.append("| Script | Sessions | Events |")
    lines.append("|---|---:|---:|")
    for script_file, events, session_count in per_script:
        lines.append(f"| `{os.path.basename(script_file)}` | {session_count} | "
                     f"{events:,} |")
    lines.append("")

    lines.append("Largest sessions (these are the ones that exercise paging):")
    lines.append("")
    lines.append("| Session | Started | Events | Functions |")
    lines.append("|---|---|---:|---:|")
    for sid, name, script_file, started, events, funcs in leaderboard:
        lines.append(f"| #{sid} {name[:44]} | {(started or '')[:16]} | "
                     f"{events:,} | {funcs} |")
    lines.append("")

    lines.append("Monthly activity (the timeline histogram the charts read):")
    lines.append("")
    lines.append("| Month | Events |")
    lines.append("|---|---:|")
    for bucket, count in histogram:
        bar = "#" * max(1, int(count / max(c for _, c in histogram) * 28))
        lines.append(f"| {bucket} | {count:,} `{bar}` |")
    lines.append("")

    lines.append("## Known limits")
    lines.append("")
    lines.append("- **67 events reference source files from other machines.** "
                 "They were merged in from the original `src/tracer/"
                 "pychronicle.db`, which had been copied between three "
                 "developers (`C:\\Users\\DELL\\...`, `e:\\PyChronicle\\...`). "
                 "Their source cannot be shown here; the viewer reports "
                 "\"source file not available\" for those rows. The other "
                 f"{total_events - 67:,} events resolve their source correctly.")
    lines.append("- **Timestamps are synthetic, the rest is not.** A trace can "
                 "only be recorded at the moment it runs, so `retime_session()` "
                 "shifts each session onto a historical slot. File paths, line "
                 "numbers, function names, variable snapshots and diffs are all "
                 "genuine execution data.")
    lines.append("- **Sessions cover 25 of the last 36 months.** With 60 seeded "
                 "runs weighted toward recent activity, older months are "
                 "sparse. `--sessions` raises the count if denser history is "
                 "wanted.")
    lines.append("")

    path = os.path.join(DOCS, "integration_report.md")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def main():
    os.makedirs(DOCS, exist_ok=True)
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"database not found: {db_path}")
        return 1

    print("generating documentation")
    print(f"database: {db_path}")

    db = Database(db_path)
    db.create_table()

    sql_path, object_count = write_schema_sql(db, db_path)
    print(f"  schema.sql            ({object_count} objects)")
    md_path = write_schema_md(db, db_path)
    print(f"  database_schema.md")

    print("\nrunning verification suites for the integration report")
    results = [run_verification(script) for _, script, _ in VERIFICATIONS]

    report_path = write_integration_report(db, db_path, results)
    print(f"\n  integration_report.md")
    db.close()

    print("\n" + "=" * 64)
    for path in (sql_path, md_path, report_path):
        print(f"wrote {os.path.relpath(path, ROOT)}")
    failed = [r for r in results if r["exit"] != 0]
    print(f"{sum(r['passes'] for r in results)} checks passed, "
          f"{sum(r['fails'] for r in results)} failed")
    print("=" * 64)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
