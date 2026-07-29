# PyChronicle — Database Validation Report

**Generated:** 2026-07-29 23:25:01  
**Database:** `pychronicle_1m.db` (1,283,059,712 bytes)  
**Produced by:** `tools/validate_db.py`

## Result

| Checks | Passed | Warnings | Failed |
|---|---|---|---|
| 42 | 42 | 0 | 0 |

All checks passed. The database is structurally sound, referentially consistent and populated.

## Inventory

| Metric | Value |
|---|---|
| Trace events | 1,001,032 |
| Trace sessions | 1,187 |
| AST summaries (files parsed) | 7 |
| Distinct functions observed | 57 |
| Distinct source files traced | 7 |
| Earliest event | 2023-08-01T00:51:10.716590 |
| Latest event | 2026-07-29T16:19:23.827860 |
| Distinct months covered | 36 |

Event mix:

| Event type | Count |
|---|---|
| `line` | 783,209 |
| `call` | 108,637 |
| `return` | 108,637 |
| `exception` | 549 |

## Checks

### Structure

| Check | Result | Detail |
|---|---|---|
| table `sessions` exists | PASS | — |
| table `events` exists | PASS | — |
| table `ast_summary` exists | PASS | — |
| events has every canonical column | PASS | 9 columns |
| events.id is INTEGER PRIMARY KEY | PASS | — |
| events.line is INTEGER | PASS | — |
| events.session_id is INTEGER | PASS | — |
| events text columns are TEXT | PASS | wrong=[] |
| sessions has every expected column | PASS | 7 columns |
| all expected indexes present | PASS | 8 indexes |
| events declares its sessions foreign key | PASS | 1 foreign key(s) |
| ast_summary.file has a UNIQUE constraint | PASS | 1 unique index(es) |
### Integrity

| Check | Result | Detail |
|---|---|---|
| PRAGMA integrity_check | PASS | ok |
| PRAGMA foreign_key_check finds no violations | PASS | 0 violation(s) |
| no events point at a missing session | PASS | 0 orphan(s) |
| no events without a session | PASS | 0 unassigned |
| no empty sessions | PASS | 0 empty |
### Content

| Check | Result | Detail |
|---|---|---|
| events table is populated | PASS | 1,001,032 rows |
| sessions table is populated | PASS | 1,187 rows |
| event volume meets the 10,000 target | PASS | 1,001,032 events (override with PYCHRONICLE_MIN_EVENTS) |
| ast_summary table is populated | PASS | 7 file(s) |
| events.event has no NULLs | PASS | 0 null(s) |
| events.function has no NULLs | PASS | 0 null(s) |
| events.file has no NULLs | PASS | 0 null(s) |
| events.line has no NULLs | PASS | 0 null(s) |
| events.timestamp has no NULLs | PASS | 0 null(s) |
| no negative line numbers | PASS | — |
| event types are all recognised | PASS | types=['call', 'exception', 'line', 'return'] |
| no double-inserted events | PASS | 0 duplicate group(s) |
| ast_summary holds one row per file | PASS | 7 rows / 7 files |
### Timestamps

| Check | Result | Detail |
|---|---|---|
| every timestamp parses as ISO-8601 | PASS | 0 invalid |
| no timestamps in the future | PASS | latest=2026-07-29T16:19:23.827860 |
| history spans at least 2 years | PASS | 1093 days (2023-08-01 .. 2026-07-29) |
| events are chronological within each session | PASS | 0 out of order |
| no session ends before it starts | PASS | — |
| events spread across at least 12 months | PASS | 36 distinct months |
### Payloads

| Check | Result | Detail |
|---|---|---|
| variable snapshots all decode | PASS | 0 undecodable |
| variable diffs are well-formed JSON | PASS | 0 malformed |
| most events carry variables | PASS | 6,635 of 1,001,032 have no variables |
| payload size per event stays bounded | PASS | avg=742 B, max=8,039 B |
| sessions.total_events matches actual rows | PASS | 0 mismatch(es) |
| no sessions left in a non-completed state | PASS | — |

## Notes on two checks that look surprising

**Duplicate data.** Repeated `(function, line)` pairs are expected in trace data: a loop body genuinely executes the same line many times. The duplicate check therefore looks for rows identical *including their timestamp*, which would indicate the same event was written twice rather than executed twice.

**Events with no variables.** A `call` event on a function with no arguments has an empty local scope, so an empty `variables` value is correct rather than missing data. The check only fails if most rows are empty.

