"""
PyChronicle Tracer — records Python execution with session tracking,
variable diffs and AST static analysis.

Usage:
    python tracer.py                    # Traces the built-in demo
    python tracer.py <script.py>        # Traces a target script
    python tracer.py <script.py> -v     # ... and prints every event

Environment:
    PYCHRONICLE_DB       override the database path
    PYCHRONICLE_SESSION  override the session name
    PYCHRONICLE_VERBOSE  set to 1 to print every event

The Tracer class is importable, so callers (for example tools/seed_database.py)
can record many sessions in one process instead of paying process-startup cost
per session.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_db_path          # noqa: E402
from database import Database           # noqa: E402

try:
    from parser import parse_source     # noqa: E402
except ImportError:                     # AST module optional
    parse_source = None


# ---------------------------------------------------------------------------
# User-code detection
# ---------------------------------------------------------------------------
# sys.settrace is process-wide, so without filtering the timeline fills up
# with interpreter internals triggered by things like print() — noise that
# buries the real trace steps.

_STDLIB_DIRS = tuple(
    os.path.normcase(os.path.abspath(p))
    for p in {sys.prefix, sys.base_prefix, os.path.dirname(os.__file__)}
    if p
)


def is_user_code(file_name):
    """True if this frame belongs to the traced program, not the runtime."""
    if not file_name or file_name.startswith("<"):
        return False          # <frozen ...>, <string>, <stdin>
    path = os.path.normcase(os.path.abspath(file_name))
    if "site-packages" in path or "dist-packages" in path:
        return False
    return not path.startswith(_STDLIB_DIRS)


# ---------------------------------------------------------------------------
# Variable snapshots
# ---------------------------------------------------------------------------
# Snapshots are stored as JSON rather than str(dict) so both UIs can read
# them: the integrated UI calls json.loads(), and the diff engine decodes
# JSON before falling back to literal_eval.
#
# Large containers are summarised rather than dumped in full. Without this a
# single frame holding a few hundred records writes hundreds of KB per row,
# and a 10,000-event database balloons into hundreds of megabytes.

# These bounds decide the on-disk cost of every event row, so they are
# tunable: bulk seeding a very large history can trade snapshot detail for
# file size without touching the code.
#
#   PYCHRONICLE_MAX_STR    characters kept per string value   (default 200)
#   PYCHRONICLE_MAX_ITEMS  items kept per list/dict           (default 8)
#   PYCHRONICLE_MAX_DEPTH  nesting levels kept                (default 3)
MAX_STRING_LENGTH = int(os.environ.get("PYCHRONICLE_MAX_STR", "200"))
MAX_CONTAINER_ITEMS = int(os.environ.get("PYCHRONICLE_MAX_ITEMS", "8"))
MAX_DEPTH = int(os.environ.get("PYCHRONICLE_MAX_DEPTH", "3"))


def to_storable(value, depth=0):
    """Convert one local variable into a compact JSON-safe form."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            trimmed = value[:MAX_STRING_LENGTH]
            return f"{trimmed}...<+{len(value) - MAX_STRING_LENGTH} chars>"
        return value

    if depth >= MAX_DEPTH:
        return f"<{type(value).__name__}>"

    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        if len(items) > MAX_CONTAINER_ITEMS:
            return {
                "__summary__": type(value).__name__,
                "len": len(items),
                "head": [to_storable(i, depth + 1) for i in items[:MAX_CONTAINER_ITEMS]],
            }
        return [to_storable(item, depth + 1) for item in items]

    if isinstance(value, dict):
        if len(value) > MAX_CONTAINER_ITEMS:
            keys = list(value)[:MAX_CONTAINER_ITEMS]
            return {
                "__summary__": "dict",
                "len": len(value),
                "head": {str(k): to_storable(value[k], depth + 1) for k in keys},
            }
        return {str(k): to_storable(v, depth + 1) for k, v in value.items()}

    text = repr(value)
    if len(text) > MAX_STRING_LENGTH:
        text = text[:MAX_STRING_LENGTH] + "..."
    return text


def snapshot_locals(frame_locals):
    """Build the JSON-safe variable snapshot for one frame."""
    snapshot = {}
    for name, value in frame_locals.items():
        if name.startswith("__"):
            continue
        try:
            snapshot[name] = to_storable(value)
        except Exception:
            snapshot[name] = f"<unrepresentable {type(value).__name__}>"
    return snapshot


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------

class Tracer:
    """Records execution events into the shared PyChronicle database.

    One Tracer instance owns one database connection and can record any
    number of sessions:

        tracer = Tracer()
        tracer.trace_file("examples/invoice_service.py")
        tracer.trace_callable(my_function, session_name="unit run")
        tracer.close()
    """

    # Frames belonging to the tracer's own plumbing are never recorded.
    _OWN_FRAMES = frozenset({
        "_trace", "start", "stop", "trace_file", "trace_callable",
        "close", "_begin_session", "_end_session",
    })

    def __init__(self, db_path=None, verbose=False, store_ast=True):
        self.db_path = db_path or get_db_path()
        self.db = Database(self.db_path)
        self.db.create_table()
        self.verbose = verbose
        self.store_ast = store_ast and parse_source is not None

        self.session_id = None
        self.trace_log = []
        self._prev_vars = {}          # (function, file) -> last snapshot
        self._event_count = 0

    # -- session lifecycle ------------------------------------------------

    def _begin_session(self, name, script_file=None):
        self.session_id = self.db.create_session(name=name, script_file=script_file)
        self.trace_log = []
        self._prev_vars = {}
        self._event_count = 0
        self.db.begin_batch()
        return self.session_id

    def _end_session(self):
        # Flush buffered events before closing the session so its recorded
        # event count reflects rows that actually exist.
        self.db.end_batch()
        if self.session_id is not None:
            self.db.end_session(self.session_id)
        return self.session_id

    # -- tracing ----------------------------------------------------------

    def _trace(self, frame, event, arg):
        function_name = frame.f_code.co_name
        file_name = frame.f_code.co_filename
        print("=" * 80)
        print("FUNCTION :", function_name)
        print("FILE :", file_name)

        if function_name in self._OWN_FRAMES or not is_user_code(file_name):
            return None

        line_number = frame.f_lineno
        local_vars = snapshot_locals(frame.f_locals)

        scope_key = (function_name, file_name)
        var_diff = Database.compute_var_diff(self._prev_vars.get(scope_key), local_vars)
        self._prev_vars[scope_key] = dict(local_vars)

        record = {
            "event": event,
            "function": function_name,
            "file": file_name,
            "line": line_number,
            "variables": local_vars,
            "var_diff": var_diff,
        }
        self.trace_log.append(record)
        self._event_count += 1

        self.db.insert_event_with_diff(
            event=event,
            function=function_name,
            file=file_name,
            line=line_number,
            variables=json.dumps(local_vars),
            var_diff=var_diff,
            session_id=self.session_id,
        )

        if self.verbose:
            print("=" * 50)
            print(f"[{event}] {function_name}() @ "
                  f"{os.path.basename(file_name)}:{line_number}")
            diff_display = Database.format_diff_display(var_diff)
            if diff_display != "No changes":
                print(f"  Changes:\n{diff_display}")

        return self._trace

    def start(self):
        sys.settrace(self._trace)

    def stop(self):
        sys.settrace(None)

    def parse_and_store_ast(self, file_path):
        """Store the static structure of a file before it is executed."""
        if not self.store_ast:
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                source = handle.read()
            _, summary = parse_source(source, file_name=file_path)
            self.db.insert_ast_summary(file_path, summary)
            return summary
        except (OSError, SyntaxError) as exc:
            print(f"PyChronicle: AST parse skipped for {file_path} ({exc})")
            return None

    def trace_file(self, file_path, session_name=None):
        """Parse (AST) and execute (runtime trace) a Python script.

        Returns (session_id, event_count).
        """
        file_path = os.path.abspath(file_path)
        name = session_name or f"Trace: {os.path.basename(file_path)}"

        summary = self.parse_and_store_ast(file_path)
        if summary is not None and self.verbose:
            print(f"PyChronicle: AST stored — {len(summary['functions'])} functions, "
                  f"{len(summary['classes'])} classes, "
                  f"{len(summary['imports'])} imports")

        with open(file_path, "r", encoding="utf-8") as handle:
            code = compile(handle.read(), file_path, "exec")

        self._begin_session(name, script_file=file_path)
        script_globals = {"__name__": "__main__", "__file__": file_path}
        try:
            self.start()
            exec(code, script_globals)
        finally:
            # Always stop tracing and flush, even if the traced script raises,
            # otherwise buffered events are lost and the UI shows nothing.
            self.stop()
            self._end_session()

        return self.session_id, self._event_count

    def trace_callable(self, func, *func_args, session_name=None, **func_kwargs):
        """Run func(*args, **kwargs) under trace. Returns (session_id, count)."""
        name = session_name or f"Trace: {getattr(func, '__name__', 'callable')}()"
        self._begin_session(name, script_file=getattr(func, "__module__", None))
        try:
            self.start()
            func(*func_args, **func_kwargs)
        finally:
            self.stop()
            self._end_session()
        return self.session_id, self._event_count

    def close(self):
        self.db.close()


# ---------------------------------------------------------------------------
# Built-in demo (used when no script is given)
# ---------------------------------------------------------------------------

def add(a, b):
    return a + b


def multiply(a, b):
    result = a * b
    return result


def demo():
    x = 10
    y = 20
    z = add(x, y)
    w = multiply(x, y)
    print(f"Result: add={z}, multiply={w}")
    return z, w


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    verbose = os.environ.get("PYCHRONICLE_VERBOSE", "0") == "1"
    if "-v" in argv or "--verbose" in argv:
        verbose = True
        argv = [a for a in argv if a not in ("-v", "--verbose")]

    target_script = argv[0] if argv else None

    tracer = Tracer(verbose=verbose)
    print(f"PyChronicle: database -> {tracer.db_path}")

    session_name = os.environ.get("PYCHRONICLE_SESSION")

    if target_script:
        print(f"PyChronicle: tracing {target_script}")
        session_id, count = tracer.trace_file(target_script,
                                              session_name=session_name)
    else:
        print("PyChronicle: running os.path.basename(file_path)")
        session_id, count = tracer.trace_callable(
            demo, session_name=session_name or "os.path.basename(file_path)"
        )

    stored = tracer.db.count_events_in_session(session_id)
    by_type = tracer.db.get_session_event_types(session_id)
    changed = sum(1 for r in tracer.trace_log
                  if not Database.diff_is_empty(r["var_diff"]))

    print("\n" + "=" * 50)
    print(f"Session #{session_id} complete — {count} events traced, "
          f"{stored} rows stored in {os.path.basename(tracer.db_path)}")
    print(f"  event types       : {by_type}")
    print(f"  steps with changes: {changed}")
    print("=" * 50)

    # The per-event change list is only readable for short traces.
    if verbose:
        print("\nVariable Change Summary:")
        print("-" * 40)
        for record in tracer.trace_log:
            diff = record["var_diff"]
            if not Database.diff_is_empty(diff):
                print(f"  [{record['event']}] {record['function']}() "
                      f"line {record['line']}:")
                print(f"    {Database.format_diff_display(diff)}")

    tracer.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
