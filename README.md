# PyChronicle

A Python execution tracer with a terminal UI. It records every `call` / `line` /
`return` / `exception` event of a program along with the variable changes at each
step, stores them in SQLite alongside a static AST summary of the source, and
lets you step through the timeline afterwards.

## Quick start

```bash
pip install -r requirements.txt

python tools/seed_database.py     # record a realistic trace history
python app.py                     # open the Trace Timeline UI
```

Already have a database and just want to check it?

```bash
python tools/setup_db.py          # create / repair / verify, then report
```

## Tracing your own program

```bash
python src/tracer/tracer.py path/to/your_script.py
python app.py                     # the new session appears first
```

Run the tracer from any directory — it always writes to the database the UI
reads. Add `-v` to print every event as it is recorded.

The tracer is also importable, which is how the seeder records many sessions in
one process:

```python
from tracer import Tracer

tracer = Tracer()
tracer.trace_file("examples/invoice_service.py")
tracer.trace_callable(my_function, 42, session_name="unit run")
tracer.close()
```

## UI controls

| Key | Action |
|---|---|
| `n` / `p` | next / previous session |
| `→` / `←` | next / previous page of events |
| `f` | cycle the event-type filter (all → call → line → return → exception) |
| `r` | clear filters and search |
| type in the search box | filter by function, variable content or file |
| `d` | toggle dark mode |
| `q` | quit |

The timeline is paged at 250 events (`app.PAGE_SIZE`). Sessions here run to
thousands of events, and mounting one widget per event does not scale.

## The database

One canonical file: **`pychronicle.db` in the project root**.

Every component resolves it through `src/tracer/config.get_db_path()`, so the
tracer and the UI cannot drift apart. Point everything elsewhere with:

```bash
# PowerShell
$env:PYCHRONICLE_DB = "C:\path\to\other.db"
```

Three tables: `sessions` (one row per run), `events` (one row per trace step,
this is the Trace Timeline) and `ast_summary` (one row per statically parsed
file). Full column-by-column documentation is in
[docs/database_schema.md](docs/database_schema.md), and the DDL is dumped to
[docs/schema.sql](docs/schema.sql).

Read events through the `Database` methods rather than `SELECT *`. A database
migrated from an older schema gets its newer columns appended in migration
order, so positional reads silently return the wrong field. Every query in
`database.py` names its columns, and `Database.row_to_dict(row)` turns a row
into a name-keyed dict.

### Sharing the database file

The database runs in WAL mode, so recent writes may sit in a `pychronicle.db-wal`
side-car. `tools/setup_db.py` compacts the file and checkpoints the WAL back
into it, then tells you exactly which files to send. `Database.backup_database(path)`
makes a consistent copy through SQLite's online backup API — a plain file copy
is not WAL-safe.

## Tools

| Command | What it does |
|---|---|
| `python tools/seed_database.py` | Records a realistic trace history by running `examples/` under the real tracer, then backdating each session across the last three years. `--sessions`, `--max-events`, `--reset`, `--dry-run`. |
| `python tools/setup_db.py` | Creates the schema, merges legacy database files, repairs sessions (orphans, missing foreign key, legacy variable formats, colliding timestamps), compacts, and verifies. |
| `python tools/validate_db.py` | 42 structural, referential and content checks → `docs/validation_report.md`. |
| `python tools/perf_benchmark.py` | Query, index and write-throughput measurements → `docs/performance_report.md`. |
| `python tools/generate_docs.py` | Dumps `docs/schema.sql`, `docs/database_schema.md`, and runs every test suite into `docs/integration_report.md`. |

## Verification

```bash
python tests/db_regression_test.py     # database behaviour, incl. legacy migration
python tests/ui_smoke_test.py          # headless UI: paging, filters, search
python tests/dual_ui_compat_test.py    # one file readable by both UI branches
python tests/db_inspect.py             # print what is currently stored
python tests/storage_audit.py          # full performance audit (slow)
```

Reports live in [docs/](docs/): validation, performance and integration.

## Layout

```
app.py                          Textual UI (timeline, source viewer, inspector)
src/tracer/config.py            shared database path resolution
src/tracer/database.py          SQLite storage, sessions, diffs, maintenance
src/tracer/tracer.py            Tracer class (sys.settrace) + CLI
src/tracer/parser.py            AST front-end
src/tracer/visiter.py           AST visitor (structural summary)
examples/                       realistic programs used to generate trace data
tools/                          seed, setup, validate, benchmark, docs
tests/                          regression, UI, compatibility, inspector, audit
docs/                           generated schema and reports
```

## Notes on the seeded data

The events are real: every row was produced by actually running the programs in
`examples/` under the tracer, so file paths, line numbers, function names,
variable snapshots and diffs are genuine execution data — which matters because
the UI opens the traced file from disk and highlights the recorded line.

Only the timestamps are synthetic. A trace can only be recorded at the moment it
runs, so `Database.retime_session()` shifts each session onto a historical slot
to give the timeline and date filters a realistic three-year history.
