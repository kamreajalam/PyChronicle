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

    def create_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            function TEXT,
            file TEXT,
            line INTEGER,
            variables TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        self.conn.commit()

    def insert_event(self, event, function, file, line, variables):
        self.cursor.execute("""
        INSERT INTO events(event, function, file, line, variables, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (event, function, file, line, variables, datetime.now().isoformat()))

        self.conn.commit()

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
        self.conn.close()