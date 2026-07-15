from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem
from rich.syntax import Syntax

class PyChronicleApp(App):
    """
    A rich, interactive CLI dashboard allowing developers to visually 
    scrub back and forth through execution history.
    """
    
    # 1. Keyboard Navigation & Theme toggles mapped to Footer bindings
    BINDINGS = [
        ("d", "toggle_dark", "Toggle Dark Theme"), 
        ("q", "quit", "Quit Application")
    ]

    # Clean styling to organize our panels visually
    CSS = """
    #sidebar-box {
        width: 35;
        background: $panel;
        border-right: tall $accent;
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

    # Mock Data to simulate stepping through a program
    STEPS_DATA = {
        "step1": {
            "code": "# Step 1: Initialize values\nx = 5\ny = 10\ntotal = 0",
            "vars": "x = 5\ny = 10\ntotal = 0",
            "event": "System initialized variables in local scope memory workspace."
        },
        "step2": {
            "code": "# Step 2: Add values together\nx = 5\ny = 10\ntotal = x + y",
            "vars": "x = 5\ny = 10\ntotal = 15",
            "event": "Executed addition operator. Variable 'total' updated from 0 to 15."
        },
        "step3": {
            "code": "# Step 3: Mutate x\nx = 20\ny = 10\ntotal = x + y",
            "vars": "x = 20\ny = 10\ntotal = 15",
            "event": "Reassigned global variable 'x' to 20. Warning: 'total' is now stale!"
        }
    }

    def compose(self) -> ComposeResult:
        # 2. Header & Footer
        yield Header()
        
        with Horizontal():
            # 3. Timeline Sidebar (using ListView for easy keyboard navigation)
            with Vertical(id="sidebar-box"):
                yield Static(" TIMELINE ", id="sidebar-title")
                yield ListView(
                    ListItem(Static("Step 01: Setup Variables"), id="step1"),
                    ListItem(Static("Step 02: Calculate Total"), id="step2"),
                    ListItem(Static("Step 03: Update State"), id="step3"),
                    id="timeline-list"
                )
            
            # Main code visual workspace
            with Vertical(id="main-workspace"):
                # 4. Code Viewer
                with Vertical(id="code-viewer-panel"):
                    yield Static(" CODE VIEWER ", id="code-title")
                    yield Static("Use Arrow Keys to select a step...", id="code-display", classes="display-box")
                
                # Bottom Row splitting Variables and Events
                with Horizontal(id="bottom-row"):
                    # 5. Variable Panel
                    with Vertical(id="var-panel"):
                        yield Static(" VARIABLE PANEL ", id="var-title")
                        yield Static("No variables.", id="var-display", classes="display-box")
                    
                    # 6. Event Log Panel
                    with Vertical(id="event-log-panel"):
                        yield Static(" EVENT LOG ", id="event-title")
                        yield Static("System idle.", id="event-display", classes="display-box")
                    
        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """
        Triggers automatically when keyboard arrow keys move selection
        up and down through the timeline steps list.
        """
        if event.item and event.item.id:
            step_id = event.item.id
            data = self.STEPS_DATA.get(step_id, {})
            
            # Format the python code with colorful syntax highlighting
            syntax_code = Syntax(data.get("code", ""), "python", theme="monokai", line_numbers=True)
            
            # Push dynamic updates to all three panels simultaneously!
            self.query_one("#code-display", Static).update(syntax_code)
            self.query_one("#var-display", Static).update(data.get("vars", ""))
            self.query_one("#event-display", Static).update(data.get("event", ""))

    # 7. Dark Theme Toggle action handler
    def action_toggle_dark(self) -> None:
        self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"

if __name__ == "__main__":
    app = PyChronicleApp()
    app.run()