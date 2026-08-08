import sqlite3
import json
import os
from datetime import datetime, timedelta

try:  # flat import (src/tracer on sys.path) with package fallback
    from config import get_db_path
except ImportError:  # pragma: no cover
    from .config import get_db_path


# Canonical logical column order for the events table.
#
# Never use "SELECT * FROM events": a database created before session support
# gets its session_id / var_diff / timestamp columns appended by ALTER TABLE,
# so "*" returns them in a different order than a freshly created database.
# The UI reads event fields positionally, so "*" silently produced wrong
# values (and IndexError for the timestamp) on migrated databases.
EVENT_COLUMNS = (
    "id", "session_id", "event", "function", "file",
    "line", "variables", "var_diff", "timestamp",
)
_EVENT_COLS_SQL = ", ".join(EVENT_COLUMNS)

SESSION_COLUMNS = (
    "id", "name", "script_file", "started_at",
    "ended_at", "total_events", "status",
)
_SESSION_COLS_SQL = ", ".join(SESSION_COLUMNS)

# Physical (on-disk) column order for the events table.
#
# This is intentionally different from EVENT_COLUMNS. The integrated UI branch
# reads `SELECT *` rows positionally as
#   (id, event, function, file, line, variables, timestamp)
# so those seven columns come first, with session_id and var_diff appended
# after them. That way a single database file works with both UIs.
#
# Code in this module never relies on physical order — every statement names
# its columns — so the two orders can differ safely.
EVENTS_PHYSICAL_ORDER = (
    "id", "event", "function", "file", "line",
    "variables", "timestamp", "session_id", "var_diff",
)

_EVENTS_TABLE_BODY = """id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            function TEXT,
            file TEXT,
            line INTEGER,
            variables TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            session_id INTEGER,
            var_diff TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id)"""


class Database:

    # Exposed so callers can index rows by name instead of magic numbers.
    EVENT_COLUMNS = EVENT_COLUMNS
    SESSION_COLUMNS = SESSION_COLUMNS

    def __init__(self, db_name=None):
        # Default to the shared canonical path so the tracer and the UI can
        # never drift apart based on the current working directory.
        if db_name is None:
            db_name = get_db_path()
        self.db_name = db_name

        parent = os.path.dirname(os.path.abspath(db_name))
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

        # Performance optimizations
        self.cursor.execute("PRAGMA journal_mode=WAL")
        self.cursor.execute("PRAGMA synchronous=NORMAL")
        self.cursor.execute("PRAGMA cache_size=-8000")
        self.cursor.execute("PRAGMA temp_store=MEMORY")
        self.conn.commit()

        # Batch insert buffer
        self._batch_buffer = []
        self._batch_mode = False

    def create_table(self):
        # --- Sessions table ---
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            script_file TEXT,
            started_at TEXT,
            ended_at TEXT,
            total_events INTEGER DEFAULT 0,
            status TEXT DEFAULT 'running'
        )
        """)

        # --- Events table ---
        # The PHYSICAL column order below is deliberate and must not be
        # reshuffled. The integrated UI branch reads rows from `SELECT *`
        # positionally as (id, event, function, file, line, variables,
        # timestamp), so keeping those seven first — and appending session_id
        # and var_diff after them — lets one database file serve both UIs.
        #
        # Nothing in this module depends on physical order: every query names
        # its columns explicitly (see EVENT_COLUMNS / _EVENT_COLS_SQL).
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS events (
            {_EVENTS_TABLE_BODY}
        )
        """)

        # Migrate: add session_id column if missing (for existing DBs)
        self._migrate_schema()

        # Create indexes for commonly queried columns
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_event ON events(event)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_function ON events(function)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_file ON events(file)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_line ON events(line)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)"
        )
        # Composite index for the UI's main access pattern: page through one
        # session's events in id order.
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_session_id "
            "ON events(session_id, id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at)"
        )
        self.conn.commit()

        # The AST table ships with the schema so a single database file works
        # with both the runtime UI and the integrated AST UI.
        self.create_ast_table()

    def _migrate_schema(self):
        """Add new columns to existing databases without losing data."""
        # Check columns in events table
        self.cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in self.cursor.fetchall()]

        if "session_id" not in columns:
            self.cursor.execute("ALTER TABLE events ADD COLUMN session_id INTEGER")

        if "var_diff" not in columns:
            self.cursor.execute("ALTER TABLE events ADD COLUMN var_diff TEXT")

        if "timestamp" not in columns:
            # Older databases predate the timestamp column entirely. SQLite
            # rejects a non-constant default in ALTER TABLE, so add the column
            # and backfill it instead of using CURRENT_TIMESTAMP.
            self.cursor.execute("ALTER TABLE events ADD COLUMN timestamp TEXT")
            self.cursor.execute(
                "UPDATE events SET timestamp = ? WHERE timestamp IS NULL",
                (datetime.now().isoformat(),)
            )

        # Ensure sessions table exists (already handled by CREATE IF NOT EXISTS above)
        self.conn.commit()

    # ===================================================================
    # SESSION MANAGEMENT
    # ===================================================================

    def create_session(self, name=None, script_file=None):
        """Start a new trace session. Returns the session ID."""
        if name is None:
            name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        self.cursor.execute("""
            INSERT INTO sessions (name, script_file, started_at, status)
            VALUES (?, ?, ?, 'running')
        """, (name, script_file, datetime.now().isoformat()))
        self.conn.commit()
        return self.cursor.lastrowid

    def end_session(self, session_id):
        """Mark a session as complete and update its event count."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,)
        )
        count = self.cursor.fetchone()[0]

        self.cursor.execute("""
            UPDATE sessions
            SET ended_at = ?, total_events = ?, status = 'completed'
            WHERE id = ?
        """, (datetime.now().isoformat(), count, session_id))
        self.conn.commit()

    def get_all_sessions(self):
        """Return all sessions, most recently started first.

        Ordering is by start time rather than by id. Ids only track insertion
        order, which stops matching chronological order as soon as sessions are
        recorded in more than one pass (or backdated by retime_session), and the
        UI's session switcher presents this list as newest-first.
        """
        self.cursor.execute(f"""
            SELECT {_SESSION_COLS_SQL} FROM sessions
            ORDER BY COALESCE(started_at, ended_at, '') DESC, id DESC
        """)
        return self.cursor.fetchall()

    def get_session_by_id(self, session_id):
        self.cursor.execute(
            f"SELECT {_SESSION_COLS_SQL} FROM sessions WHERE id = ?", (session_id,)
        )
        return self.cursor.fetchone()

    def get_events_by_session(self, session_id, limit=None, offset=0):
        """Get events belonging to a session, optionally one page at a time.

        The UI pages through large sessions instead of loading every row,
        because mounting tens of thousands of list widgets at once is slow.
        """
        sql = (f"SELECT {_EVENT_COLS_SQL} FROM events "
               "WHERE session_id = ? ORDER BY id")
        params = [session_id]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

    def count_events_in_session(self, session_id):
        """Number of events in a session (without loading them)."""
        self.cursor.execute(
            "SELECT COUNT(*) FROM events WHERE session_id = ?", (session_id,)
        )
        return self.cursor.fetchone()[0]

    def get_session_event_types(self, session_id):
        """Event-type histogram for one session, e.g. {'line': 812, 'call': 96}."""
        self.cursor.execute(
            "SELECT event, COUNT(*) FROM events WHERE session_id = ? "
            "GROUP BY event ORDER BY COUNT(*) DESC", (session_id,)
        )
        return dict(self.cursor.fetchall())

    def get_events_by_session_filtered(self, session_id, event_type=None,
                                       function=None, keyword=None,
                                       limit=None, offset=0):
        """Paged session events with optional type / function / keyword filters.

        Backs the UI's filter controls. Every clause is parameterised.
        """
        sql = (f"SELECT {_EVENT_COLS_SQL} FROM events WHERE session_id = ?")
        params = [session_id]

        if event_type:
            sql += " AND event = ?"
            params.append(event_type)
        if function:
            sql += " AND function = ?"
            params.append(function)
        if keyword:
            sql += " AND (function LIKE ? OR variables LIKE ? OR file LIKE ?)"
            like = f"%{keyword}%"
            params.extend([like, like, like])

        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

    def count_events_by_session_filtered(self, session_id, event_type=None,
                                         function=None, keyword=None):
        """Row count for the same filters — used to compute page counts."""
        sql = "SELECT COUNT(*) FROM events WHERE session_id = ?"
        params = [session_id]

        if event_type:
            sql += " AND event = ?"
            params.append(event_type)
        if function:
            sql += " AND function = ?"
            params.append(function)
        if keyword:
            sql += " AND (function LIKE ? OR variables LIKE ? OR file LIKE ?)"
            like = f"%{keyword}%"
            params.extend([like, like, like])

        self.cursor.execute(sql, params)
        return self.cursor.fetchone()[0]

    def get_functions_in_session(self, session_id):
        """Distinct function names in a session, most frequent first."""
        self.cursor.execute(
            "SELECT function, COUNT(*) FROM events WHERE session_id = ? "
            "GROUP BY function ORDER BY COUNT(*) DESC", (session_id,)
        )
        return self.cursor.fetchall()

    def get_session_summary(self, session_id):
        """Get a summary of a specific session."""
        session = self.get_session_by_id(session_id)
        if not session:
            return None

        self.cursor.execute(
            "SELECT event, COUNT(*) FROM events WHERE session_id = ? GROUP BY event",
            (session_id,)
        )
        by_type = dict(self.cursor.fetchall())

        self.cursor.execute(
            "SELECT DISTINCT function FROM events WHERE session_id = ?",
            (session_id,)
        )
        functions = [row[0] for row in self.cursor.fetchall()]

        return {
            "session_id": session[0],
            "name": session[1],
            "script_file": session[2],
            "started_at": session[3],
            "ended_at": session[4],
            "total_events": session[5],
            "status": session[6],
            "by_type": by_type,
            "functions": functions
        }

    def delete_session(self, session_id):
        """Delete a session and all its events."""
        self.cursor.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
        self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    # ===================================================================
    # AST STATIC-ANALYSIS STORAGE
    # ===================================================================
    # Stores the output of the AST module (parser.py + visiter.py) so the UI
    # can show static structure (functions, classes, imports) alongside the
    # runtime trace events. One row per source file, keyed by absolute path;
    # re-parsing a file updates its row instead of duplicating it.
    #
    # Schema is kept byte-identical to the integrated branch so a single
    # database file works with both UIs.

    def create_ast_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS ast_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT UNIQUE,
            imports TEXT,
            variables TEXT,
            functions TEXT,
            classes TEXT,
            loops TEXT,
            conditions TEXT,
            returns TEXT,
            function_defs TEXT,
            class_defs TEXT,
            parsed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def insert_ast_summary(self, file_path, summary):
        """Store (or update) the AST visitor's summary for a source file."""
        self.create_ast_table()
        self.cursor.execute("""
        INSERT INTO ast_summary(
            file, imports, variables, functions, classes,
            loops, conditions, returns, function_defs, class_defs, parsed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(file) DO UPDATE SET
            imports=excluded.imports,
            variables=excluded.variables,
            functions=excluded.functions,
            classes=excluded.classes,
            loops=excluded.loops,
            conditions=excluded.conditions,
            returns=excluded.returns,
            function_defs=excluded.function_defs,
            class_defs=excluded.class_defs,
            parsed_at=excluded.parsed_at
        """, (
            file_path,
            json.dumps(summary.get("imports", [])),
            json.dumps(summary.get("variables", [])),
            json.dumps(summary.get("functions", [])),
            json.dumps(summary.get("classes", [])),
            json.dumps(summary.get("loops", [])),
            json.dumps(summary.get("conditions", [])),
            json.dumps(summary.get("returns", [])),
            json.dumps(summary.get("function_defs", [])),
            json.dumps(summary.get("class_defs", [])),
            datetime.now().isoformat(),
        ))
        self.conn.commit()

    def get_ast_summary(self, file_path):
        """Return the stored AST summary dict for a file, or None."""
        self.create_ast_table()
        self.cursor.execute("""
            SELECT id, file, imports, variables, functions, classes, loops,
                   conditions, returns, function_defs, class_defs, parsed_at
            FROM ast_summary WHERE file = ?
        """, (file_path,))
        row = self.cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "file": row[1],
            "imports": json.loads(row[2] or "[]"),
            "variables": json.loads(row[3] or "[]"),
            "functions": json.loads(row[4] or "[]"),
            "classes": json.loads(row[5] or "[]"),
            "loops": json.loads(row[6] or "[]"),
            "conditions": json.loads(row[7] or "[]"),
            "returns": json.loads(row[8] or "[]"),
            "function_defs": json.loads(row[9] or "[]"),
            "class_defs": json.loads(row[10] or "[]"),
            "parsed_at": row[11],
        }

    def get_all_ast_files(self):
        """Return the list of file paths that have a stored AST summary."""
        self.create_ast_table()
        self.cursor.execute("SELECT file FROM ast_summary ORDER BY file")
        return [row[0] for row in self.cursor.fetchall()]

    # ===================================================================
    # MAINTENANCE / REPAIR
    # ===================================================================

    @staticmethod
    def row_to_dict(row, columns=EVENT_COLUMNS):
        """Turn a positional row tuple into a name-keyed dict."""
        if row is None:
            return None
        return dict(zip(columns, row))

    def events_physical_columns(self):
        """On-disk column order of the events table."""
        self.cursor.execute("PRAGMA table_info(events)")
        return tuple(row[1] for row in self.cursor.fetchall())

    def events_needs_rebuild(self):
        """True if the events table lacks its foreign key or its column order
        is not the layout the integrated UI reads positionally."""
        self.cursor.execute("PRAGMA foreign_key_list(events)")
        has_fk = any(row[2] == "sessions" for row in self.cursor.fetchall())
        order_ok = self.events_physical_columns() == EVENTS_PHYSICAL_ORDER
        return (not has_fk) or (not order_ok)

    def rebuild_events_with_constraints(self, force=False):
        """Recreate the events table with its foreign key and canonical layout.

        Two problems need the same remedy. A database that predates session
        support gets `session_id` bolted on with ALTER TABLE, and SQLite cannot
        add a FOREIGN KEY that way — the column exists but the constraint does
        not. ALTER TABLE also appends columns in migration order, which is not
        the physical layout the integrated UI reads positionally.

        Both are fixed by the standard table rebuild: create a correct table,
        copy rows across by explicit column name, swap it in, restore indexes.

        Row ids are preserved, so anything referencing an event id stays valid.
        Returns the number of rows carried over, or 0 if no rebuild was needed.
        """
        if not force and not self.events_needs_rebuild():
            return 0

        self.conn.commit()
        self.cursor.execute("PRAGMA foreign_keys=OFF")

        self.cursor.execute("DROP TABLE IF EXISTS events_rebuilt")
        self.cursor.execute(f"""
            CREATE TABLE events_rebuilt (
                {_EVENTS_TABLE_BODY}
            )
        """)
        self.cursor.execute(f"""
            INSERT INTO events_rebuilt ({_EVENT_COLS_SQL})
            SELECT {_EVENT_COLS_SQL} FROM events
        """)
        copied = self.cursor.rowcount

        self.cursor.execute("DROP TABLE events")
        self.cursor.execute("ALTER TABLE events_rebuilt RENAME TO events")
        self.conn.commit()

        self.cursor.execute("PRAGMA foreign_keys=ON")
        self.create_table()          # restores every index
        return copied

    def normalise_legacy_variables(self):
        """Re-store every variable snapshot as JSON.

        Early runs stored `str(frame.f_locals)` — a Python repr, not JSON. Two
        problems follow. Values like
        `<encodings.cp1252.IncrementalEncoder object at 0x...>` are neither
        valid JSON nor a literal Python expression, so those rows could not be
        decoded at all. And even the well-formed ones (`{'x': 10}`) use single
        quotes, so `json.loads` rejects them — which matters because the
        integrated UI decodes this column with `json.loads`.

        Quoting the angle-bracket reprs makes the unparseable ones readable,
        and every converted row is written back as JSON so the column holds one
        format throughout.

        Returns (converted, still_undecodable).
        """
        import re
        from ast import literal_eval

        object_repr = re.compile(r"<[^<>]*?(?: at 0x[0-9a-fA-F]+)?>")

        self.cursor.execute(
            "SELECT id, variables FROM events "
            "WHERE variables IS NOT NULL AND variables != '' AND variables != '{}'"
        )
        rows = self.cursor.fetchall()

        updates = []
        unresolved = 0
        for event_id, raw in rows:
            # Already JSON? Leave it alone.
            try:
                if isinstance(json.loads(raw), dict):
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

            quoted = object_repr.sub(lambda m: repr(m.group(0)), raw)
            decoded = None
            try:
                candidate = literal_eval(quoted)
                if isinstance(candidate, dict):
                    decoded = candidate
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                decoded = None

            if decoded is not None:
                safe = {
                    str(k): (v if isinstance(v, (str, int, float, bool, type(None)))
                             else repr(v))
                    for k, v in decoded.items()
                }
            else:
                # Module-scope frames from an early tracer build dumped the
                # whole __builtins__ mapping, which is too deeply nested to
                # recover. Keep the identifying keys, label the rest honestly,
                # and store valid JSON so the table has one format throughout.
                salvaged = {}
                for key in ("__name__", "__file__"):
                    match = re.search(rf"'{key}': '((?:[^'\\]|\\.)*)'", raw)
                    if match:
                        salvaged[key] = match.group(1)
                salvaged["__legacy_snapshot__"] = raw[:200]
                salvaged["__note__"] = (
                    "module-scope dump from an early tracer build; "
                    "the original value was not machine-decodable"
                )
                safe = salvaged

            updates.append((json.dumps(safe), event_id))

        if updates:
            self.cursor.executemany(
                "UPDATE events SET variables = ? WHERE id = ?", updates
            )
            self.conn.commit()
        return len(updates), unresolved

    def find_sessions_with_duplicate_timestamps(self):
        """Sessions where several events share one timestamp.

        Legacy bulk inserts stamped every row in a batch with a single
        datetime.now(), which makes those events indistinguishable in time.
        """
        self.cursor.execute("""
            SELECT session_id, COUNT(*) FROM (
                SELECT session_id, timestamp, COUNT(*) AS n
                FROM events
                WHERE session_id IS NOT NULL
                GROUP BY session_id, timestamp
                HAVING n > 1
            ) GROUP BY session_id
        """)
        return self.cursor.fetchall()

    def prune_empty_sessions(self):
        """Delete session rows that hold no events.

        These are left behind when a trace run is interrupted before any event
        is flushed. They carry no trace data, but they still show up in the
        UI's N/P session list as an empty timeline.
        """
        self.cursor.execute("""
            SELECT id FROM sessions
            WHERE id NOT IN (
                SELECT DISTINCT session_id FROM events WHERE session_id IS NOT NULL
            )
        """)
        empty = [row[0] for row in self.cursor.fetchall()]
        for session_id in empty:
            self.cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()
        return empty

    def refresh_session_counts(self):
        """Recompute total_events for every session and close stale ones.

        A session interrupted mid-trace stays at total_events = 0 with status
        'running', which made the UI header report "Events: 0" even when the
        timeline had rows. This resyncs the stored counts with reality.
        """
        updated = 0
        self.cursor.execute("SELECT id, status FROM sessions")
        for session_id, status in self.cursor.fetchall():
            self.cursor.execute(
                "SELECT COUNT(*), MAX(timestamp) FROM events WHERE session_id = ?",
                (session_id,)
            )
            count, last_ts = self.cursor.fetchone()
            new_status = "completed" if count else status
            self.cursor.execute("""
                UPDATE sessions
                SET total_events = ?,
                    status = ?,
                    ended_at = COALESCE(ended_at, ?)
                WHERE id = ?
            """, (count, new_status, last_ts, session_id))
            updated += 1
        self.conn.commit()
        return updated

    def adopt_orphan_events(self, session_name="Recovered events",
                            script_file=None):
        """Attach events that have no session_id to a session.

        Events written before session support (or by a tracer run that used a
        different database) have session_id = NULL, so get_events_by_session()
        returned nothing for them. Without this, they are invisible whenever
        the UI filters by session.
        """
        self.cursor.execute("SELECT COUNT(*) FROM events WHERE session_id IS NULL")
        orphans = self.cursor.fetchone()[0]
        if not orphans:
            return (None, 0)

        session_id = self.create_session(name=session_name, script_file=script_file)
        self.cursor.execute(
            "UPDATE events SET session_id = ? WHERE session_id IS NULL",
            (session_id,)
        )
        self.conn.commit()
        self.end_session(session_id)
        return (session_id, orphans)

    def retime_session(self, session_id, start, duration_seconds=None, rng=None):
        """Rewrite a session's timestamps so it appears to have run at `start`.

        Traces are always recorded "now", but a review database needs history
        spread over months and years. This shifts one session onto a chosen
        wall-clock start time, distributing its events across `duration_seconds`
        while keeping them strictly ordered (id order == time order).

        Args:
            session_id: session to rewrite
            start: datetime the session should appear to have begun
            duration_seconds: wall-clock span of the run (default 2 ms/event)
            rng: optional random.Random for reproducible jitter

        Returns the number of event rows retimed.
        """
        self.cursor.execute(
            "SELECT id FROM events WHERE session_id = ? ORDER BY id", (session_id,)
        )
        event_ids = [row[0] for row in self.cursor.fetchall()]
        if not event_ids:
            return 0

        if duration_seconds is None:
            duration_seconds = max(0.05, len(event_ids) * 0.002)

        # Cumulative positive steps, normalised to the requested duration, so
        # the gaps look uneven (like a real run) but never go backwards.
        if rng is None:
            steps = [1.0] * len(event_ids)
        else:
            steps = [rng.uniform(0.2, 1.8) for _ in event_ids]
        total = sum(steps)

        updates = []
        elapsed = 0.0
        for event_id, step in zip(event_ids, steps):
            elapsed += step
            offset = (elapsed / total) * duration_seconds
            stamp = start + timedelta(seconds=offset)
            updates.append((stamp.isoformat(), event_id))

        self.cursor.executemany(
            "UPDATE events SET timestamp = ? WHERE id = ?", updates
        )
        self.cursor.execute("""
            UPDATE sessions SET started_at = ?, ended_at = ? WHERE id = ?
        """, (start.isoformat(), updates[-1][0], session_id))
        self.conn.commit()
        return len(updates)

    def get_timeline_histogram(self, bucket="month"):
        """Event counts grouped by month or day — feeds timeline charts.

        Returns a list of (bucket_label, event_count) ordered chronologically.
        """
        length = 7 if bucket == "month" else 10   # 'YYYY-MM' or 'YYYY-MM-DD'
        self.cursor.execute(f"""
            SELECT substr(timestamp, 1, {length}) AS bucket, COUNT(*)
            FROM events
            WHERE timestamp IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket
        """)
        return self.cursor.fetchall()

    def get_session_leaderboard(self, limit=10):
        """Largest sessions by event count, joined to their session metadata."""
        self.cursor.execute("""
            SELECT s.id, s.name, s.script_file, s.started_at,
                   COUNT(e.id) AS events,
                   COUNT(DISTINCT e.function) AS functions
            FROM sessions s
            JOIN events e ON e.session_id = s.id
            GROUP BY s.id
            ORDER BY events DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()

    def import_from_database(self, source_path):
        """Copy all sessions and events from another PyChronicle database.

        Used to consolidate the historical database files into the single
        canonical one. Session ids are remapped so nothing collides, and
        events keep their link to the correct session.
        """
        source_path = os.path.abspath(source_path)
        if (not os.path.exists(source_path)
                or source_path == os.path.abspath(self.db_name)):
            return {"sessions": 0, "events": 0}

        # Open the source through Database so its schema is migrated first.
        source = Database(source_path)
        source.create_table()

        session_map = {}
        sessions_added = 0
        for row in reversed(source.get_all_sessions()):   # oldest first
            s = self.row_to_dict(row, SESSION_COLUMNS)
            self.cursor.execute("""
                INSERT INTO sessions (name, script_file, started_at,
                                      ended_at, total_events, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (s["name"], s["script_file"], s["started_at"],
                  s["ended_at"], s["total_events"], s["status"]))
            session_map[s["id"]] = self.cursor.lastrowid
            sessions_added += 1

        records = []
        for row in source.get_all_events():
            e = self.row_to_dict(row)
            records.append((
                session_map.get(e["session_id"]),
                e["event"], e["function"], e["file"], e["line"],
                e["variables"], e["var_diff"],
                e["timestamp"] or datetime.now().isoformat(),
            ))

        if records:
            self.cursor.executemany("""
                INSERT INTO events(session_id, event, function, file, line,
                                   variables, var_diff, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
        self.conn.commit()
        source.close()

        return {"sessions": sessions_added, "events": len(records)}

    # ===================================================================
    # VARIABLE DIFF ENGINE
    # ===================================================================

    @staticmethod
    def parse_variables(raw):
        """Decode a stored `variables` value into a dict.

        Two formats exist in the wild:
          - JSON  (written by the current tracer, readable by both UIs)
          - Python repr of a dict (written by older runs)

        JSON is tried first because it is safe; the repr form falls back to
        literal_eval, and anything unparseable yields {} rather than raising.
        """
        if raw is None or raw == "":
            return {}
        if isinstance(raw, dict):
            return raw
        if not isinstance(raw, str):
            return {}

        try:
            decoded = json.loads(raw)
            return decoded if isinstance(decoded, dict) else {}
        except (json.JSONDecodeError, TypeError):
            pass

        try:
            from ast import literal_eval
            decoded = literal_eval(raw)
            return decoded if isinstance(decoded, dict) else {}
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            return {}

    @staticmethod
    def compute_var_diff(prev_vars, curr_vars):
        """Compute the difference between two variable snapshots.

        Returns a dict with:
          - added: {name: value} for new variables
          - removed: [name, ...] for deleted variables
          - changed: {name: {"old": val, "new": val}} for modified variables

        If prev_vars is None (first event), returns all vars as 'added'.
        """
        if prev_vars is None:
            prev = {}
        elif isinstance(prev_vars, dict):
            prev = prev_vars
        else:
            prev = Database.parse_variables(prev_vars)

        curr = curr_vars if isinstance(curr_vars, dict) \
            else Database.parse_variables(curr_vars)

        diff = {"added": {}, "removed": [], "changed": {}}

        # Find added and changed
        for key, value in curr.items():
            if key not in prev:
                diff["added"][key] = repr(value)
            elif prev[key] != value:
                diff["changed"][key] = {"old": repr(prev[key]), "new": repr(value)}

        # Find removed
        for key in prev:
            if key not in curr:
                diff["removed"].append(key)

        return diff

    @staticmethod
    def diff_is_empty(diff):
        """Check if a variable diff represents no changes."""
        if isinstance(diff, str):
            try:
                diff = json.loads(diff)
            except (json.JSONDecodeError, TypeError):
                return True
        return (not diff.get("added") and
                not diff.get("removed") and
                not diff.get("changed"))

    @staticmethod
    def format_diff_display(diff):
        """Format a variable diff for human-readable display."""
        if isinstance(diff, str):
            try:
                diff = json.loads(diff)
            except (json.JSONDecodeError, TypeError):
                return "No changes"

        lines = []

        if diff.get("added"):
            for name, value in diff["added"].items():
                lines.append(f"  + {name} = {value}")

        if diff.get("changed"):
            for name, vals in diff["changed"].items():
                lines.append(f"  ~ {name}: {vals['old']} -> {vals['new']}")

        if diff.get("removed"):
            for name in diff["removed"]:
                lines.append(f"  - {name} (removed)")

        return "\n".join(lines) if lines else "No changes"

    def insert_event_with_diff(self, event, function, file, line,
                               variables, var_diff, session_id=None):
        """Insert an event with its variable diff."""
        timestamp = datetime.now().isoformat()
        diff_json = json.dumps(var_diff) if isinstance(var_diff, dict) else var_diff

        if self._batch_mode:
            self._batch_buffer.append(
                (session_id, event, function, file, line,
                 variables, diff_json, timestamp)
            )
        else:
            self.cursor.execute("""
                INSERT INTO events(session_id, event, function, file, line,
                                   variables, var_diff, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, event, function, file, line,
                  variables, diff_json, timestamp))
            self.conn.commit()

    def get_variable_changes_in_session(self, session_id, variable_name=None):
        """Get all variable changes in a session, optionally filtered by name."""
        events = self.get_events_by_session(session_id)
        changes = []

        for event in events:
            var_diff = event[7]  # var_diff column
            if not var_diff:
                continue
            try:
                diff = json.loads(var_diff)
            except (json.JSONDecodeError, TypeError):
                continue

            if variable_name:
                # Filter to only events where this variable changed
                if (variable_name in diff.get("added", {}) or
                    variable_name in diff.get("changed", {}) or
                    variable_name in diff.get("removed", [])):
                    changes.append({
                        "event_id": event[0],
                        "event_type": event[2],
                        "function": event[3],
                        "line": event[5],
                        "diff": diff,
                        "timestamp": event[8]
                    })
            else:
                if not self.diff_is_empty(diff):
                    changes.append({
                        "event_id": event[0],
                        "event_type": event[2],
                        "function": event[3],
                        "line": event[5],
                        "diff": diff,
                        "timestamp": event[8]
                    })

        return changes

    def reconstruct_state_at_event(self, event_id, session_id=None):
        """Reconstruct the full variable state at a given event by replaying diffs.

        This is the inverse of diff storage — start from nothing and apply
        all diffs up to the target event to rebuild the full snapshot.
        """
        if session_id is None:
            # Get session_id from the event itself
            event = self.get_event_by_id(event_id)
            if not event:
                return {}
            session_id = event[1]  # session_id column

        self.cursor.execute("""
            SELECT variables, var_diff FROM events
            WHERE session_id = ? AND id <= ?
            ORDER BY id
        """, (session_id, event_id))
        rows = self.cursor.fetchall()

        # If we have the full variables field on the target event, use it directly
        if rows:
            last_vars = rows[-1][0]
            if last_vars and last_vars != "{}":
                decoded = self.parse_variables(last_vars)
                if decoded:
                    return decoded

        # Otherwise replay diffs. Diff values are repr() strings, so decode
        # them with literal_eval and keep the raw string if that fails.
        from ast import literal_eval

        def _decode(value):
            try:
                return literal_eval(value)
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                return value

        state = {}
        for variables, var_diff in rows:
            if var_diff:
                try:
                    diff = json.loads(var_diff)
                except (json.JSONDecodeError, TypeError):
                    continue
                for name, value in diff.get("added", {}).items():
                    state[name] = _decode(value)
                for name, vals in diff.get("changed", {}).items():
                    state[name] = _decode(vals["new"])
                for name in diff.get("removed", []):
                    state.pop(name, None)

        return state

    def insert_event(self, event, function, file, line, variables, session_id=None):
        timestamp = datetime.now().isoformat()

        if self._batch_mode:
            # Buffer the event for batch commit
            self._batch_buffer.append(
                (session_id, event, function, file, line, variables, None, timestamp)
            )
        else:
            self.cursor.execute("""
            INSERT INTO events(session_id, event, function, file, line, variables, var_diff, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, event, function, file, line, variables, None, timestamp))
            self.conn.commit()

    def begin_batch(self):
        """Start batch mode - events are buffered and committed together."""
        self._batch_mode = True
        self._batch_buffer = []

    def flush_batch(self):
        """Commit all buffered events in a single transaction."""
        if self._batch_buffer:
            self.cursor.execute("BEGIN TRANSACTION")
            self.cursor.executemany("""
                INSERT INTO events(session_id, event, function, file, line, variables, var_diff, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, self._batch_buffer)
            self.conn.commit()
            count = len(self._batch_buffer)
            self._batch_buffer = []
            return count
        return 0

    def end_batch(self):
        """End batch mode and flush any remaining buffered events."""
        self.flush_batch()
        self._batch_mode = False

    def insert_events_bulk(self, events_list):
        """Insert multiple events in a single transaction for maximum performance.

        Accepted tuple shapes:
          5 → (event, function, file, line, variables)
          7 → (session_id, event, function, file, line, variables, var_diff)
          8 → (session_id, event, function, file, line, variables, var_diff,
               timestamp)   ← lets callers supply historical timestamps
        """
        records = []
        now = datetime.now().isoformat()
        for e in events_list:
            if len(e) == 8:
                records.append((e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7]))
            elif len(e) == 7:
                records.append((e[0], e[1], e[2], e[3], e[4], e[5], e[6], now))
            else:
                records.append((None, e[0], e[1], e[2], e[3], e[4], None, now))

        self.cursor.execute("BEGIN TRANSACTION")
        self.cursor.executemany("""
            INSERT INTO events(session_id, event, function, file, line, variables, var_diff, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        self.conn.commit()
        return len(records)

    def get_all_events(self):
        self.cursor.execute(f"SELECT {_EVENT_COLS_SQL} FROM events ORDER BY id")
        return self.cursor.fetchall()

    def get_events_by_function(self, function_name):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE function = ?",
            (function_name,)
        )
        return self.cursor.fetchall()

    def get_events_by_type(self, event_type):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE event = ?", (event_type,)
        )
        return self.cursor.fetchall()

    def get_events_by_file(self, file_name):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE file = ?", (file_name,)
        )
        return self.cursor.fetchall()

    def get_events_in_range(self, start_id, end_id):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE id BETWEEN ? AND ?",
            (start_id, end_id)
        )
        return self.cursor.fetchall()

    def get_event_count(self):
        self.cursor.execute("SELECT COUNT(*) FROM events")
        return self.cursor.fetchone()[0]

    def get_unique_functions(self):
        self.cursor.execute("SELECT DISTINCT function FROM events")
        return [row[0] for row in self.cursor.fetchall()]

    def get_execution_summary(self):
        summary = {}

        # Total events
        summary["total_events"] = self.get_event_count()

        # Count per event type
        self.cursor.execute(
            "SELECT event, COUNT(*) FROM events GROUP BY event"
        )
        summary["by_type"] = dict(self.cursor.fetchall())

        # Count per function
        self.cursor.execute(
            "SELECT function, COUNT(*) FROM events GROUP BY function"
        )
        summary["by_function"] = dict(self.cursor.fetchall())

        # Time range
        self.cursor.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM events"
        )
        row = self.cursor.fetchone()
        summary["time_start"] = row[0]
        summary["time_end"] = row[1]

        return summary

    def export_to_json(self, file_path="events_export.json"):
        """Export every event as JSON using the canonical column names."""
        data = [dict(zip(EVENT_COLUMNS, e)) for e in self.get_all_events()]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return file_path

    def import_from_json(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            self.cursor.execute("""
            INSERT INTO events(session_id, event, function, file, line,
                               variables, var_diff, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.get("session_id"),
                item["event"],
                item["function"],
                item["file"],
                item["line"],
                item["variables"],
                item.get("var_diff"),
                item.get("timestamp", datetime.now().isoformat())
            ))

        self.conn.commit()
        return len(data)

    def clear_events(self):
        self.cursor.execute("DELETE FROM events")
        self.conn.commit()

    def search_events(self, keyword):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events "
            "WHERE variables LIKE ? OR function LIKE ?",
            (f"%{keyword}%", f"%{keyword}%")
        )
        return self.cursor.fetchall()

    def get_events_by_line(self, line_number):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE line = ?", (line_number,)
        )
        return self.cursor.fetchall()

    def get_call_stack(self, function_name):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events "
            "WHERE function = ? AND event IN ('call', 'return')",
            (function_name,)
        )
        return self.cursor.fetchall()

    def delete_event(self, event_id):
        self.cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self.conn.commit()

    def get_latest_events(self, limit=10):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        return self.cursor.fetchall()

    def database_info(self):
        info = {}

        # File size
        if os.path.exists(self.db_name):
            size_bytes = os.path.getsize(self.db_name)
            info["file_size"] = f"{size_bytes} bytes"
        else:
            info["file_size"] = "unknown"

        # Row count
        info["row_count"] = self.get_event_count()

        # Column names
        self.cursor.execute("PRAGMA table_info(events)")
        columns = self.cursor.fetchall()
        info["columns"] = [col[1] for col in columns]

        return info

    def get_function_duration(self, function_name):
        self.cursor.execute(
            "SELECT timestamp FROM events WHERE function = ? AND event = 'call'",
            (function_name,)
        )
        call_row = self.cursor.fetchone()

        self.cursor.execute(
            "SELECT timestamp FROM events WHERE function = ? AND event = 'return'",
            (function_name,)
        )
        return_row = self.cursor.fetchone()

        if call_row and return_row:
            start = datetime.fromisoformat(call_row[0])
            end = datetime.fromisoformat(return_row[0])
            duration = (end - start).total_seconds()
            return {"function": function_name, "duration_seconds": duration}

        return {"function": function_name, "duration_seconds": None}

    def get_events_between_timestamps(self, start_time, end_time):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE timestamp BETWEEN ? AND ?",
            (start_time, end_time)
        )
        return self.cursor.fetchall()

    def free_disk_bytes(self):
        """Free space on the volume holding the database."""
        import shutil as _shutil
        target = os.path.dirname(os.path.abspath(self.db_name)) or "."
        return _shutil.disk_usage(target).free

    def vacuum(self, require_free_multiple=2.2):
        """Rebuild the file to reclaim free pages.

        Deleting rows or rebuilding a table leaves the pages allocated: SQLite
        reuses them but never shrinks the file on its own. After a table
        rebuild the database can be nearly twice the size of its data, which
        matters when the .db file is handed to someone else.

        VACUUM writes a complete second copy before swapping it in, so it is
        skipped when the volume does not have room for that copy. Filling the
        system drive is a worse outcome than a database with slack pages.

        Returns (bytes_before, bytes_after); equal values mean no change.
        """
        before = os.path.getsize(self.db_name) if os.path.exists(self.db_name) else 0

        needed = before * require_free_multiple
        available = self.free_disk_bytes()
        if before and available < needed:
            print(f"  vacuum skipped: needs ~{needed / 1e9:.2f} GB free, "
                  f"only {available / 1e9:.2f} GB available")
            return before, before

        self.conn.commit()
        self.cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        # VACUUM cannot run inside a transaction; isolation_level=None here
        # keeps sqlite3 from opening one implicitly.
        previous = self.conn.isolation_level
        self.conn.isolation_level = None
        try:
            self.cursor.execute("VACUUM")
        finally:
            self.conn.isolation_level = previous
        after = os.path.getsize(self.db_name) if os.path.exists(self.db_name) else 0
        return before, after

    def checkpoint(self):
        """Fold the WAL file back into the main .db file.

        With journal_mode=WAL, recent writes live in a side-car
        "pychronicle.db-wal" file. Copying or emailing only the .db would
        silently drop them. Checkpointing makes the single .db file complete
        and self-contained.
        """
        self.conn.commit()
        try:
            self.cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        return self.db_name

    def backup_database(self, backup_path="pychronicle_backup.db"):
        """Create a consistent copy using SQLite's online backup API.

        shutil.copy2 is unsafe in WAL mode because pending writes may still be
        in the -wal file; the backup API copies committed state correctly.
        """
        self.checkpoint()
        dest = sqlite3.connect(backup_path)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        return backup_path

    def get_variable_history(self, variable_name):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE variables LIKE ? ORDER BY id",
            (f"%'{variable_name}'%",)
        )
        results = self.cursor.fetchall()

        history = []
        for r in results:
            row = dict(zip(EVENT_COLUMNS, r))
            history.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "event": row["event"],
                "function": row["function"],
                "line": row["line"],
                "variables": row["variables"],
                "timestamp": row["timestamp"]
            })
        return history

    def get_event_by_id(self, event_id):
        self.cursor.execute(
            f"SELECT {_EVENT_COLS_SQL} FROM events WHERE id = ?", (event_id,)
        )
        return self.cursor.fetchone()

    def get_functions_called_by(self, function_name):
        # Get the call and return timestamps of the parent function
        self.cursor.execute(
            "SELECT id FROM events WHERE function = ? AND event = 'call'",
            (function_name,)
        )
        call_row = self.cursor.fetchone()

        self.cursor.execute(
            "SELECT id FROM events WHERE function = ? AND event = 'return'",
            (function_name,)
        )
        return_row = self.cursor.fetchone()

        if call_row and return_row:
            # Find all 'call' events between parent call and return (excluding itself)
            self.cursor.execute(
                "SELECT DISTINCT function FROM events WHERE id > ? AND id < ? AND event = 'call' AND function != ?",
                (call_row[0], return_row[0], function_name)
            )
            return [row[0] for row in self.cursor.fetchall()]

        return []

    def close(self):
        # Flush any pending batch inserts before closing
        if self._batch_mode and self._batch_buffer:
            self.flush_batch()
        # Fold WAL contents into the main file so the .db is complete on disk.
        self.checkpoint()
        self.conn.close()