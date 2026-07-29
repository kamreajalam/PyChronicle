"""PyChronicle UI — browse recorded trace sessions in the terminal.

Reads the canonical database (see src/tracer/config.py) that the tracer writes
to, and presents:

  * TRACE TIMELINE     — one paged, filterable list of events per session
  * SOURCE CODE VIEWER — the real traced file, with the recorded line highlighted
  * VARIABLE INSPECTOR — the variable diff for the step, plus the full snapshot

The timeline is paged rather than loaded whole: sessions here run to thousands
of events, and mounting one list widget per event does not scale.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src", "tracer"))

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ListView, ListItem, Input
from rich.syntax import Syntax

from config import get_db_path
from database import Database

# Events per timeline page. Large enough to scroll through comfortably, small
# enough that switching pages is instant.
PAGE_SIZE = 250

# Cycled by the "f" key.
EVENT_TYPE_FILTERS = [None, "call", "line", "return", "exception"]


class PyChronicleApp(App):
    """Terminal UI over the PyChronicle trace database."""

    BINDINGS = [
        ("d", "toggle_dark", "Dark Mode"),
        ("n", "next_session", "Next Session"),
        ("p", "prev_session", "Prev Session"),
        ("right", "next_page", "Next Page"),
        ("left", "prev_page", "Prev Page"),
        ("f", "cycle_filter", "Filter Type"),
        ("r", "reset_filters", "Reset"),
        ("q", "quit", "Quit"),
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
        width: 46;
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
    #search-input {
        margin-bottom: 1;
    }
    #filter-display {
        color: $text-muted;
        margin-bottom: 1;
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

    def __init__(self, db_path=None):
        super().__init__()
        # Shared canonical path — the same file tracer.py writes to.
        self.db_path = db_path or get_db_path()
        self.db = Database(self.db_path)
        self.db.create_table()

        self.sessions = self.db.get_all_sessions()
        self.current_session_idx = 0

        # Filter / paging state
        self.page = 0
        self.filter_index = 0          # into EVENT_TYPE_FILTERS
        self.keyword = ""

        self.total_matching = 0
        self.events = []
        self._load_events()

    # -- data access ------------------------------------------------------

    @property
    def event_type_filter(self):
        return EVENT_TYPE_FILTERS[self.filter_index]

    def _get_current_session(self):
        if self.sessions and 0 <= self.current_session_idx < len(self.sessions):
            return self.sessions[self.current_session_idx]
        return None

    def _load_events(self):
        """Load one page of events for the current session and filters."""
        session = self._get_current_session()
        if not session:
            # Legacy rows with no session at all still deserve to be shown.
            self.events = self.db.get_all_events()[:PAGE_SIZE]
            self.total_matching = self.db.get_event_count()
            return self.events

        session_id = session[0]
        self.total_matching = self.db.count_events_by_session_filtered(
            session_id,
            event_type=self.event_type_filter,
            keyword=self.keyword or None,
        )

        # Clamp the page after a filter change shrinks the result set.
        max_page = max(0, (self.total_matching - 1) // PAGE_SIZE)
        self.page = min(self.page, max_page)

        self.events = self.db.get_events_by_session_filtered(
            session_id,
            event_type=self.event_type_filter,
            keyword=self.keyword or None,
            limit=PAGE_SIZE,
            offset=self.page * PAGE_SIZE,
        )
        return self.events

    # -- rendering helpers ------------------------------------------------

    def _session_text(self):
        session = self._get_current_session()
        if not session:
            return (" No sessions found — run:  python tools/seed_database.py"
                    f"   (db: {os.path.basename(self.db_path)})")

        started = (session[3] or "")[:16].replace("T", " ")
        return (
            f" Session {self.current_session_idx + 1}/{len(self.sessions)}"
            f" · #{session[0]} · {session[1]}"
            f" · started {started}"
            f" · {session[5]} events · {session[6]}"
            "   [n/p session · ←/→ page · f filter · r reset]"
        )

    def _event_label(self, event):
        event_type = event[2]
        func_name = event[3]
        line_num = event[5]
        var_diff = event[7]
        has_diff = var_diff and not Database.diff_is_empty(var_diff)
        marker = "*" if has_diff else " "
        return f"{marker}#{event[0]} [{event_type}] {func_name}() line {line_num}"

    def _build_items(self):
        if not self.events:
            if self.keyword or self.event_type_filter:
                return [ListItem(Static(" (no events match the current filter) "))]
            return [ListItem(Static(" (no events — run the seeder or tracer) "))]
        return [
            ListItem(Static(self._event_label(e)), id=f"event_{e[0]}")
            for e in self.events
        ]

    def _page_count(self):
        return max(1, (self.total_matching + PAGE_SIZE - 1) // PAGE_SIZE)

    def _stats_text(self):
        first = self.page * PAGE_SIZE + 1 if self.events else 0
        last = self.page * PAGE_SIZE + len(self.events)
        functions = {e[3] for e in self.events}
        diff_count = sum(1 for e in self.events
                         if e[7] and not Database.diff_is_empty(e[7]))
        return (f" {first}-{last} of {self.total_matching:,} | "
                f"page {self.page + 1}/{self._page_count()} | "
                f"{len(functions)} funcs | {diff_count} changes ")

    def _filter_text(self):
        active = self.event_type_filter or "all types"
        keyword = f' · search "{self.keyword}"' if self.keyword else ""
        return f" filter: {active}{keyword}"

    # -- layout -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="session-bar"):
            yield Static(self._session_text(), id="session-label")

        with Horizontal():
            with Vertical(id="sidebar-box"):
                yield Static(" TRACE TIMELINE ", id="sidebar-title")
                yield Input(placeholder="search function / variables / file",
                            id="search-input")
                yield Static(self._filter_text(), id="filter-display")
                yield ListView(*self._build_items(), id="log-list")
                yield Static(self._stats_text(), id="stats-display")

            with Vertical(id="main-workspace"):
                with Vertical(id="code-viewer-panel"):
                    yield Static(" SOURCE CODE VIEWER ", id="code-title")
                    yield Static("Select a trace event to view details...",
                                 id="code-display")

                with Vertical(id="bottom-inspector-box"):
                    yield Static(" VARIABLE INSPECTOR ", id="var-title")
                    yield Static("Select an event to see what changed.",
                                 id="var-display")

        yield Footer()

    # -- event detail -----------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Show source and variables for the highlighted trace event."""
        if not (event.item and event.item.id):
            return

        event_id = int(event.item.id.replace("event_", ""))
        db_event = self.db.get_event_by_id(event_id)
        if not db_event:
            return

        row = Database.row_to_dict(db_event)

        self.query_one("#code-title", Static).update(
            f" {row['event'].upper()} · {row['function']}() · "
            f"line {row['line']} · {row['timestamp']} "
        )
        self.query_one("#code-display", Static).update(
            self._render_source(row["file"], row["line"])
        )
        self.query_one("#var-display", Static).update(self._render_variables(row))

    def _render_source(self, file_name, line_num):
        """Show the real traced file with the recorded line highlighted."""
        try:
            with open(file_name, "r", encoding="utf-8") as handle:
                source = handle.read()
        except OSError:
            return Syntax(
                f"# Source file not available:\n# {file_name}",
                "python", theme="monokai",
            )

        total_lines = source.count("\n") + 1
        start = max(1, line_num - 6)
        end = min(total_lines, line_num + 6)
        return Syntax(
            source, "python", theme="monokai", line_numbers=True,
            line_range=(start, end), highlight_lines={line_num},
        )

    def _render_variables(self, row):
        """Diff for this step, then the full variable snapshot."""
        parts = []

        var_diff = row["var_diff"]
        if var_diff and not Database.diff_is_empty(var_diff):
            parts.append("What changed at this step:")
            parts.append("-" * 38)
            parts.append(Database.format_diff_display(var_diff))
        else:
            parts.append("No variable changes at this step.")

        parts.append("")
        variables = Database.parse_variables(row["variables"])
        if variables:
            parts.append("Full variable state:")
            parts.append("-" * 38)
            for name, value in variables.items():
                rendered = repr(value)
                if len(rendered) > 300:
                    rendered = rendered[:300] + "..."
                parts.append(f"  {name} = {rendered}")
        else:
            parts.append("No variables in scope.")

        parts.append("")
        parts.append(f"file: {row['file']}")
        return "\n".join(parts)

    # -- actions ----------------------------------------------------------

    async def refresh_timeline(self) -> None:
        """Reload the timeline, header, stats and filter line.

        ListView.clear() is awaitable: the old rows have to be removed before
        the new ones are mounted, otherwise the two pages collide on widget id.
        """
        self._load_events()

        log_list = self.query_one("#log-list", ListView)
        await log_list.clear()
        await log_list.extend(self._build_items())

        self.query_one("#session-label", Static).update(self._session_text())
        self.query_one("#stats-display", Static).update(self._stats_text())
        self.query_one("#filter-display", Static).update(self._filter_text())

    async def action_next_session(self) -> None:
        if self.sessions and self.current_session_idx < len(self.sessions) - 1:
            self.current_session_idx += 1
            self.page = 0
            await self.refresh_timeline()

    async def action_prev_session(self) -> None:
        if self.sessions and self.current_session_idx > 0:
            self.current_session_idx -= 1
            self.page = 0
            await self.refresh_timeline()

    async def action_next_page(self) -> None:
        if self.page + 1 < self._page_count():
            self.page += 1
            await self.refresh_timeline()

    async def action_prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            await self.refresh_timeline()

    async def action_cycle_filter(self) -> None:
        self.filter_index = (self.filter_index + 1) % len(EVENT_TYPE_FILTERS)
        self.page = 0
        await self.refresh_timeline()

    async def action_reset_filters(self) -> None:
        self.filter_index = 0
        self.keyword = ""
        self.page = 0
        self.query_one("#search-input", Input).value = ""
        await self.refresh_timeline()

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Live keyword filter."""
        if event.input.id == "search-input":
            self.keyword = event.value.strip()
            self.page = 0
            await self.refresh_timeline()

    def action_toggle_dark(self) -> None:
        self.theme = ("textual-light" if self.theme == "textual-dark"
                      else "textual-dark")

    def on_unmount(self) -> None:
        self.db.close()


if __name__ == "__main__":
    PyChronicleApp().run()
