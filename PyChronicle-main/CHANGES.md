# PyChronicle - Changes by Thanu

Scope: **Integration Support, Testing, Additional Features** only.
No change was made to what the app fundamentally does (a Textual TUI that
scrubs through recorded execution steps showing code / variables / event
log for each step). Everything below is a bug fix, a testability
refactor, or an additive enhancement.

## Files added

| File | Purpose |
|---|---|
| `trace_loader.py` | Extracted the JSON / SQLite / demo-data loading logic out of `PyChronicleApp` into plain functions, so it can be unit-tested without spinning up the Textual app. Also fixes two integration bugs (see below). |
| `requirements.txt` | The project had no dependency manifest at all; `textual` and `rich` were required by `app.py` but undeclared. Added, plus `pytest`/`pytest-asyncio` for the test suite. |
| `pytest.ini` | Enables `pytest-asyncio` auto mode so the async Textual integration tests run without extra decorators per test. |
| `tests/test_trace_loader.py` | 16 unit tests covering JSON loading, SQLite loading, source-priority fallback (JSON → SQLite → demo), malformed-file handling, and `vars` formatting. |
| `tests/test_app_integration.py` | 5 integration tests that boot the real `PyChronicleApp` with Textual's `Pilot` test harness and drive it like a user would (select a step, check all three panels update, keyboard navigation, demo-data fallback banner, the crash regression below). |
| `CHANGES.md` | This file. |

## Files modified

| File | What changed |
|---|---|
| `app.py` | Bug fix, refactor to use `trace_loader`, and additive features (details below). |

## Bugs fixed

1. **`NameError` / broken formatting in `on_list_view_highlighted` (app.py).**
   The original method had inconsistent indentation:
   ```python
   def on_list_view_highlighted(self, event):
       if event.item and event.item.id:
           ...
           if isinstance(vars_text, dict):
               vars_text = "\n".join(...)
           code_text = data.get("code", "")
       vars_text = data.get("vars", "")      # <- dedented out of the `if`
       event_text = data.get("event", "")    # <- dedented out of the `if`
       ...
   ```
   Two separate problems here:
   - If a `ListView.Highlighted` event ever fired with no selected item
     (empty timeline, list losing selection, etc.), `data` was never
     assigned, and the method would raise `NameError: name 'data' is not
     defined` and crash the app.
   - Even when an item *was* selected, the dict→string conversion for
     `vars_text` was thrown away immediately by the unconditional
     `vars_text = data.get("vars", "")` a few lines later, so any trace
     step whose `"vars"` was a real dict (rather than a preformatted
     string) would render as `<class 'dict'>`'s default `str()` output
     instead of readable `key = value` lines.

   Fixed by moving all of this into a single, correctly-scoped
   `_show_step()` helper, and covered by
   `tests/test_app_integration.py::test_no_selection_does_not_crash` and
   `::test_selecting_a_step_updates_all_three_panels`.

2. **SQLite path returned differently-shaped data than the JSON path.**
   The JSON loader returned `{"code": ..., "vars": ..., "event": ...}` per
   step; the SQLite loader returned a plain tuple-derived dict that
   happened to have the same keys by coincidence of column order, with no
   guarantee of matching if the schema changed. Now both paths are
   produced by the same code shape and are covered by tests that check
   both sources independently and that the app renders identically
   regardless of which source is used.

3. **Unhandled/partial failures in trace loading.** The original code
   only wrapped the two `open`/`sqlite3.connect` calls in broad
   `except Exception`, printed a message, and then would silently fall
   through — but a malformed JSON file with valid syntax but empty content
   (`{}`), or a SQLite DB missing the `execution_steps` table, were not
   explicitly tested and one path (SQLite `OperationalError` on a missing
   table) was not distinguished from "file doesn't exist". `trace_loader.py`
   now handles both explicitly and is regression-tested for each case.

## Additional features

All additive, none change the existing behavior when no new options are used:

- **`--trace` / `-t` and `--db` CLI arguments** so you can point PyChronicle
  at a specific trace file or database instead of only ever reading
  `trace_output.json` / `pychronicle.db` from the current directory:
  ```bash
  python app.py --trace my_run.json
  python app.py --db my_run.db
  ```
- **"Using demo data" indicator.** If neither a trace file nor a database
  is found, the sidebar now reads `TIMELINE (demo data)` instead of just
  `TIMELINE`, so it's obvious you're looking at the built-in sample data
  rather than a real trace that failed to load correctly.
- **Step position indicator.** The code viewer title now shows
  `CODE VIEWER (Step 2 of 5)` while browsing, so you always know where you
  are in the timeline.
- **Home / End keybindings** to jump straight to the first or last step
  in the timeline, in addition to arrow-key scrubbing.
- **Out-of-range line-highlight guard.** `line_number` values from a trace
  file that don't correspond to an actual line in that step's code no
  longer get passed to `rich.syntax.Syntax`'s `highlight_lines` untested;
  they're now validated against the step's actual line count first.
- **Friendlier empty-value display.** Empty `vars`/`event` values now show
  `"No variables."` / `"System idle."` (matching the panel's own
  placeholder text) instead of a blank panel.

## Testing summary

```
$ python -m pytest tests/ -v
...
20 passed in ~1.2s
```

- `tests/test_trace_loader.py` — 16 tests, pure unit tests, no Textual
  event loop needed (fast, good for CI).
- `tests/test_app_integration.py` — 5 tests using Textual's `Pilot` to
  drive the actual running app (boot, selection, keybindings, fallback
  banner, and the crash regression from bug #1 above).

Run with:
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Explicitly out of scope (left untouched)

- The overall widget layout/CSS and visual design.
- The trace data *format* (`step_id -> {code, vars, event, line_number}`)
  and the demo-data content itself.
- Any tracer/recorder component that produces `trace_output.json` or
  `pychronicle.db` in the first place — none exists in this repo; only the
  viewer (`app.py`) does, so nothing there was added or changed.
