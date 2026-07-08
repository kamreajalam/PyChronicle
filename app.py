from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem

class PyChronicleApp(App):
    """A real-world multi-panel Terminal UI layout for PyChronicle."""
    
    BINDINGS = [("d", "toggle_dark", "Toggle Dark Mode"), ("q", "quit", "Quit")]

    CSS = """
    #sidebar {
        width: 35;
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
    #main-content {
        padding: 2;
    }
    #panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            
            with Vertical(id="sidebar"):
                yield Static(" LOG TIMELINE ", id="sidebar-title")
                yield ListView(
                    ListItem(Static("Step 01: Initialized database")),
                    ListItem(Static("Step 02: Connected to SQLite")),
                    ListItem(Static("Step 03: Executed query batch")),
                    ListItem(Static("Step 04: Cache updated (Success)")),
                    id="log-list"
                )
            
        
            with Vertical(id="main-content"):
                yield Static(" MAIN PANEL ", id="panel-title")
                yield Static(
                    "Welcome to PyChronicle UI!\n\n"
                    "Select a history log checkpoint from the sidebar to inspect execution steps, local state modifications, and core variable tracking indices.", 
                    id="welcome-text"
                )
                
        yield Footer()

    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()