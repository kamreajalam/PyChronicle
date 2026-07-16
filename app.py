import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "tracer"))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem
from rich.syntax import Syntax
from database import Database


class PyChronicleApp(App):
    """PyChronicle UI - displays real traced events from the SQLite database."""

    BINDINGS = [("d", "toggle_dark", "Toggle Dark Mode"), ("q", "quit", "Quit")]

    CSS = """
    #sidebar-box {
        width: 40;
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
        height: 1fr;
        background: $background;
        padding: 1 2;
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
        self.events = self.db.get_all_events()

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(" TRACE TIMELINE ", id="sidebar-title")

                # Build list items from real database events
                items = []
                for event in self.events:
                    event_id = event[0]
                    event_type = event[1]
                    func_name = event[2]
                    line_num = event[4]
                    label = f"[{event_type}] {func_name}() line {line_num}"
                    items.append(
                        ListItem(Static(label), id=f"event_{event_id}")
                    )

                yield ListView(*items, id="log-list")

                # Show stats at bottom of sidebar
                count = len(self.events)
                functions = self.db.get_unique_functions()
                yield Static(
                    f" {count} events | {len(functions)} functions ",
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
                    yield Static(" VARIABLE INSPECTOR ", id="code-title")
                    yield Static("No variables tracked.", id="var-display")

        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Shows event details when a trace event is selected."""
        if event.item and event.item.id:
            # Extract event ID from the item id (format: "event_19")
            event_id = int(event.item.id.replace("event_", ""))
            db_event = self.db.get_event_by_id(event_id)

            if db_event:
                # Build code display showing trace info
                event_type = db_event[1]
                func_name = db_event[2]
                file_name = db_event[3]
                line_num = db_event[4]
                timestamp = db_event[6]

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

                # Show variables
                variables = db_event[5]
                if variables and variables != "{}":
                    var_display = f"Variables at this point:\n\n{variables}"
                else:
                    var_display = "No variables at this point."

                self.query_one("#var-display", Static).update(var_display)

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
