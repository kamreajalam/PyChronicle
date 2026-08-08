import copy
import json
import os
import sqlite3

from src.config import get_db_path


# ============================================================
# DEMO DATA
# ============================================================

DEMO_STEPS = {
    "step1": {
        "code": (
            "# Step 1: Initialize values\n"
            "x = 5\n"
            "y = 10\n"
            "total = 0"
        ),
        "vars": (
            "x = 5\n"
            "y = 10\n"
            "total = 0"
        ),
        "event": "System initialized variables.",
        "line_number": 1,
    },
    "step2": {
        "code": (
            "# Step 2: Add values together\n"
            "x = 5\n"
            "y = 10\n"
            "total = x + y"
        ),
        "vars": (
            "x = 5\n"
            "y = 10\n"
            "total = 15"
        ),
        "event": "Executed addition.",
        "line_number": 3,
    },
}


# ============================================================
# VARIABLE FORMATTER
# ============================================================

def format_vars(vars_data):
    """Convert variable data into display-ready text."""

    if vars_data is None:
        return ""

    if isinstance(vars_data, dict):

        output = []

        for key, value in vars_data.items():

            # Hide function memory addresses
            if (
                isinstance(value, str)
                and "<function" in value
            ):
                continue

            output.append(
                f"{key} = {value}"
            )

        return "\n".join(output)

    return str(vars_data)


# ============================================================
# JSON LOADER
# ============================================================

def load_from_json(json_path="trace_output.json"):
    """Load trace data from JSON."""

    if not json_path:
        return None

    if not os.path.exists(json_path):
        return None

    try:

        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict) and data:
            return data

    except (
        json.JSONDecodeError,
        OSError
    ) as exc:

        print(
            f"Error reading JSON trace "
            f"'{json_path}': {exc}"
        )

    return None


# ============================================================
# LATEST SESSION
# ============================================================

def _find_latest_session(cursor):
    """
    Return the latest completed session ID.

    If the sessions table does not match the expected schema,
    return None instead of failing.
    """

    try:

        cursor.execute(
            """
            SELECT id
            FROM sessions
            WHERE status = 'completed'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row:
            return row[0]

    except sqlite3.Error:
        pass

    return None


# ============================================================
# SOURCE CODE LOADER
# ============================================================

def _source_code(file_path, line_number):
    """
    Read source code around a traced line.

    Returns:
        (code_text, relative_line_number)
    """

    if not file_path:
        return "", 1

    if not os.path.exists(file_path):
        return "", 1

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as file:

            lines = file.readlines()

        if not lines:
            return "", 1

        try:
            line_number = int(line_number)

        except (
            TypeError,
            ValueError
        ):

            line_number = 1

        line_number = max(
            1,
            min(
                line_number,
                len(lines)
            )
        )

        start = max(
            0,
            line_number - 3
        )

        end = min(
            len(lines),
            line_number + 2
        )

        code = "".join(
            lines[start:end]
        ).rstrip()

        relative_line = (
            line_number - start
        )

        return (
            code,
            relative_line
        )

    except OSError:

        return "", 1


# ============================================================
# HELPER: FIND COLUMN
# ============================================================

def _find_column(columns, candidates):
    """
    Find the first matching column from a list of possible
    column names.
    """

    lowered = {
        str(column).lower(): column
        for column in columns
    }

    for candidate in candidates:

        if candidate.lower() in lowered:
            return lowered[candidate.lower()]

    return None


# ============================================================
# SQLITE LOADER
# ============================================================

def load_from_sqlite(db_path="pychronicle.db"):
    """
    Load execution data from SQLite.

    Supports both:

    1. Real PyChronicle database
       - sessions
       - events
       - session_id

    2. Small/simple SQLite databases used by tests.
    """

    if not db_path:
        return None

    if not os.path.exists(db_path):
        return None

    conn = None

    try:

        conn = sqlite3.connect(
            str(db_path)
        )

        cursor = conn.cursor()

        # ========================================================
        # FIND TABLES
        # ========================================================

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        tables = {
            row[0]
            for row in cursor.fetchall()
        }

        if "events" not in tables:
            return None

        # ========================================================
        # FIND EVENT TABLE COLUMNS
        # ========================================================

        cursor.execute(
            "PRAGMA table_info(events)"
        )

        column_rows = cursor.fetchall()

        columns = [
            row[1]
            for row in column_rows
        ]

        if not columns:
            return None

        # ========================================================
        # FIND COMMON COLUMN NAMES
        # ========================================================

        id_column = _find_column(
            columns,
            [
                "id",
                "event_id",
                "step_id",
            ]
        )

        event_column = _find_column(
            columns,
            [
                "event",
                "event_type",
                "type",
                "event_name",
            ]
        )

        function_column = _find_column(
            columns,
            [
                "function",
                "function_name",
                "func",
            ]
        )

        file_column = _find_column(
            columns,
            [
                "file",
                "file_path",
                "filename",
                "source_file",
            ]
        )

        line_column = _find_column(
            columns,
            [
                "line",
                "line_number",
                "lineno",
                "source_line",
            ]
        )

        variables_column = _find_column(
            columns,
            [
                "variables",
                "vars",
                "variable",
                "variable_data",
            ]
        )

        var_diff_column = _find_column(
            columns,
            [
                "var_diff",
                "variable_diff",
                "changes",
                "diff",
            ]
        )

        timestamp_column = _find_column(
            columns,
            [
                "timestamp",
                "created_at",
                "time",
            ]
        )

        session_column = _find_column(
            columns,
            [
                "session_id",
                "session",
            ]
        )

        # ========================================================
        # LATEST SESSION
        # ========================================================

        session_id = None

        if (
            session_column is not None
            and "sessions" in tables
        ):

            session_id = _find_latest_session(
                cursor
            )

        # ========================================================
        # SELECT ALL EVENTS
        #
        # We intentionally select * so that small test databases
        # with different schemas also work.
        # ========================================================

        query = "SELECT * FROM events"

        params = []

        if (
            session_id is not None
            and session_column is not None
        ):

            query += (
                f" WHERE {session_column} = ?"
            )

            params.append(
                session_id
            )

        # Order by ID if available.

        if id_column is not None:

            query += (
                f" ORDER BY {id_column} ASC"
            )

        else:

            query += " ORDER BY rowid ASC"

        cursor.execute(
            query,
            params
        )

        rows = cursor.fetchall()

        if not rows:
            return None

        # ========================================================
        # CREATE COLUMN INDEX
        # ========================================================

        column_index = {
            column: index
            for index, column
            in enumerate(columns)
        }

        def get_value(row, column):
            """Safely get a value from a database row."""

            if column is None:
                return None

            index = column_index.get(
                column
            )

            if index is None:
                return None

            return row[index]

        # ========================================================
        # BUILD STEPS
        # ========================================================

        steps = {}

        for index, row in enumerate(
            rows,
            start=1
        ):

            event_id = get_value(
                row,
                id_column
            )

            event = get_value(
                row,
                event_column
            )

            function = get_value(
                row,
                function_column
            )

            file_path = get_value(
                row,
                file_column
            )

            line_number = get_value(
                row,
                line_column
            )

            variables = get_value(
                row,
                variables_column
            )

            var_diff = get_value(
                row,
                var_diff_column
            )

            timestamp = get_value(
                row,
                timestamp_column
            )

            # ====================================================
            # PARSE VARIABLES
            # ====================================================

            parsed_vars = variables

            if isinstance(
                variables,
                str
            ):

                text = variables.strip()

                if text:

                    try:

                        parsed_vars = json.loads(
                            text
                        )

                    except (
                        json.JSONDecodeError,
                        TypeError
                    ):

                        parsed_vars = variables

            # ====================================================
            # FORMAT VARIABLES
            # ====================================================

            vars_text = format_vars(
                parsed_vars
            )

            # ====================================================
            # BASIC VALUES
            # ====================================================

            event_name = (
                event
                if event is not None
                else "unknown"
            )

            function_name = (
                function
                if function is not None
                else "unknown"
            )

            line_value = (
                line_number
                if line_number is not None
                else 1
            )

            filename = (
                os.path.basename(
                    str(file_path)
                )
                if file_path
                else "unknown"
            )

            # ====================================================
            # EVENT LOG
            # ====================================================

            event_text = (
                f"Event: {event_name}\n"
                f"Function: {function_name}\n"
                f"File: {filename}\n"
                f"Line: {line_value}"
            )

            if var_diff:

                event_text += (
                    f"\nVariable changes: "
                    f"{var_diff}"
                )

            # ====================================================
            # SOURCE CODE
            # ====================================================

            code_text = ""

            if file_path:

                code_text, _ = _source_code(
                    str(file_path),
                    line_value
                )

            # ====================================================
            # FALLBACK CODE
            # ====================================================

            if not code_text:

                code_text = (
                    f"# Event {event_id or index}\n"
                    f"# Function: {function_name}\n"
                    f"# Line: {line_value}"
                )

            # ====================================================
            # STORE STEP
            # ====================================================

            steps[
                f"step{index}"
            ] = {
                "code": code_text,
                "vars": vars_text,
                "event": event_text,
                "line_number": line_value,
                "source_line": line_value,
                "function": function,
                "file": file_path,
                "event_id": event_id or index,
                "session_id": session_id,
                "var_diff": var_diff,
                "timestamp": timestamp,
            }

        return steps

    except (
        sqlite3.Error,
        OSError,
        TypeError,
        ValueError
    ) as exc:

        print(
            f"SQLite loading error: {exc}"
        )

        return None

    finally:

        if conn is not None:

            conn.close()


# ============================================================
# MAIN TRACE LOADER
# ============================================================

def load_tracer_data(
    json_path="trace_output.json",
    db_path="pychronicle.db"
):
    """
    Load execution data.

    Priority:

    1. SQLite real execution data
    2. JSON backup
    3. Demo data
    """

    # ========================================================
    # 1. SQLITE
    # ========================================================

    data = load_from_sqlite(
        db_path
    )

    if data:

        print(
            f"Loaded {len(data)} real "
            f"events from SQLite."
        )

        return (
            data,
            "sqlite"
        )

    # ========================================================
    # 2. JSON
    # ========================================================

    data = load_from_json(
        json_path
    )

    if data:

        print(
            f"Loaded {len(data)} steps "
            f"from JSON."
        )

        return (
            data,
            "json"
        )

    # ========================================================
    # 3. DEMO
    # ========================================================

    print(
        "No trace found. Using demo data."
    )

    return (
        copy.deepcopy(
            DEMO_STEPS
        ),
        "demo"
    )