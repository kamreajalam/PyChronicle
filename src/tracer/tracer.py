"""
PyChronicle Tracer — traces Python execution with session tracking
and variable diff storage.

Usage:
    python tracer.py                 # Traces the built-in demo
    python tracer.py <script.py>     # Traces a target script
"""
from database import Database
import sys
import os

# Create database and ensure schema
db = Database()
db.create_table()

# Determine what we're tracing
target_script = None
if len(sys.argv) > 1:
    target_script = sys.argv[1]

# Start a session
session_name = f"Trace: {os.path.basename(target_script)}" if target_script else "Demo trace"
session_id = db.create_session(name=session_name, script_file=target_script)

# Variable diff tracking — keeps the last known state per function scope
_prev_vars = {}  # key: (function_name, file_name) -> dict of variables
trace_log = []


def trace(frame, event, arg):
    function_name = frame.f_code.co_name
    file_name = frame.f_code.co_filename
    line_number = frame.f_lineno
    local_vars = frame.f_locals.copy()

    # Compute variable diff
    scope_key = (function_name, file_name)
    prev = _prev_vars.get(scope_key)
    var_diff = Database.compute_var_diff(prev, local_vars)
    _prev_vars[scope_key] = local_vars.copy()

    # Save in memory
    record = {
        "event": event,
        "function": function_name,
        "file": file_name,
        "line": line_number,
        "variables": local_vars,
        "var_diff": var_diff
    }
    trace_log.append(record)

    # Save in SQLite with diff
    db.insert_event_with_diff(
        event=event,
        function=function_name,
        file=file_name,
        line=line_number,
        variables=str(local_vars),
        var_diff=var_diff,
        session_id=session_id
    )

    # Print with diff highlights
    print("=" * 50)
    print(f"[{event}] {function_name}() @ {os.path.basename(file_name)}:{line_number}")
    diff_display = Database.format_diff_display(var_diff)
    if diff_display != "No changes":
        print(f"  Changes:\n{diff_display}")

    return trace


# --- Demo functions (used when no script is provided) ---

def add(a, b):
    return a + b


def multiply(a, b):
    result = a * b
    return result


def main():
    x = 10
    y = 20
    z = add(x, y)
    w = multiply(x, y)
    print(f"Result: add={z}, multiply={w}")


# --- Execute ---

if target_script:
    # Trace an external script
    print(f"PyChronicle: Tracing {target_script} (session #{session_id})")
    db.begin_batch()
    sys.settrace(trace)

    # Execute the target script
    script_globals = {"__name__": "__main__", "__file__": target_script}
    with open(target_script, "r") as f:
        code = compile(f.read(), target_script, "exec")
        exec(code, script_globals)

    sys.settrace(None)
    db.end_batch()
else:
    # Run built-in demo
    print(f"PyChronicle: Running demo trace (session #{session_id})")
    db.begin_batch()
    sys.settrace(trace)
    main()
    sys.settrace(None)
    db.end_batch()

# End the session
db.end_session(session_id)

print("\n" + "=" * 50)
print(f"Session #{session_id} complete — {len(trace_log)} events recorded")
print("=" * 50)

# Show summary of variable changes
print("\nVariable Change Summary:")
print("-" * 40)
for record in trace_log:
    diff = record["var_diff"]
    if not Database.diff_is_empty(diff):
        print(f"  [{record['event']}] {record['function']}() line {record['line']}:")
        print(f"    {Database.format_diff_display(diff)}")

db.close()
