import json
import sqlite3
import os
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem
from rich.syntax import Syntax

class PyChronicleApp(App):
    """
    A rich, interactive CLI dashboard allowing developers to visually 
    scrub back and forth through execution history.
    """
    
    BINDINGS = [
        ("d", "toggle_dark", "Toggle Dark Theme"), 
        ("q", "quit", "Quit Application")
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

    def __init__(self):
        super().__init__()
        self.steps_data = self.load_tracer_data()

    def load_tracer_data(self) -> dict:
        """
        Loads execution state from trace_output.json or pychronicle.db if available.
        Falls back to demo steps if no file is found.
        """
        # 1. Try loading from trace_output.json
        if os.path.exists("trace_output.json"):
            try:
                with open("trace_output.json", "r") as f:
                    data = json.load(f)
                    if data:
                        return data
            except Exception as e:
                print(f"Error reading JSON trace: {e}")

        # 2. Try loading from SQLite database
        if os.path.exists("pychronicle.db"):
            try:
                conn = sqlite3.connect("pychronicle.db")
                cursor = conn.cursor()
                cursor.execute("SELECT step_id, code, vars, event FROM execution_steps ORDER BY id ASC")
                rows = cursor.fetchall()
                conn.close()
                if rows:
                    return {
                        row[0]: {"code": row[1], "vars": row[2], "event": row[3]}
                        for row in rows
                    }
            except Exception as e:
                print(f"Error reading SQLite trace: {e}")

        # 3. Fallback Demo Data if no trace data exists
        return {
            "step1": {
                "code": "# Step 1: Initialize values\nx = 5\ny = 10\ntotal = 0",
                "vars": "x = 5\ny = 10\ntotal = 0",
                "event": "System initialized variables in local scope memory workspace."
            },
            "step2": {
                "code": "# Step 2: Add values together\nx = 5\ny = 10\ntotal = x + y",
                "vars": "x = 5\ny = 10\ntotal = 15",
                "event": "Executed addition operator. Variable 'total' updated to 15."
            }
        }

    def compose(self) -> ComposeResult:
        yield Header()
        
        # Dynamically build timeline items based on loaded tracer data
        list_items = [
            ListItem(Static(f"Step {idx+1:02d}: {step_id}"), id=step_id)
            for idx, step_id in enumerate(self.steps_data.keys())
        ]

        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(" TIMELINE ", id="sidebar-title")
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

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.item.id:
            step_id = event.item.id
            data = self.steps_data.get(step_id, {})
            
            code_text = data.get("code", "")
            vars_text = data.get("vars", "")
            event_text = data.get("event", "")

            # Format dictionary vars into readable string if passed as dict
            if isinstance(vars_text, dict):
                vars_text = "\n".join([f"{k} = {v}" for k, v in vars_text.items()])

            code_text = data.get("code", "")
        vars_text = data.get("vars", "")
        event_text = data.get("event", "")
        
        # Get active line number and create syntax view with line highlighting
        line_no = data.get("line_number", 1)
        syntax_code = Syntax(code_text, "python", theme="monokai", highlight_lines={line_no})
        self.query_one("#code-display", Static).update(syntax_code)
        self.query_one("#var-display", Static).update(vars_text)
        self.query_one("#event-display", Static).update(event_text)

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()