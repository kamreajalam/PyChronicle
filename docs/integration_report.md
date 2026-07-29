# PyChronicle — Integration Report

**Generated:** 2026-07-29 23:11:32  
**Database:** `pychronicle.db` (93,827,072 bytes)  
**Produced by:** `tools/generate_docs.py`

## Result

All verification suites passed: **118 checks passed, 0 failed** across 4 suites.

| Area | Script | Checks passed | Failed | Exit |
|---|---|---:|---:|:---:|
| Database behaviour | `tests/db_regression_test.py` | 32 | 0 | 0 |
| UI rendering | `tests/ui_smoke_test.py` | 28 | 0 | 0 |
| Dual-UI compatibility | `tests/dual_ui_compat_test.py` | 16 | 0 | 0 |
| Database validation | `tools/validate_db.py` | 42 | 0 | 0 |

- **Database behaviour** (`tests/db_regression_test.py`) — Schema migration from the pre-session layout, orphan adoption, session pruning, cross-database merge, batch inserts, JSON export/import, WAL-safe backup.
- **UI rendering** (`tests/ui_smoke_test.py`) — Headless Textual run: timeline population, paging, event-type filter, keyword search, source resolution, session switching.
- **Dual-UI compatibility** (`tests/dual_ui_compat_test.py`) — The same file read both by named columns and by the integrated branch's positional `SELECT *`, plus `ast_summary` layout.
- **Database validation** (`tools/validate_db.py`) — Structure, referential integrity, content sanity, timestamp validity, payload decodability.

## The pipeline that was verified

```
examples/*.py
      │
      ├── parser.py + visiter.py ──> ast_summary   (static structure)
      │
      └── tracer.py (sys.settrace) ──> events      (runtime steps)
                                        │  session_id
                                        ▼
                                     sessions
                                        │
                    config.get_db_path() ── one canonical file
                                        │
                                        ▼
                                     app.py  (Trace Timeline)
```

Both stages write through the same `Database` instance, so a traced run always lands in the file the UI reads. The path comes from `config.get_db_path()` rather than a relative default, which is what previously let the tracer and the UI drift onto two different files.

## Data actually present

| Metric | Value |
|---|---|
| Trace events | **100,170** |
| Trace sessions | 333 |
| Files with stored AST summaries | 7 |
| Distinct functions observed | 60 |
| Earliest event | 2023-08-04T18:11:26.086048 |
| Latest event | 2026-07-29T20:52:35.363822 |
| Distinct months with activity | 36 |

Event mix:

| Event type | Count | Share |
|---|---:|---:|
| `line` | 76,918 | 76.8% |
| `call` | 11,578 | 11.6% |
| `return` | 11,578 | 11.6% |
| `exception` | 96 | 0.1% |

Events per traced program:

| Script | Sessions | Events |
|---|---:|---:|
| `inventory_planner.py` | 13 | 25,587 |
| `api_gateway_sim.py` | 58 | 16,945 |
| `recommendation_engine.py` | 22 | 14,288 |
| `order_etl_pipeline.py` | 49 | 11,247 |
| `invoice_service.py` | 49 | 11,149 |
| `sample_program.py` | 93 | 10,509 |
| `auth_service.py` | 45 | 10,364 |

Largest sessions (these are the ones that exercise paging):

| Session | Started | Events | Functions |
|---|---|---:|---:|
| #341 replenishment-planner #404 (prod) 2026-01-31 | 2026-01-31T03:17 | 8,192 | 11 |
| #46 replenishment-planner #401 (staging) 2025-06 | 2025-06-04T02:16 | 2,463 | 11 |
| #168 replenishment-planner #406 (prod) 2026-04-26 | 2026-04-26T00:53 | 2,463 | 11 |
| #230 replenishment-planner #408 (prod) 2024-06-18 | 2024-06-18T03:27 | 2,463 | 11 |
| #75 recommender-rebuild #407 (ci) 2023-09-22 13: | 2023-09-22T13:44 | 1,584 | 17 |
| #99 recommender-rebuild #402 (ci) 2024-09-11 09: | 2024-09-11T09:30 | 1,568 | 17 |
| #42 recommender-rebuild #402 (ci) 2025-05-08 16: | 2025-05-08T16:01 | 1,524 | 17 |
| #338 recommender-rebuild #409 (staging) 2026-01-2 | 2026-01-23T10:12 | 1,494 | 17 |

Monthly activity (the timeline histogram the charts read):

| Month | Events |
|---|---:|
| 2023-08 | 2,090 `###` |
| 2023-09 | 1,810 `###` |
| 2023-10 | 521 `#` |
| 2023-11 | 2,736 `#####` |
| 2023-12 | 2,319 `####` |
| 2024-01 | 230 `#` |
| 2024-02 | 967 `#` |
| 2024-03 | 866 `#` |
| 2024-04 | 1,632 `###` |
| 2024-05 | 1,853 `###` |
| 2024-06 | 3,664 `#######` |
| 2024-07 | 1,072 `##` |
| 2024-08 | 1,225 `##` |
| 2024-09 | 5,177 `#########` |
| 2024-10 | 3,063 `#####` |
| 2024-11 | 2,260 `####` |
| 2024-12 | 2,794 `#####` |
| 2025-01 | 919 `#` |
| 2025-02 | 1,886 `###` |
| 2025-03 | 3,788 `#######` |
| 2025-04 | 3,151 `######` |
| 2025-05 | 3,234 `######` |
| 2025-06 | 7,982 `###############` |
| 2025-07 | 1,462 `##` |
| 2025-08 | 1,108 `##` |
| 2025-09 | 2,897 `#####` |
| 2025-10 | 2,942 `#####` |
| 2025-11 | 2,170 `####` |
| 2025-12 | 5,840 `###########` |
| 2026-01 | 14,635 `############################` |
| 2026-02 | 1,518 `##` |
| 2026-03 | 507 `#` |
| 2026-04 | 4,009 `#######` |
| 2026-05 | 1,011 `#` |
| 2026-06 | 1,576 `###` |
| 2026-07 | 5,256 `##########` |

## Known limits

- **67 events reference source files from other machines.** They were merged in from the original `src/tracer/pychronicle.db`, which had been copied between three developers (`C:\Users\DELL\...`, `e:\PyChronicle\...`). Their source cannot be shown here; the viewer reports "source file not available" for those rows. The other 100,103 events resolve their source correctly.
- **Timestamps are synthetic, the rest is not.** A trace can only be recorded at the moment it runs, so `retime_session()` shifts each session onto a historical slot. File paths, line numbers, function names, variable snapshots and diffs are all genuine execution data.
- **Sessions cover 25 of the last 36 months.** With 60 seeded runs weighted toward recent activity, older months are sparse. `--sessions` raises the count if denser history is wanted.

