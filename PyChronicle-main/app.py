import argparse

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem
from rich.syntax import Syntax

from trace_loader import load_tracer_data, format_vars


class PyChronicleApp(App):
    """
    A rich, interactive CLI dashboard allowing developers to visually
    scrub back and forth through execution history.
    """

    BINDINGS = [
        ("d", "toggle_dark", "Toggle Dark Theme"),
        ("home", "first_step", "First Step"),
        ("end", "last_step", "Last Step"),
        ("q", "quit", "Quit Application"),
    ]

    CSS = """
    #sidebar-box {
        width: 35;
        background: $panel;
        border-right: solid $accent;
        padding: 1;
    }
    #sidebar-title, #event-title, #code-title, #var-title {
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
    #bottom-row {
        height: 2fr;
    }
    #var-panel, #event-log-panel {
        width: 1fr;
        padding: 1 2;
        background: $background;
    }
    #var-panel {
        border-right: solid $accent;
    }
    .display-box {
        background: $boost;
        padding: 1;
        height: 100%;
    }
    """

    def __init__(self, json_path="trace_output.json", db_path="pychronicle.db"):
        super().__init__()
        self.json_path = json_path
        self.db_path = db_path
        self.steps_data, self.data_source = load_tracer_data(json_path, db_path)
        # Preserve insertion order so "first"/"last"/index lookups line up
        # with what's shown in the sidebar timeline.
        self._step_ids = list(self.steps_data.keys())

    def compose(self) -> ComposeResult:
        yield Header()

        # Dynamically build timeline items based on loaded tracer data
        list_items = [
            ListItem(Static(f"Step {idx+1:02d}: {step_id}"), id=step_id)
            for idx, step_id in enumerate(self._step_ids)
        ]

        sidebar_label = " TIMELINE "
        if self.data_source == "demo":
            # Make it obvious in the UI that no real trace was found, rather
            # than silently showing demo data that looks like a real trace.
            sidebar_label = " TIMELINE (demo data) "

        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(sidebar_label, id="sidebar-title")
                yield ListView(*list_items, id="timeline-list")

            with Vertical(id="main-workspace"):
                with Vertical(id="code-viewer-panel"):
                    yield Static(" CODE VIEWER ", id="code-title")
                    yield Static("Use Arrow Keys to select a step...", id="code-display", classes="display-box")

                with Horizontal(id="bottom-row"):
                    with Vertical(id="var-panel"):
                        yield Static(" VARIABLE PANEL ", id="var-title")
                        yield Static("No variables.", id="var-display", classes="display-box")

                    with Vertical(id="event-log-panel"):
                        yield Static(" EVENT LOG ", id="event-title")
                        yield Static("System idle.", id="event-display", classes="display-box")

        yield Footer()

    def _show_step(self, step_id: str) -> None:
        """Render the given step's code/vars/event into the three panels."""
        data = self.steps_data.get(step_id, {})

        code_text = data.get("code", "")
        vars_text = format_vars(data.get("vars", ""))
        event_text = data.get("event", "")

        # Get active line number and create syntax view with line highlighting.
        # Guard against a line number that doesn't exist in this step's code
        # so Syntax never gets an out-of-range highlight target.
        line_count = code_text.count("\n") + 1 if code_text else 0
        line_no = data.get("line_number", 1)
        highlight_lines = {line_no} if 1 <= line_no <= line_count else set()

        syntax_code = Syntax(code_text, "python", theme="monokai", highlight_lines=highlight_lines)

        # Include a "step X of N" indicator so it's clear where you are in
        # the timeline without having to look back at the sidebar.
        if step_id in self._step_ids:
            position = f" (Step {self._step_ids.index(step_id) + 1} of {len(self._step_ids)})"
        else:
            position = ""

        self.query_one("#code-title", Static).update(f" CODE VIEWER{position} ")
        self.query_one("#code-display", Static).update(syntax_code)
        self.query_one("#var-display", Static).update(vars_text or "No variables.")
        self.query_one("#event-display", Static).update(event_text or "System idle.")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.item.id:
            self._show_step(event.item.id)

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

    def action_first_step(self) -> None:
        list_view = self.query_one("#timeline-list", ListView)
        if len(list_view):
            list_view.index = 0

    def action_last_step(self) -> None:
        list_view = self.query_one("#timeline-list", ListView)
        if len(list_view):
            list_view.index = len(list_view) - 1


def parse_args():
    parser = argparse.ArgumentParser(description="PyChronicle - visual execution history scrubber")
    parser.add_argument(
        "--trace", "-t",
        dest="json_path",
        default="trace_output.json",
        help="Path to a JSON trace file (default: trace_output.json)",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="pychronicle.db",
        help="Path to a SQLite trace database, used if --trace is not found (default: pychronicle.db)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = PyChronicleApp(json_path=args.json_path, db_path=args.db_path)
    app.run()
