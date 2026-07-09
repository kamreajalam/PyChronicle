from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem
from rich.syntax import Syntax

class PyChronicleApp(App):
    """PyChronicle UI with fully dynamic sidebar log-to-panel state tracking."""
    
    BINDINGS = [("d", "toggle_dark", "Toggle Dark Mode"), ("q", "quit", "Quit")]

    CSS = """
    #sidebar-box {
        width: 32;
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
    """

    CODE_DATA = {
        "step1": "import sqlite3\n\ndef init_db():\n    conn = sqlite3.connect('chronicle.db')\n    print('Database Initialized')",
        "step2": "def connect_db():\n    db = sqlite3.connect('chronicle.db')\n    return db",
        "step3": "def run_query(db):\n    cursor = db.cursor()\n    cursor.execute('INSERT INTO logs VALUES(1, \"Active\")')\n    db.commit()"
    }

    VARIABLE_DATA = {
        "step1": "db_status = 'INITIALIZING'\nactive_threads = 0",
        "step2": "db_status = 'CONNECTED'\nactive_threads = 1",
        "step3": "db_status = 'EXECUTING_QUERY'\nactive_threads = 1\nrows_inserted = 1"
    }

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(" LOG TIMELINE ", id="sidebar-title")
                yield ListView(
                    ListItem(Static("Step 01: Initialized database"), id="step1"),
                    ListItem(Static("Step 02: Connected to SQLite"), id="step2"),
                    ListItem(Static("Step 03: Executed query batch"), id="step3"),
                    id="log-list"
                )
            
            with Vertical(id="main-workspace"):
                with Vertical(id="code-viewer-panel"):
                    yield Static(" SOURCE CODE VIEWER ", id="code-title")
                    yield Static("Select a log step to view execution path...", id="code-display")
                
                with Vertical(id="bottom-inspector-box"):
                    yield Static(" VARIABLE INSPECTOR ", id="code-title")
                
                    yield Static("No variables tracked.", id="var-display")
                    
        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Triggers automatically every time you select a new step in the sidebar."""
        if event.item and event.item.id:
            raw_code = self.CODE_DATA.get(event.item.id, "No source trace.")
            new_vars = self.VARIABLE_DATA.get(event.item.id, "No variable trace.")
            
            colored_code = Syntax(raw_code, "python", theme="monokai", line_numbers=True)
            
            self.query_one("#code-display", Static).update(colored_code)
            self.query_one("#var-display", Static).update(new_vars)

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()