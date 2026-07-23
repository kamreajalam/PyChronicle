import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "tracer"))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem, Select
from rich.syntax import Syntax
from rich.text import Text
from database import Database


class PyChronicleApp(App):
    """PyChronicle UI - displays traced events with session support and variable diffs."""

    BINDINGS = [
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("q", "quit", "Quit"),
        ("n", "next_session", "Next Session"),
        ("p", "prev_session", "Prev Session"),
    ]

    CSS = """
    #session-bar {
        height: 3;
        background: $primary-background;
        padding: 0 2;
        border-bottom: solid $accent;
    }
    #session-label {
        text-style: bold;
        color: $accent;
        padding: 1 1;
    }
    #sidebar-box {
        width: 44;
        background: $panel;
        border-right: vkey $accent;
        padding: 1;
    }
    #sidebar-title {
        text-align: center;
        background: $accent;
        color: $text;
        margin-bottom: 1;
        text-style: bold;
    }
    #main-workspace {
        background: $surface;
    }
    #code-viewer-panel {
        height: 3fr;
        padding: 1 2;
        border-bottom: solid $accent;
    }
    #code-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #code-display {
        background: $boost;
        padding: 1;
    }
    #bottom-inspector-box {
        height: 2fr;
        background: $background;
        padding: 1 2;
    }
    #var-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #var-display {
        background: $boost;
        padding: 1;
    }
    #stats-display {
        text-align: center;
        background: $accent;
        color: $text;
        margin-top: 1;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        db_path = os.path.join(os.path.dirname(__file__), "src", "tracer", "pychronicle.db")
        self.db = Database(db_path)
        self.db.create_table()

        # Load sessions
        self.sessions = self.db.get_all_sessions()
        self.current_session_idx = 0
        self.events = []

        if self.sessions:
            session_id = self.sessions[0][0]
            self.events = self.db.get_events_by_session(session_id)

        # Fallback: if no sessions exist, load all events (legacy support)
        if not self.events:
            self.events = self.db.get_all_events()

    def _get_current_session(self):
        """Get the currently selected session tuple."""
        if self.sessions and 0 <= self.current_session_idx < len(self.sessions):
            return self.sessions[self.current_session_idx]
        return None

    def compose(self) -> ComposeResult:
        yield Header()

        # Session bar at top
        session = self._get_current_session()
        if session:
            session_text = (
                f" Session: {session[1]} | "
                f"Script: {session[2] or 'demo'} | "
                f"Events: {session[5]} | "
                f"Status: {session[6]} | "
                f"[N/P to switch]"
            )
        else:
            session_text = " No sessions found — run tracer.py to create one"

        with Vertical(id="session-bar"):
            yield Static(session_text, id="session-label")

        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(" TRACE TIMELINE ", id="sidebar-title")

                # Build list items from events
                items = []
                for event in self.events:
                    event_id = event[0]
                    event_type = event[2]   # event column
                    func_name = event[3]    # function column
                    line_num = event[5]     # line column
                    var_diff = event[7]     # var_diff column

                    # Mark events that have variable changes with a dot
                    has_diff = var_diff and not Database.diff_is_empty(var_diff)
                    marker = "*" if has_diff else " "
                    label = f"{marker}[{event_type}] {func_name}() line {line_num}"
                    items.append(
                        ListItem(Static(label), id=f"event_{event_id}")
                    )

                yield ListView(*items, id="log-list")

                # Stats
                count = len(self.events)
                functions = set(e[3] for e in self.events)
                diff_count = sum(
                    1 for e in self.events
                    if e[7] and not Database.diff_is_empty(e[7])
                )
                yield Static(
                    f" {count} events | {len(functions)} funcs | {diff_count} changes ",
                    id="stats-display"
                )

            with Vertical(id="main-workspace"):
                with Vertical(id="code-viewer-panel"):
                    yield Static(" SOURCE CODE VIEWER ", id="code-title")
                    yield Static(
                        "Select a trace event to view details...",
                        id="code-display"
                    )

                with Vertical(id="bottom-inspector-box"):
                    yield Static(" VARIABLE DIFF INSPECTOR ", id="var-title")
                    yield Static(
                        "Select an event to see what changed.",
                        id="var-display"
                    )

        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Shows event details and variable diff when a trace event is selected."""
        if event.item and event.item.id:
            event_id = int(event.item.id.replace("event_", ""))
            db_event = self.db.get_event_by_id(event_id)

            if db_event:
                # Column mapping with session_id:
                # (id, session_id, event, function, file, line, variables, var_diff, timestamp)
                event_type = db_event[2]
                func_name = db_event[3]
                file_name = db_event[4]
                line_num = db_event[5]
                variables = db_event[6]
                var_diff = db_event[7]
                timestamp = db_event[8]

                # Build code display
                code_text = (
                    f"# Event: {event_type}\n"
                    f"# Function: {func_name}()\n"
                    f"# File: {file_name}\n"
                    f"# Line: {line_num}\n"
                    f"# Time: {timestamp}\n"
                    f"\n"
                    f"# --- Trace Point ---\n"
                    f"def {func_name}(...):\n"
                    f"    # >> line {line_num} ({event_type})\n"
                    f"    pass"
                )

                colored_code = Syntax(
                    code_text, "python", theme="monokai", line_numbers=True
                )
                self.query_one("#code-display", Static).update(colored_code)

                # Variable diff display
                var_text = ""

                # Show the diff (what changed)
                if var_diff and not Database.diff_is_empty(var_diff):
                    diff_display = Database.format_diff_display(var_diff)
                    var_text += "What changed at this step:\n"
                    var_text += "-" * 35 + "\n"
                    var_text += diff_display + "\n\n"
                else:
                    var_text += "No variable changes at this step.\n\n"

                # Show full state
                if variables and variables != "{}":
                    var_text += "Full variable state:\n"
                    var_text += "-" * 35 + "\n"
                    var_text += variables
                else:
                    var_text += "No variables in scope."

                self.query_one("#var-display", Static).update(var_text)

    def action_next_session(self) -> None:
        """Switch to the next session."""
        if self.sessions and self.current_session_idx < len(self.sessions) - 1:
            self.current_session_idx += 1
            self._reload_session()

    def action_prev_session(self) -> None:
        """Switch to the previous session."""
        if self.sessions and self.current_session_idx > 0:
            self.current_session_idx -= 1
            self._reload_session()

    def _reload_session(self) -> None:
        """Reload the UI for the current session."""
        # The simplest approach: restart the app view
        # For a full implementation you'd replace the ListView contents
        session = self._get_current_session()
        if session:
            session_text = (
                f" Session: {session[1]} | "
                f"Script: {session[2] or 'demo'} | "
                f"Events: {session[5]} | "
                f"Status: {session[6]} | "
                f"[N/P to switch]"
            )
            self.query_one("#session-label", Static).update(session_text)

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-light" if self.theme == "textual-dark" else "textual-dark"
        )

    def on_unmount(self) -> None:
        """Close database when app exits."""
        self.db.close()


if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()
