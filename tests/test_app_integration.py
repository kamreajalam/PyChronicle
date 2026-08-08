"""
Integration tests for PyChronicleApp.

These exercise app.py's own code (widget composition + event handling),
not just the extracted trace_loader helpers, using Textual's Pilot test
harness to drive the running app the way a user would.
"""

import json
import os
import sys

import pytest
from textual.widgets import ListView, Static

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import PyChronicleApp


def _write_trace(tmp_path, steps):
    trace_file = tmp_path / "trace_output.json"
    trace_file.write_text(json.dumps(steps))
    return str(trace_file)


@pytest.mark.asyncio
async def test_app_boots_and_populates_timeline(tmp_path):
    trace_path = _write_trace(
        tmp_path,
        {
            "step1": {"code": "x = 1", "vars": "x = 1", "event": "init"},
            "step2": {"code": "x = 2", "vars": "x = 2", "event": "increment"},
        },
    )
    app = PyChronicleApp(json_path=trace_path, db_path=str(tmp_path / "none.db"))

    async with app.run_test() as pilot:
        list_view = app.query_one("#timeline-list", ListView)
        assert len(list_view) == 2
        assert app.data_source == "json"


@pytest.mark.asyncio
async def test_selecting_a_step_updates_all_three_panels(tmp_path):
    trace_path = _write_trace(
        tmp_path,
        {
            "step1": {
                "code": "def add(a, b):\n    return a + b",
                "vars": {"a": 5, "b": 10},
                "event": "Function add called.",
                "line_number": 2,
            }
        },
    )
    app = PyChronicleApp(json_path=trace_path, db_path=str(tmp_path / "none.db"))

    async with app.run_test() as pilot:
        list_view = app.query_one("#timeline-list", ListView)
        list_view.focus()
        list_view.index = 0
        await pilot.pause()

        var_display = app.query_one("#var-display", Static)
        event_display = app.query_one("#event-display", Static)

        # vars was a dict in the trace file - it must be rendered as
        # readable "key = value" text, not Python's dict repr.
        assert "a = 5" in str(var_display.render())
        assert "b = 10" in str(var_display.render())
        assert "Function add called." in str(event_display.render())


@pytest.mark.asyncio
async def test_no_selection_does_not_crash(tmp_path):
    """
    Regression test: on_list_view_highlighted previously referenced
    `data` outside the `if event.item and event.item.id:` guard, which
    raised NameError whenever a Highlighted event fired with no item
    (e.g. an empty timeline). This should now just be a no-op.
    """
    trace_path = _write_trace(tmp_path, {})  # empty -> falls back to demo data path is skipped since file exists but empty dict
    app = PyChronicleApp(json_path=trace_path, db_path=str(tmp_path / "none.db"))

    async with app.run_test() as pilot:
        # Directly invoke the handler with an item lacking an id, mirroring
        # what a real (item=None) Highlighted event would do.
        list_view = app.query_one("#timeline-list", ListView)
        event = ListView.Highlighted(list_view, None)
        app.on_list_view_highlighted(event)  # should not raise
        await pilot.pause()


@pytest.mark.asyncio
async def test_first_and_last_step_bindings(tmp_path):
    trace_path = _write_trace(
        tmp_path,
        {
            "step1": {"code": "a", "vars": "a", "event": "a"},
            "step2": {"code": "b", "vars": "b", "event": "b"},
            "step3": {"code": "c", "vars": "c", "event": "c"},
        },
    )
    app = PyChronicleApp(json_path=trace_path, db_path=str(tmp_path / "none.db"))

    async with app.run_test() as pilot:
        list_view = app.query_one("#timeline-list", ListView)
        list_view.focus()
        list_view.index = 1
        await pilot.pause()

        app.action_last_step()
        await pilot.pause()
        assert list_view.index == 2

        app.action_first_step()
        await pilot.pause()
        assert list_view.index == 0


@pytest.mark.asyncio
async def test_falls_back_to_demo_data_when_no_trace_present(tmp_path):
    app = PyChronicleApp(
        json_path=str(tmp_path / "missing.json"),
        db_path=str(tmp_path / "missing.db"),
    )

    async with app.run_test() as pilot:
        assert app.data_source == "demo"
        title = app.query_one("#sidebar-title", Static)
        assert "demo data" in str(title.render())
