import copy
import json
import os
import sqlite3


# ============================================================
# DEMO DATA
# ============================================================

DEMO_STEPS = {
    "step1": {
        "code": "# Step 1: Initialize values\nx = 5\ny = 10\ntotal = 0",
        "vars": "x = 5\ny = 10\ntotal = 0",
        "event": "System initialized variables.",
        "line_number": 1,
    },
    "step2": {
        "code": "# Step 2: Add values together\nx = 5\ny = 10\ntotal = x + y",
        "vars": "x = 5\ny = 10\ntotal = 15",
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
        return "\n".join(
            f"{key} = {value}"
            for key, value in vars_data.items()
        )

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
# SOURCE CODE READER
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
        except (TypeError, ValueError):
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

    except (
        OSError,
        UnicodeError
    ):
        return "", 1


# ============================================================
# REAL PYCHRONICLE SQLITE LOADER
# ============================================================

def _load_events_table(
    cursor,
    tables,
    columns
):
    """
    Load the real PyChronicle events table.

    Returns PyChronicle step dictionary or None.
    """

    if "events" not in tables:
        return None

    # --------------------------------------------------------
    # Find latest completed session
    # --------------------------------------------------------

    session_id = None

    if (
        "sessions" in tables
        and "session_id" in columns
    ):

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
                session_id = row[0]

        except sqlite3.Error:
            session_id = None

    # --------------------------------------------------------
    # Safely determine available columns
    # --------------------------------------------------------

    def col(name):
        if name in columns:
            return name

        return f"NULL AS {name}"

    query = f"""
        SELECT
            {col("id")},
            {col("event")},
            {col("function")},
            {col("file")},
            {col("line")},
            {col("variables")},
            {col("var_diff")},
            {col("timestamp")}
        FROM events
    """

    params = ()

    if (
        session_id is not None
        and "session_id" in columns
    ):

        query += """
            WHERE session_id = ?
            ORDER BY id ASC
        """

        params = (session_id,)

    else:

        query += """
            ORDER BY id ASC
        """

    try:

        cursor.execute(
            query,
            params
        )

        rows = cursor.fetchall()

    except sqlite3.Error:
        return None

    if not rows:
        return None

    steps = {}

    # --------------------------------------------------------
    # Convert real events into UI steps
    # --------------------------------------------------------

    for index, row in enumerate(
        rows,
        start=1
    ):

        (
            event_id,
            event,
            function,
            file_path,
            line_number,
            variables,
            var_diff,
            timestamp,
        ) = row

        # ----------------------------------------------------
        # Variables
        # ----------------------------------------------------

        parsed_vars = variables

        if isinstance(
            variables,
            str
        ):

            try:

                parsed_vars = json.loads(
                    variables
                )

            except (
                json.JSONDecodeError,
                TypeError
            ):
                pass

        vars_text = format_vars(
            parsed_vars
        )

        # ----------------------------------------------------
        # Event information
        # ----------------------------------------------------

        event_name = (
            event
            or "unknown"
        )

        function_name = (
            function
            or "unknown"
        )

        line_value = (
            line_number
            or 1
        )

        filename = (
            os.path.basename(file_path)
            if file_path
            else "unknown"
        )

        event_text = (
            f"Event: {event_name}\n"
            f"Function: {function_name}\n"
            f"File: {filename}\n"
            f"Line: {line_value}"
        )

        if var_diff:
            event_text += (
                f"\nVariable changes: {var_diff}"
            )

        # ----------------------------------------------------
        # Source code
        # ----------------------------------------------------

        code_text, relative_line = (
            _source_code(
                file_path,
                line_value
            )
        )

        # ----------------------------------------------------
        # Fallback code
        # ----------------------------------------------------

        if not code_text:

            code_text = (
                f"# Event {event_id}\n"
                f"# Function: {function_name}\n"
                f"# Line: {line_value}"
            )

            relative_line = 1

        # ----------------------------------------------------
        # Store step
        # ----------------------------------------------------

        steps[
            f"step{index}"
        ] = {
            "code": code_text,
            "vars": vars_text,
            "event": event_text,
            "line_number": relative_line,
            "source_line": line_value,
            "function": function,
            "file": file_path,
            "event_id": event_id,
            "session_id": session_id,
            "var_diff": var_diff,
            "timestamp": timestamp,
        }

    return steps


# ============================================================
# TEST / SIMPLE SQLITE LOADER
# ============================================================

def _load_execution_steps(
    cursor,
    tables
):
    """
    Load the simple execution_steps schema used by tests.

    Schema:

        execution_steps(
            id,
            step_id,
            code,
            vars,
            event
        )

    IMPORTANT:
    Returns exactly the structure expected by the unit tests.
    """

    if "execution_steps" not in tables:
        return None

    try:

        cursor.execute(
            """
            SELECT
                step_id,
                code,
                vars,
                event
            FROM execution_steps
            ORDER BY id ASC
            """
        )

        rows = cursor.fetchall()

    except sqlite3.Error:
        return None

    if not rows:
        return None

    steps = {}

    for (
        step_id,
        code,
        vars_text,
        event,
    ) in rows:

        steps[step_id] = {
            "code": code,
            "vars": vars_text,
            "event": event,
        }

    return steps


# ============================================================
# SQLITE LOADER
# ============================================================

def load_from_sqlite(
    db_path="pychronicle.db"
):
    """
    Load execution data from SQLite.

    Supports BOTH:

    1. Real PyChronicle database:
       sessions + events

    2. Simple test database:
       execution_steps

    Returns:
        dict of steps
        or None
    """

    if not db_path:
        return None

    if not os.path.exists(db_path):
        return None

    conn = None

    try:

        conn = sqlite3.connect(
            db_path
        )

        cursor = conn.cursor()

        # ----------------------------------------------------
        # Find tables
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # SIMPLE TEST DATABASE
        # ----------------------------------------------------

        if "execution_steps" in tables:

            result = _load_execution_steps(
                cursor,
                tables
            )

            if result:
                return result

        # ----------------------------------------------------
        # REAL PYCHRONICLE DATABASE
        # ----------------------------------------------------

        if "events" in tables:

            cursor.execute(
                "PRAGMA table_info(events)"
            )

            columns = {
                row[1]
                for row in cursor.fetchall()
            }

            result = _load_events_table(
                cursor,
                tables,
                columns
            )

            if result:
                return result

        # ----------------------------------------------------
        # No supported schema
        # ----------------------------------------------------

        return None

    except sqlite3.Error as exc:

        print(
            f"SQLite loading error: {exc}"
        )

        return None

    finally:

        if conn is not None:
            conn.close()


# ============================================================
# MAIN DATA LOADER
# ============================================================

def load_tracer_data(
    json_path="trace_output.json",
    db_path="pychronicle.db"
):
    """
    Load tracer data using the required priority:

        JSON
          ↓
        SQLite
          ↓
        Demo

    This priority is required by the project tests.
    """

    # ========================================================
    # 1. JSON FIRST
    # ========================================================

    data = load_from_json(
        json_path
    )

    if data:

        print(
            f"Loaded {len(data)} steps from JSON."
        )

        return (
            data,
            "json"
        )

    # ========================================================
    # 2. SQLITE SECOND
    # ========================================================

    data = load_from_sqlite(
        db_path
    )

    if data:

        print(
            f"Loaded {len(data)} real events from SQLite."
        )

        return (
            data,
            "sqlite"
        )

    # ========================================================
    # 3. DEMO LAST
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