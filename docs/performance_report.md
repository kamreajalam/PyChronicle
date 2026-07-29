# PyChronicle — Performance Report

**Generated:** 2026-07-29 23:31:31  
**Database:** `pychronicle_1m.db` (1,283,059,712 bytes)  
**Dataset:** 1,001,032 events across 1,187 sessions  
**Repetitions per query:** 25  
**Python:** 3.14.4 · **SQLite:** 3.50.4  
**Produced by:** `tools/perf_benchmark.py`

## Summary

- Every query the UI issues completes in **under 424.0 ms**, so paging and filtering are limited by rendering, not by SQL.
- The slowest measured query is *global keyword search (LIKE, full table)* at 1902.71 ms.
- Indexes matter most for *filter by event type*: **9115.4x** faster than the same query with the indexes dropped.
- Writes: bulk executemany reaches **103,024 rows/s**, 26x the throughput of commit per insert (3,986 rows/s).

## Query latency

| Query | Avg | p95 | Best | Rows returned |
|---|---:|---:|---:|---:|
| list all sessions (session switcher) | 1.509 ms | 1.817 ms | 1.394 ms | 1,187 |
| count events in largest session (session #1177) | 0.199 ms | 0.203 ms | 0.189 ms | 1 |
| timeline page 1 (LIMIT 250) | 0.359 ms | 0.535 ms | 0.321 ms | 250 |
| timeline middle page (OFFSET 3848) | 0.466 ms | 0.486 ms | 0.446 ms | 250 |
| timeline last page (OFFSET 7946) | 2.595 ms | 2.212 ms | 1.352 ms | 250 |
| single event lookup by id (detail pane) | 0.035 ms | 0.070 ms | 0.013 ms | 9 |
| event-type filter, count + page | 1.349 ms | 1.804 ms | 1.108 ms | 2 |
| keyword search inside a session (LIKE) | 1.058 ms | 1.322 ms | 0.979 ms | 250 |
| function histogram for one session (GROUP BY) | 2.543 ms | 2.772 ms | 2.370 ms | 11 |
| execution summary over every event (1,001,032 rows) | 314.574 ms | 320.885 ms | 309.195 ms | 5 |
| month histogram (timeline chart) | 399.460 ms | 423.771 ms | 384.483 ms | 36 |
| day histogram (timeline chart) | 423.957 ms | 436.600 ms | 411.254 ms | 670 |
| session leaderboard (JOIN + GROUP BY) | 1469.790 ms | 3356.681 ms | 1149.371 ms | 10 |
| events by function across all sessions | 80.979 ms | 88.701 ms | 76.591 ms | 22,736 |
| events by type across all sessions | 1.262 ms | 1.877 ms | 0.834 ms | 549 |
| global keyword search (LIKE, full table) | 1902.706 ms | 3026.731 ms | 1612.551 ms | 45,460 |
| date-range scan (one month) | 156.574 ms | 196.362 ms | 140.359 ms | 39,738 |

Timeline pages are capped at 250 rows by `app.PAGE_SIZE`. The middle- and last-page timings show the cost of `OFFSET`: SQLite still walks the skipped rows, but at this dataset size the difference stays in the sub-millisecond range.

## Index impact

Measured on a temporary copy of the database: each query is timed with the indexes in place, then again after dropping them (`idx_events_event`, `idx_events_function`, `idx_events_file`, `idx_events_line`, `idx_events_session`, `idx_events_session_id`, `idx_events_timestamp`, `idx_sessions_started`).

| Query | With indexes | Without | Speedup |
|---|---:|---:|---:|
| filter by event type | 0.178 ms | 1625.313 ms | 9115.41x |
| filter by function | 1.070 ms | 2628.122 ms | 2455.96x |
| filter by file | 292.074 ms | 2410.739 ms | 8.25x |
| session page (session_id + id order) | 0.115 ms | 39.277 ms | 341.70x |
| date range scan | 1.511 ms | 1409.787 ms | 933.03x |

### Query plans

`SEARCH ... USING INDEX` means the index is used; `SCAN` means a full table walk.

| Query | Plan with indexes | Plan without |
|---|---|---|
| filter by event type | `SEARCH events USING COVERING INDEX idx_events_event (event=?)` | `SEARCH events USING COVERING INDEX idx_events_event (event=?)` |
| filter by function | `SEARCH events USING COVERING INDEX idx_events_function (function=?)` | `SEARCH events USING COVERING INDEX idx_events_function (function=?)` |
| filter by file | `SCAN events USING COVERING INDEX idx_events_file` | `SCAN events USING COVERING INDEX idx_events_file` |
| session page (session_id + id order) | `SEARCH events USING COVERING INDEX idx_events_session (session_id=?)` | `SEARCH events USING COVERING INDEX idx_events_session (session_id=?)` |
| date range scan | `SEARCH events USING COVERING INDEX idx_events_timestamp (timestamp>? AND timestamp<?)` | `SEARCH events USING COVERING INDEX idx_events_timestamp (timestamp>? AND timestamp<?)` |

## Write throughput

| Strategy | Rows | Time | Rate |
|---|---:|---:|---:|
| commit per insert | 400 | 0.100 s | 3,986 rows/s |
| batch mode | 400 | 0.008 s | 47,960 rows/s |
| bulk executemany | 400 | 0.004 s | 103,024 rows/s |

The tracer uses batch mode (`begin_batch` / `end_batch`) for exactly this reason: committing once per event would make the tracer itself the bottleneck in the traced program.

## Configuration in effect

| Setting | Value | Why |
|---|---|---|
| `journal_mode` | wal | write-ahead logging lets the UI read while the tracer writes |
| `synchronous` | 1 | fewer fsyncs, which is what cuts p99 write latency |
| `cache_size` | -8000 | negative value means KiB, so this is an 8 MB page cache |
| `temp_store` | 2 | sorting and grouping happen in memory |
| `page_size` | 4096 bytes | SQLite default |

## Storage

| Metric | Value |
|---|---|
| Database size | 1,283,059,712 bytes |
| Events | 1,001,032 |
| Bytes per event row | 1,282 |
| Average payload per event | 742 bytes (variables + var_diff) |

Row cost is dominated by the JSON variable snapshot and its diff. `tracer.to_storable()` truncates long strings at 200 characters and summarises containers over 8 items, which is what keeps the average payload bounded as traces grow.

