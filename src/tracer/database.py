import sqlite3
import json
import os
import shutil
from datetime import datetime


class Database:

    def __init__(self, db_name="pychronicle.db"):
        self.db_name = db_name
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

        # --- Events table (with optional session_id) ---
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            event TEXT,
            function TEXT,
            file TEXT,
            line INTEGER,
            variables TEXT,
            var_diff TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
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
        self.conn.commit()

    def _migrate_schema(self):
        """Add new columns to existing databases without losing data."""
        # Check columns in events table
        self.cursor.execute("PRAGMA table_info(events)")
        columns = [col[1] for col in self.cursor.fetchall()]

        if "session_id" not in columns:
            self.cursor.execute("ALTER TABLE events ADD COLUMN session_id INTEGER")

        if "var_diff" not in columns:
            self.cursor.execute("ALTER TABLE events ADD COLUMN var_diff TEXT")

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
        """Return all sessions ordered by most recent first."""
        self.cursor.execute("SELECT * FROM sessions ORDER BY id DESC")
        return self.cursor.fetchall()

    def get_session_by_id(self, session_id):
        self.cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        return self.cursor.fetchone()

    def get_events_by_session(self, session_id):
        """Get all events belonging to a specific session."""
        self.cursor.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY id", (session_id,)
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
    # VARIABLE DIFF ENGINE
    # ===================================================================

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
        elif isinstance(prev_vars, str):
            try:
                prev = eval(prev_vars) if prev_vars else {}
            except Exception:
                prev = {}
        else:
            prev = prev_vars

        if isinstance(curr_vars, str):
            try:
                curr = eval(curr_vars) if curr_vars else {}
            except Exception:
                curr = {}
        else:
            curr = curr_vars

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
                try:
                    return eval(last_vars)
                except Exception:
                    pass

        # Otherwise replay diffs
        state = {}
        for variables, var_diff in rows:
            if var_diff:
                try:
                    diff = json.loads(var_diff)
                    for name, value in diff.get("added", {}).items():
                        try:
                            state[name] = eval(value)
                        except Exception:
                            state[name] = value
                    for name, vals in diff.get("changed", {}).items():
                        try:
                            state[name] = eval(vals["new"])
                        except Exception:
                            state[name] = vals["new"]
                    for name in diff.get("removed", []):
                        state.pop(name, None)
                except (json.JSONDecodeError, TypeError):
                    pass

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

        Args:
            events_list: List of tuples (event, function, file, line, variables)
                         or (session_id, event, function, file, line, variables, var_diff)
        """
        records = []
        for e in events_list:
            if len(e) == 5:
                records.append((None, e[0], e[1], e[2], e[3], e[4], None, datetime.now().isoformat()))
            elif len(e) == 7:
                records.append((e[0], e[1], e[2], e[3], e[4], e[5], e[6], datetime.now().isoformat()))
            else:
                records.append((None, e[0], e[1], e[2], e[3], e[4], None, datetime.now().isoformat()))

        self.cursor.execute("BEGIN TRANSACTION")
        self.cursor.executemany("""
            INSERT INTO events(session_id, event, function, file, line, variables, var_diff, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
        self.conn.commit()
        return len(records)

    def get_all_events(self):
        self.cursor.execute("SELECT * FROM events")
        return self.cursor.fetchall()

    def get_events_by_function(self, function_name):
        self.cursor.execute(
            "SELECT * FROM events WHERE function = ?", (function_name,)
        )
        return self.cursor.fetchall()

    def get_events_by_type(self, event_type):
        self.cursor.execute(
            "SELECT * FROM events WHERE event = ?", (event_type,)
        )
        return self.cursor.fetchall()

    def get_events_by_file(self, file_name):
        self.cursor.execute(
            "SELECT * FROM events WHERE file = ?", (file_name,)
        )
        return self.cursor.fetchall()

    def get_events_in_range(self, start_id, end_id):
        self.cursor.execute(
            "SELECT * FROM events WHERE id BETWEEN ? AND ?", (start_id, end_id)
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
        events = self.get_all_events()
        data = []
        for e in events:
            data.append({
                "id": e[0],
                "event": e[1],
                "function": e[2],
                "file": e[3],
                "line": e[4],
                "variables": e[5],
                "timestamp": e[6]
            })

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return file_path

    def import_from_json(self, file_path):
        with open(file_path, "r") as f:
            data = json.load(f)

        for item in data:
            self.cursor.execute("""
            INSERT INTO events(event, function, file, line, variables, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item["event"],
                item["function"],
                item["file"],
                item["line"],
                item["variables"],
                item.get("timestamp", datetime.now().isoformat())
            ))

        self.conn.commit()
        return len(data)

    def clear_events(self):
        self.cursor.execute("DELETE FROM events")
        self.conn.commit()

    def search_events(self, keyword):
        self.cursor.execute(
            "SELECT * FROM events WHERE variables LIKE ? OR function LIKE ?",
            (f"%{keyword}%", f"%{keyword}%")
        )
        return self.cursor.fetchall()

    def get_events_by_line(self, line_number):
        self.cursor.execute(
            "SELECT * FROM events WHERE line = ?", (line_number,)
        )
        return self.cursor.fetchall()

    def get_call_stack(self, function_name):
        self.cursor.execute(
            "SELECT * FROM events WHERE function = ? AND event IN ('call', 'return')",
            (function_name,)
        )
        return self.cursor.fetchall()

    def delete_event(self, event_id):
        self.cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
        self.conn.commit()

    def get_latest_events(self, limit=10):
        self.cursor.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
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
            "SELECT * FROM events WHERE timestamp BETWEEN ? AND ?",
            (start_time, end_time)
        )
        return self.cursor.fetchall()

    def backup_database(self, backup_path="pychronicle_backup.db"):
        self.conn.commit()
        shutil.copy2(self.db_name, backup_path)
        return backup_path

    def get_variable_history(self, variable_name):
        self.cursor.execute("SELECT * FROM events WHERE variables LIKE ?",
                            (f"%'{variable_name}'%",))
        results = self.cursor.fetchall()

        history = []
        for r in results:
            variables = r[5]
            history.append({
                "id": r[0],
                "event": r[1],
                "function": r[2],
                "line": r[4],
                "variables": variables,
                "timestamp": r[6]
            })
        return history

    def get_event_by_id(self, event_id):
        self.cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
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
        self.conn.close()