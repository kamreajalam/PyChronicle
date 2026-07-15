from database import Database
import sys

# Create database
db = Database()
db.create_table()

# Store all trace events
trace_log = []


def trace(frame, event, arg):
    function_name = frame.f_code.co_name
    file_name = frame.f_code.co_filename
    line_number = frame.f_lineno
    local_vars = frame.f_locals.copy()

    # Save in memory
    record = {
        "event": event,
        "function": function_name,
        "file": file_name,
        "line": line_number,
        "variables": local_vars
    }

    trace_log.append(record)

    # Save in SQLite
    db.insert_event(
        event,
        function_name,
        file_name,
        line_number,
        str(local_vars)
    )

    print("=" * 50)
    print(record)

    return trace


def add(a, b):
    return a + b


def main():
    x = 10
    y = 20
    z = add(x, y)
    print("Result:", z)


sys.settrace(trace)
main()
sys.settrace(None)

print("\nCollected Trace Events")
print("=" * 50)

for item in trace_log:
    print(item)

db.close()