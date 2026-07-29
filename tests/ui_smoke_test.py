"""Headless check that the UI renders real data from the shared database.

Verifies the integration points that matter for the review: the app opens the
same database the tracer writes to, the Trace Timeline is populated, paging and
filtering work, and selecting an event fills both detail panes.

    python tests/ui_smoke_test.py
"""

import asyncio
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src", "tracer"))

from textual.widgets import Input, ListView, Static  # noqa: E402

from app import PAGE_SIZE, PyChronicleApp  # noqa: E402
from config import get_db_path  # noqa: E402
from database import Database  # noqa: E402

failures = []

# The review asks the timeline to show 10,000+ events. Lower this when working
# against a small development database:  PYCHRONICLE_MIN_EVENTS=500
MIN_EVENTS = int(os.environ.get("PYCHRONICLE_MIN_EVENTS", "10000"))


def check(name, condition, detail=""):
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}"
          + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(name)


def static_text(widget):
    """Read the text out of a Static across Textual versions."""
    for attr in ("renderable", "content"):
        if hasattr(widget, attr):
            value = getattr(widget, attr)
            if value is not None:
                return str(value)
    return str(widget.render())


async def run_checks():
    app = PyChronicleApp()

    print("\n1. database wiring")
    print(f"  db path: {app.db_path}")
    check("UI opens the canonical database",
          os.path.abspath(app.db_path) == os.path.abspath(get_db_path()))
    check("sessions loaded", len(app.sessions) > 0, f"{len(app.sessions)} sessions")
    check(f"event volume meets the {MIN_EVENTS:,} target",
          app.db.get_event_count() >= MIN_EVENTS,
          f"{app.db.get_event_count():,} events "
          f"(override with PYCHRONICLE_MIN_EVENTS)")

    start = time.perf_counter()
    async with app.run_test() as pilot:
        mount_seconds = time.perf_counter() - start

        print("\n2. first render")
        timeline = app.query_one("#log-list", ListView)
        rows = len(timeline.children)
        stats = static_text(app.query_one("#stats-display", Static))
        header = static_text(app.query_one("#session-label", Static))

        print(f"  header : {header.strip()[:96]}")
        print(f"  stats  : {stats.strip()}")
        print(f"  mounted in {mount_seconds:.2f}s with {rows} timeline rows")

        check("timeline is populated", rows > 0, f"{rows} rows")
        check("page never exceeds PAGE_SIZE", rows <= PAGE_SIZE,
              f"{rows} <= {PAGE_SIZE}")
        check("rows match loaded events", rows == len(app.events))
        check("first render under 5s", mount_seconds < 5.0,
              f"{mount_seconds:.2f}s")
        check("stats does not report zero", " 0 of 0 " not in stats)

        print("\n3. event detail")
        await pilot.press("tab")
        await pilot.pause()
        detail = static_text(app.query_one("#var-display", Static))
        title = static_text(app.query_one("#code-title", Static))
        print(f"  code title: {title.strip()}")

        # Inspect the rendered Syntax object rather than its repr, so this

        # actually proves the traced file was found and read from disk.
        sample = Database.row_to_dict(app.db.get_event_by_id(app.events[0][0]))
        syntax = app._render_source(sample["file"], sample["line"])
        print(f"  traced file: {sample['file']}")
        check("traced file exists on disk", os.path.exists(sample["file"]))
        check("code viewer read real source",
              "Source file not available" not in syntax.code
              and "def " in syntax.code)
        check("recorded line is inside the file",
              sample["line"] <= syntax.code.count("\n") + 1,
              f"line {sample['line']}")
        check("variable inspector filled", len(detail.strip()) > 0)
        check("inspector shows the traced file path", "file:" in detail)

        print("\n4. pagination")
        session = app._get_current_session()
        total = app.db.count_events_in_session(session[0])
        pages_before = app._page_count()
        page_one_ids = [e[0] for e in app.events]
        await pilot.press("right")
        await pilot.pause()
        page_two_ids = [e[0] for e in app.events]
        print(f"  session #{session[0]} has {total:,} events "
              f"across {pages_before} page(s)")

        if total > PAGE_SIZE:
            check("next page loads different events",
                  page_one_ids != page_two_ids and app.page == 1,
                  f"page={app.page}")
            check("page 2 ids continue after page 1",
                  min(page_two_ids) > max(page_one_ids))
            await pilot.press("left")
            await pilot.pause()
            check("previous page returns to page 1",
                  app.page == 0 and [e[0] for e in app.events] == page_one_ids)
        else:
            # Find a session big enough to page through.
            big = next((i for i, s in enumerate(app.sessions)
                        if app.db.count_events_in_session(s[0]) > PAGE_SIZE), None)
            check("a multi-page session exists to demonstrate paging",
                  big is not None)
            if big is not None:
                app.current_session_idx = big
                app.page = 0
                await app.refresh_timeline()
                await pilot.pause()
                first_ids = [e[0] for e in app.events]
                await pilot.press("right")
                await pilot.pause()
                second_ids = [e[0] for e in app.events]
                print(f"  paged session #{app.sessions[big][0]}: "
                      f"{app.db.count_events_in_session(app.sessions[big][0]):,} events, "
                      f"{app._page_count()} pages")
                check("next page loads different events",
                      first_ids != second_ids and app.page == 1)
                check("page 2 ids continue after page 1",
                      min(second_ids) > max(first_ids))
                await pilot.press("left")
                await pilot.pause()
                check("previous page returns to page 1", app.page == 0)

        print("\n5. event-type filter")
        await pilot.press("r")
        await pilot.pause()
        unfiltered_total = app.total_matching
        await pilot.press("f")          # -> call
        await pilot.pause()
        filtered_total = app.total_matching
        kinds = {e[2] for e in app.events}
        print(f"  filter={app.event_type_filter} "
              f"{unfiltered_total:,} -> {filtered_total:,} events")
        check("filter narrows the result set",
              0 < filtered_total <= unfiltered_total,
              f"{filtered_total} of {unfiltered_total}")
        check("only the selected event type is listed", kinds <= {"call"}, str(kinds))
        check("filter still returns results", len(app.events) > 0)

        await pilot.press("r")
        await pilot.pause()
        check("reset restores the unfiltered count",
              app.total_matching == unfiltered_total and app.event_type_filter is None)

        print("\n6. keyword search")
        # Derive the term from the data so this works against any database
        # rather than depending on one seeded program being present.
        session_id = app._get_current_session()[0]
        busiest = app.db.get_functions_in_session(session_id)
        keyword = next((name for name, _ in busiest
                        if name and name != "<module>"), None)
        print(f"  busiest functions: {[n for n, _ in busiest[:4]]}")

        search = app.query_one("#search-input", Input)
        unfiltered = app.total_matching
        search.value = keyword
        await pilot.pause()
        matched = app.total_matching
        print(f"  search '{keyword}' -> {matched:,} of {unfiltered:,} events")

        check("keyword search returns matching rows", matched > 0, f"{matched}")
        check("keyword search narrows the result set", matched <= unfiltered)
        check("every returned row matches the keyword",
              all(keyword in (e[3] or "") or keyword in (e[6] or "")
                  or keyword in (e[4] or "") for e in app.events))

        search.value = "definitely-not-in-this-database-xyzzy"
        await pilot.pause()
        print(f"  search for a missing term -> {app.total_matching} events")
        check("a term with no matches yields an empty timeline",
              app.total_matching == 0 and len(app.events) == 0)
        check("empty result still renders a placeholder row",
              len(app.query_one("#log-list", ListView).children) == 1)

        search.value = ""
        await pilot.pause()
        check("clearing the search restores results",
              app.total_matching == unfiltered, f"{app.total_matching:,}")

        print("\n7. session switching")
        before = app.current_session_idx
        await pilot.press("n")
        await pilot.pause()
        check("session switch moves and reloads",
              app.current_session_idx == before + 1
              and len(app.query_one("#log-list", ListView).children) == len(app.events),
              f"idx {before} -> {app.current_session_idx}")

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED: {failures}")
        return 1
    print("ALL UI CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_checks()))
