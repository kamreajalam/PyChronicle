# PyChronicle — Database Schema

**Generated:** 2026-07-29 23:11:22  
**Database:** `pychronicle.db` (93,827,072 bytes)  
**Engine:** SQLite (no ORM, no migration framework — the `Database` class in `src/tracer/database.py` owns all SQL)  
**Produced by:** `tools/generate_docs.py`

## Overview

```
sessions ──1:N──> events
   id   <───────── session_id   (FOREIGN KEY)

ast_summary        one row per source file (UNIQUE file)
   file  ~~~~~~~~~ events.file   (same path, not a declared FK)
```

`ast_summary.file` and `events.file` hold the same absolute paths, which is how static structure lines up with runtime events. It is deliberately not a foreign key: a file can be parsed without being executed, and vice versa.

## Tables

| Table | Rows | Purpose |
|---|---:|---|
| `ast_summary` | 7 | One row per statically parsed source file, produced by the AST module (`parser.py` + `visiter.py`). |
| `events` | 100,170 | One row per trace step. This is the Trace Timeline. |
| `imported_sources` | 1 | Bookkeeping for `tools/setup_db.py`: which legacy database files have already been merged, so merging is idempotent. |
| `sessions` | 333 | One row per traced run. Groups events and drives the UI's session switcher. |

### `ast_summary`

| # | Column | Type | Not null | Default | PK | Meaning |
|---:|---|---|:---:|---|:---:|---|
| 0 | `id` | INTEGER | no | — | yes | Row id. |
| 1 | `file` | TEXT | no | — | no | Absolute path of the parsed file. UNIQUE, so re-parsing updates in place. |
| 2 | `imports` | TEXT | no | — | no | JSON array of imported module names. |
| 3 | `variables` | TEXT | no | — | no | JSON array of assigned variable names. |
| 4 | `functions` | TEXT | no | — | no | JSON array of function names. |
| 5 | `classes` | TEXT | no | — | no | JSON array of class names. |
| 6 | `loops` | TEXT | no | — | no | JSON array of loop kinds (`for` / `while`). |
| 7 | `conditions` | TEXT | no | — | no | JSON array of branch markers. |
| 8 | `returns` | TEXT | no | — | no | JSON array of `{line, code}` for return statements. |
| 9 | `function_defs` | TEXT | no | — | no | JSON array of `{name, line}` definitions. |
| 10 | `class_defs` | TEXT | no | — | no | JSON array of `{name, line}` definitions. |
| 11 | `parsed_at` | TEXT | no | CURRENT_TIMESTAMP | no | ISO-8601 time the file was parsed. |

| Index | Columns | Unique |
|---|---|:---:|
| `sqlite_autoindex_ast_summary_1` | `file` | yes |

### `events`

| # | Column | Type | Not null | Default | PK | Meaning |
|---:|---|---|:---:|---|:---:|---|
| 0 | `id` | INTEGER | no | — | yes | Row id. Referenced by the UI's list widgets. |
| 1 | `event` | TEXT | no | — | no | Trace event kind: `call`, `line`, `return`, `exception`. |
| 2 | `function` | TEXT | no | — | no | Name of the function whose frame was executing (`<module>` for top-level code). |
| 3 | `file` | TEXT | no | — | no | Absolute path of the source file. The UI opens this to show the code. |
| 4 | `line` | INTEGER | no | — | no | Line number being executed, used to highlight the source. |
| 5 | `variables` | TEXT | no | — | no | JSON snapshot of the frame's locals at this step, truncated by `tracer.to_storable()`. |
| 6 | `timestamp` | TEXT | no | CURRENT_TIMESTAMP | no | ISO-8601 timestamp. Ordered consistently with `id` inside a session. |
| 7 | `session_id` | INTEGER | no | — | no | Owning run. Foreign key to `sessions.id`. |
| 8 | `var_diff` | TEXT | no | — | no | JSON diff against the previous snapshot of the same scope: `added`, `changed`, `removed`. |

Foreign keys:

- `session_id` → `sessions.id` (on update NO ACTION, on delete NO ACTION)

| Index | Columns | Unique |
|---|---|:---:|
| `idx_events_timestamp` | `timestamp` | no |
| `idx_events_session_id` | `session_id`, `id` | no |
| `idx_events_session` | `session_id` | no |
| `idx_events_line` | `line` | no |
| `idx_events_file` | `file` | no |
| `idx_events_function` | `function` | no |
| `idx_events_event` | `event` | no |

### `imported_sources`

| # | Column | Type | Not null | Default | PK | Meaning |
|---:|---|---|:---:|---|:---:|---|
| 0 | `id` | INTEGER | no | — | yes | — |
| 1 | `source_path` | TEXT | no | — | no | — |
| 2 | `events` | INTEGER | no | — | no | — |
| 3 | `imported_at` | TEXT | no | CURRENT_TIMESTAMP | no | — |

| Index | Columns | Unique |
|---|---|:---:|
| `sqlite_autoindex_imported_sources_1` | `source_path` | yes |

### `sessions`

| # | Column | Type | Not null | Default | PK | Meaning |
|---:|---|---|:---:|---|:---:|---|
| 0 | `id` | INTEGER | no | — | yes | Run id. Sessions are listed newest first in the UI. |
| 1 | `name` | TEXT | no | — | no | Human-readable run label, e.g. the pipeline and environment. |
| 2 | `script_file` | TEXT | no | — | no | Script that was traced, or NULL for the built-in demo. |
| 3 | `started_at` | TEXT | no | — | no | ISO-8601 start time. |
| 4 | `ended_at` | TEXT | no | — | no | ISO-8601 end time, set by `end_session()`. |
| 5 | `total_events` | INTEGER | no | 0 | no | Event count, recomputed by `refresh_session_counts()`. |
| 6 | `status` | TEXT | no | 'running' | no | `running` while tracing, `completed` afterwards. |

| Index | Columns | Unique |
|---|---|:---:|
| `idx_sessions_started` | `started_at` | no |

## Two column orders, on purpose

The `events` table has a *physical* column order that differs from the *logical* order the code uses:

- **Physical (on disk / `SELECT *`):** `id`, `event`, `function`, `file`, `line`, `variables`, `timestamp`, `session_id`, `var_diff`
- **Logical (`Database.EVENT_COLUMNS`):** `id`, `session_id`, `event`, `function`, `file`, `line`, `variables`, `var_diff`, `timestamp`

The integrated UI branch reads `SELECT *` rows positionally as `(id, event, function, file, line, variables, timestamp)`, so those seven columns are kept first and `session_id` / `var_diff` are appended after them. That lets one database file serve both UIs — verified by `tests/dual_ui_compat_test.py`.

Every statement in `database.py` names its columns explicitly, so this module never depends on physical order. Avoid `SELECT *` in new code for the same reason: a database migrated from an older schema gets its columns appended in migration order, and positional reads then silently return the wrong field.

## Sample rows

### `sessions`

```
           id : 341
         name : replenishment-planner #404 (prod) 2026-01-31 03:17
  script_file : C:\Users\hp\OneDrive\Desktop\py\PyChronicle\examples\inventory_planner.py
   started_at : 2026-01-31T03:17:05.331657
     ended_at : 2026-01-31T03:17:16.796657
 total_events : 8192
       status : completed
------------------------------------------------------------
           id : 340
         name : gateway-load-probe #433 (prod) 2026-01-28 21:26
  script_file : C:\Users\hp\OneDrive\Desktop\py\PyChronicle\examples\api_gateway_sim.py
   started_at : 2026-01-28T21:26:05.606498
     ended_at : 2026-01-28T21:26:09.102498
 total_events : 127
       status : completed
------------------------------------------------------------
           id : 339
         name : smoke-check #437 (ci) 2026-01-28 05:21
  script_file : C:\Users\hp\OneDrive\Desktop\py\PyChronicle\examples\sample_program.py
   started_at : 2026-01-28T05:21:58.760459
     ended_at : 2026-01-28T05:22:02.431459
 total_events : 113
       status : completed
------------------------------------------------------------
```

### `events`

```
           id : 1
        event : call
     function : main
         file : C:\Users\DELL\Desktop\PyChronicle\src\tracer\tracer.py
         line : 48
    variables : {}
    timestamp : 2026-07-29T20:43:08.570406
   session_id : 5
     var_diff : None
------------------------------------------------------------
           id : 2
        event : line
     function : main
         file : C:\Users\DELL\Desktop\PyChronicle\src\tracer\tracer.py
         line : 49
    variables : {}
    timestamp : 2026-07-29T20:43:08.595296
   session_id : 5
     var_diff : None
------------------------------------------------------------
           id : 3
        event : line
     function : main
         file : C:\Users\DELL\Desktop\PyChronicle\src\tracer\tracer.py
         line : 50
    variables : {"x": 10}
    timestamp : 2026-07-29T20:43:08.619322
   session_id : 5
     var_diff : None
------------------------------------------------------------
```

### `ast_summary`

```
           id : 1
         file : C:\Users\hp\OneDrive\Desktop\py\PyChronicle\examples\order_etl_pipeline.py
      imports : ["os", "random"]
    variables : ["REGIONS", "CHANNELS", "PRODUCTS", "rng", "rows", "quantity", "order_id", "order_id", "quantity", "unit_price", "gross_local", "fx_rate", "gross_usd"... (+196 chars)
    functions : ["build_raw_orders", "validate_order", "normalise_to_base_currency", "deduplicate", "aggregate_by_region", "top_skus", "main"]
      classes : []
        loops : ["for", "for", "for", "for", "for", "for"]
   conditions : ["if", "if", "if", "if", "if"]
      returns : [{"line": 62, "code": "Return(value=Name(id='rows', ctx=Load()))"}, {"line": 77, "code": "Return(value=Constant(value=True))"}, {"line": 85, "code": "... (+1408 chars)
function_defs : [{"name": "build_raw_orders", "line": 35}, {"name": "validate_order", "line": 65}, {"name": "normalise_to_base_currency", "line": 80}, {"name": "dedup... (+133 chars)
   class_defs : []
    parsed_at : 2026-07-29T23:03:14.376179
------------------------------------------------------------
```

## Runtime settings

Applied in `Database.__init__` on every connection:

| Pragma | Value | Effect |
|---|---|---|
| `journal_mode` | wal | write-ahead logging, so the UI can read while the tracer writes |
| `synchronous` | 1 | fewer fsyncs per commit |
| `cache_size` | -8000 | negative means KiB — an 8 MB page cache |
| `temp_store` | 2 | sorts and groups in memory |

Because WAL keeps recent writes in a `-wal` side-car, `Database.close()` checkpoints it back into the `.db` so the single file is complete when copied.

