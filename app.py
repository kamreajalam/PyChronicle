from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem

class PyChronicleApp(App):
    """PyChronicle Terminal UI with Sidebar, Code Viewer, and Inspector Panels."""
    
    BINDINGS = [("d", "toggle_dark", "Toggle Dark Mode"), ("q", "quit", "Quit")]

    # Updated CSS to manage the new Code Viewer block layout proportions
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
        text-style: italic;
    }
    #bottom-inspector-box {
        height: 1fr;
        background: $background;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            # Left: Timeline Sidebar Container
            with Vertical(id="sidebar-box"):
                yield Static(" LOG TIMELINE ", id="sidebar-title")
                yield ListView(
                    ListItem(Static("Step 01: Initialized database")),
                    ListItem(Static("Step 02: Connected to SQLite")),
                    ListItem(Static("Step 03: Executed query batch")),
                    id="log-list"
                )
            
            # Right: Main Workspace Container (Splits Vertically into Code + Variables)
            with Vertical(id="main-workspace"):
                
                # Top Right: Code Viewer Panel
                with Vertical(id="code-viewer-panel"):
                    yield Static(" SOURCE CODE VIEWER ", id="code-title")
                    yield Static(
                        "def connect_db():\n"
                        "    db = sqlite3.connect('chronicle.db')\n"
                        "    return db", 
                        id="code-display"
                    )
                
                # Bottom Right: Variable Panel Container
                with Vertical(id="bottom-inspector-box"):
                    yield Static(" VARIABLE INSPECTOR ", id="code-title")
                    yield Static("db_status = 'CONNECTED'\nactive_threads = 1")
                    
        yield Footer()

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()