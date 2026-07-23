"""
PyChronicle Storage Audit Script
Author: Rohit Jain (SQLite Module)

This script performs a comprehensive storage audit by:
1. Generating thousands of state changes (trace events)
2. Verifying all records are stored correctly
3. Measuring database performance (insert, query, bulk ops)
4. Identifying and applying optimizations
"""

import sys
import os
import time
import random
import string
import statistics

# Add src/tracer to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "tracer"))

from database import Database
from datetime import datetime

# --- Configuration ---
AUDIT_DB = os.path.join(
    os.path.dirname(__file__),
    f"storage_audit_{datetime.now().strftime('%H%M%S')}.db"
)
NUM_EVENTS = 2000  # Number of state changes to generate
BATCH_SIZES = [100, 500, 1000, 2000]

# --- Test Data Generators ---
EVENT_TYPES = ["call", "line", "return", "exception"]
FUNCTION_NAMES = [
    "main", "add", "subtract", "multiply", "divide",
    "process_data", "validate_input", "transform",
    "calculate_sum", "parse_config", "handle_error",
    "fetch_data", "save_result", "log_event", "cleanup",
    "initialize", "connect", "disconnect", "retry", "filter_items"
]
FILE_NAMES = [
    "app.py", "utils.py", "models.py", "database.py",
    "tracer.py", "config.py", "handlers.py", "core.py"
]


def generate_random_variables():
    """Generate realistic variable state dictionaries."""
    var_count = random.randint(1, 8)
    variables = {}
    for _ in range(var_count):
        var_name = random.choice(["x", "y", "z", "result", "data", "count",
                                   "items", "value", "flag", "temp", "index", "name"])
        var_type = random.choice(["int", "str", "list", "bool", "float"])
        if var_type == "int":
            variables[var_name] = random.randint(-1000, 1000)
        elif var_type == "str":
            variables[var_name] = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 20)))
        elif var_type == "list":
            variables[var_name] = [random.randint(0, 100) for _ in range(random.randint(1, 5))]
        elif var_type == "bool":
            variables[var_name] = random.choice([True, False])
        elif var_type == "float":
            variables[var_name] = round(random.uniform(-100, 100), 4)
    return str(variables)


def generate_event():
    """Generate a single random trace event."""
    return {
        "event": random.choice(EVENT_TYPES),
        "function": random.choice(FUNCTION_NAMES),
        "file": random.choice(FILE_NAMES),
        "line": random.randint(1, 500),
        "variables": generate_random_variables()
    }


# --- Audit Results Collector ---
class AuditResults:
    def __init__(self):
        self.results = []
        self.errors = []
        self.performance_metrics = {}

    def add_result(self, test_name, passed, details=""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {test_name}: {details}")

    def add_error(self, test_name, error):
        self.errors.append({"test": test_name, "error": str(error)})
        print(f"  [ERROR] {test_name}: {error}")

    def add_metric(self, name, value, unit=""):
        self.performance_metrics[name] = {"value": value, "unit": unit}

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": len(self.errors),
            "metrics": self.performance_metrics
        }


# --- Audit Tests ---
def test_bulk_insert(db, audit):
    """Test 1: Insert thousands of state changes and measure performance."""
    print("\n" + "=" * 60)
    print("TEST 1: Bulk Insert - Generating thousands of state changes")
    print("=" * 60)

    events_generated = []
    start_time = time.perf_counter()

    for i in range(NUM_EVENTS):
        event = generate_event()
        events_generated.append(event)
        db.insert_event(
            event["event"],
            event["function"],
            event["file"],
            event["line"],
            event["variables"]
        )

    elapsed = time.perf_counter() - start_time
    rate = NUM_EVENTS / elapsed

    audit.add_metric("single_insert_total_time", round(elapsed, 3), "seconds")
    audit.add_metric("single_insert_rate", round(rate, 1), "events/sec")
    audit.add_metric("single_insert_avg_latency", round((elapsed / NUM_EVENTS) * 1000, 4), "ms/event")

    audit.add_result(
        "Bulk insert (individual commits)",
        True,
        f"{NUM_EVENTS} events in {elapsed:.3f}s ({rate:.1f} events/sec)"
    )

    return events_generated


def test_record_integrity(db, audit, events_generated):
    """Test 2: Verify all records are stored correctly."""
    print("\n" + "=" * 60)
    print("TEST 2: Record Integrity Verification")
    print("=" * 60)

    # Check total count
    stored_count = db.get_event_count()
    audit.add_result(
        "Record count matches",
        stored_count == NUM_EVENTS,
        f"Expected {NUM_EVENTS}, got {stored_count}"
    )

    # Verify individual records by sampling
    all_events = db.get_all_events()
    sample_size = min(500, NUM_EVENTS)
    sample_indices = random.sample(range(NUM_EVENTS), sample_size)
    mismatches = 0

    for idx in sample_indices:
        stored = all_events[idx]
        original = events_generated[idx]

        # stored format: (id, event, function, file, line, variables, timestamp)
        if (stored[1] != original["event"] or
            stored[2] != original["function"] or
            stored[3] != original["file"] or
            stored[4] != original["line"] or
            stored[5] != original["variables"]):
            mismatches += 1

    audit.add_result(
        f"Record data integrity ({sample_size} samples)",
        mismatches == 0,
        f"{mismatches} mismatches found out of {sample_size} samples"
    )

    # Verify no NULL fields
    null_count = 0
    for event in all_events:
        for field in event[1:]:  # Skip ID
            if field is None:
                null_count += 1
                break

    audit.add_result(
        "No NULL fields in records",
        null_count == 0,
        f"{null_count} records with NULL fields"
    )

    # Verify timestamps are valid ISO format
    invalid_timestamps = 0
    for event in all_events:
        try:
            datetime.fromisoformat(event[6])
        except (ValueError, TypeError):
            invalid_timestamps += 1

    audit.add_result(
        "All timestamps valid ISO format",
        invalid_timestamps == 0,
        f"{invalid_timestamps} invalid timestamps"
    )

    # Verify IDs are sequential
    ids = [event[0] for event in all_events]
    is_sequential = all(ids[i] < ids[i+1] for i in range(len(ids)-1))
    audit.add_result(
        "IDs are sequential",
        is_sequential,
        f"ID range: {ids[0]} to {ids[-1]}"
    )


def test_query_performance(db, audit):
    """Test 3: Measure query performance across different operations."""
    print("\n" + "=" * 60)
    print("TEST 3: Query Performance Analysis")
    print("=" * 60)

    # Test: get_all_events
    start = time.perf_counter()
    all_events = db.get_all_events()
    elapsed = time.perf_counter() - start
    audit.add_result(
        "get_all_events()",
        elapsed < 5.0,
        f"Retrieved {len(all_events)} events in {elapsed:.4f}s"
    )
    audit.add_metric("query_get_all_events", round(elapsed * 1000, 2), "ms")

    # Test: get_events_by_function
    start = time.perf_counter()
    for func in FUNCTION_NAMES[:5]:
        db.get_events_by_function(func)
    elapsed = time.perf_counter() - start
    avg = elapsed / 5
    audit.add_result(
        "get_events_by_function() (5 queries)",
        avg < 1.0,
        f"Avg: {avg*1000:.2f}ms per query"
    )
    audit.add_metric("query_by_function_avg", round(avg * 1000, 2), "ms")

    # Test: get_events_by_type
    start = time.perf_counter()
    for event_type in EVENT_TYPES:
        db.get_events_by_type(event_type)
    elapsed = time.perf_counter() - start
    avg = elapsed / len(EVENT_TYPES)
    audit.add_result(
        "get_events_by_type() (4 queries)",
        avg < 1.0,
        f"Avg: {avg*1000:.2f}ms per query"
    )
    audit.add_metric("query_by_type_avg", round(avg * 1000, 2), "ms")

    # Test: search_events
    start = time.perf_counter()
    results = db.search_events("result")
    elapsed = time.perf_counter() - start
    audit.add_result(
        "search_events() with LIKE",
        elapsed < 2.0,
        f"Found {len(results)} matching events in {elapsed*1000:.2f}ms"
    )
    audit.add_metric("query_search_events", round(elapsed * 1000, 2), "ms")

    # Test: get_events_in_range
    start = time.perf_counter()
    db.get_events_in_range(1, 2500)
    elapsed = time.perf_counter() - start
    audit.add_result(
        "get_events_in_range(1, 2500)",
        elapsed < 2.0,
        f"Retrieved range in {elapsed*1000:.2f}ms"
    )
    audit.add_metric("query_range", round(elapsed * 1000, 2), "ms")

    # Test: get_latest_events
    start = time.perf_counter()
    for _ in range(100):
        db.get_latest_events(10)
    elapsed = time.perf_counter() - start
    avg = elapsed / 100
    audit.add_result(
        "get_latest_events(10) x100",
        avg < 0.1,
        f"Avg: {avg*1000:.3f}ms per query"
    )
    audit.add_metric("query_latest_events_avg", round(avg * 1000, 3), "ms")

    # Test: get_execution_summary
    start = time.perf_counter()
    summary = db.get_execution_summary()
    elapsed = time.perf_counter() - start
    audit.add_result(
        "get_execution_summary()",
        elapsed < 2.0,
        f"Computed summary in {elapsed*1000:.2f}ms"
    )
    audit.add_metric("query_execution_summary", round(elapsed * 1000, 2), "ms")


def test_batch_insert_performance(audit):
    """Test 4: Compare batch insert with transaction optimization."""
    print("\n" + "=" * 60)
    print("TEST 4: Batch Insert Performance (Transaction Optimization)")
    print("=" * 60)

    results_by_batch = {}

    for batch_size in BATCH_SIZES:
        # Create a fresh DB for each batch test
        batch_db_path = os.path.join(os.path.dirname(__file__), f"batch_test_{batch_size}.db")
        if os.path.exists(batch_db_path):
            os.remove(batch_db_path)

        db = Database(batch_db_path)
        db.create_table()

        # Generate events
        events = [generate_event() for _ in range(batch_size)]

        # Method 1: Individual commits (current approach)
        start = time.perf_counter()
        for event in events:
            db.insert_event(
                event["event"], event["function"],
                event["file"], event["line"], event["variables"]
            )
        individual_time = time.perf_counter() - start

        db.clear_events()

        # Method 2: Single transaction (optimized)
        start = time.perf_counter()
        db.cursor.execute("BEGIN TRANSACTION")
        for event in events:
            db.cursor.execute("""
                INSERT INTO events(event, function, file, line, variables, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event["event"], event["function"], event["file"],
                  event["line"], event["variables"], datetime.now().isoformat()))
        db.conn.commit()
        batch_time = time.perf_counter() - start

        speedup = individual_time / batch_time if batch_time > 0 else 0
        results_by_batch[batch_size] = {
            "individual": individual_time,
            "batched": batch_time,
            "speedup": speedup
        }

        audit.add_result(
            f"Batch {batch_size}: individual vs transaction",
            True,
            f"Individual: {individual_time:.3f}s | Batched: {batch_time:.3f}s | Speedup: {speedup:.1f}x"
        )

        db.close()
        os.remove(batch_db_path)

    # Record best speedup
    best_batch = max(results_by_batch.keys())
    audit.add_metric(
        "batch_transaction_speedup",
        round(results_by_batch[best_batch]["speedup"], 1),
        f"x (at {best_batch} events)"
    )


def test_database_size_and_scaling(db, audit):
    """Test 5: Check database size and verify it scales reasonably."""
    print("\n" + "=" * 60)
    print("TEST 5: Database Size & Scaling Analysis")
    print("=" * 60)

    info = db.database_info()
    file_size = os.path.getsize(AUDIT_DB)
    row_count = db.get_event_count()

    bytes_per_row = file_size / row_count if row_count > 0 else 0

    audit.add_result(
        "Database file exists and has content",
        file_size > 0,
        f"Size: {file_size:,} bytes ({file_size/1024:.1f} KB)"
    )
    audit.add_result(
        "Storage efficiency",
        bytes_per_row < 1000,  # Should be well under 1KB per row
        f"{bytes_per_row:.1f} bytes per event record"
    )
    audit.add_metric("db_file_size_kb", round(file_size / 1024, 2), "KB")
    audit.add_metric("bytes_per_row", round(bytes_per_row, 1), "bytes")
    audit.add_metric("total_rows", row_count, "rows")

    # Test: Projected size at 100k events
    projected_100k = (bytes_per_row * 100000) / (1024 * 1024)
    audit.add_result(
        "Projected size at 100k events",
        projected_100k < 500,  # Under 500MB
        f"~{projected_100k:.1f} MB"
    )
    audit.add_metric("projected_size_100k", round(projected_100k, 1), "MB")


def test_concurrent_read_write(audit):
    """Test 6: Simulate concurrent-like read/write patterns."""
    print("\n" + "=" * 60)
    print("TEST 6: Read/Write Interleaving Stress Test")
    print("=" * 60)

    rw_db_path = os.path.join(os.path.dirname(__file__), "rw_stress_test.db")
    if os.path.exists(rw_db_path):
        os.remove(rw_db_path)

    db = Database(rw_db_path)
    db.create_table()

    # Interleave writes and reads rapidly
    write_times = []
    read_times = []
    errors = 0

    for i in range(1000):
        event = generate_event()

        # Write
        try:
            start = time.perf_counter()
            db.insert_event(
                event["event"], event["function"],
                event["file"], event["line"], event["variables"]
            )
            write_times.append(time.perf_counter() - start)
        except Exception as e:
            errors += 1

        # Read after every 10 writes
        if i % 10 == 0:
            try:
                start = time.perf_counter()
                db.get_latest_events(5)
                read_times.append(time.perf_counter() - start)
            except Exception as e:
                errors += 1

    avg_write = statistics.mean(write_times) * 1000
    avg_read = statistics.mean(read_times) * 1000
    p99_write = sorted(write_times)[int(len(write_times) * 0.99)] * 1000

    audit.add_result(
        "Interleaved R/W (1000 writes, 100 reads)",
        errors == 0,
        f"Errors: {errors} | Avg write: {avg_write:.3f}ms | Avg read: {avg_read:.3f}ms"
    )
    audit.add_result(
        "Write latency P99",
        p99_write < 100,
        f"P99: {p99_write:.3f}ms"
    )
    audit.add_metric("rw_avg_write_ms", round(avg_write, 3), "ms")
    audit.add_metric("rw_avg_read_ms", round(avg_read, 3), "ms")
    audit.add_metric("rw_p99_write_ms", round(p99_write, 3), "ms")

    db.close()
    os.remove(rw_db_path)


def test_data_types_and_edge_cases(audit):
    """Test 7: Verify storage of edge-case data."""
    print("\n" + "=" * 60)
    print("TEST 7: Edge Cases & Data Type Handling")
    print("=" * 60)

    edge_db_path = os.path.join(os.path.dirname(__file__), "edge_case_test.db")
    if os.path.exists(edge_db_path):
        os.remove(edge_db_path)

    db = Database(edge_db_path)
    db.create_table()

    edge_cases = [
        # Empty variables
        ("call", "empty_func", "test.py", 1, "{}"),
        # Very long variable string
        ("line", "long_vars", "test.py", 50, str({"x": "A" * 5000})),
        # Special characters in function name
        ("call", "<module>", "<stdin>", 1, "{'__name__': '__main__'}"),
        # Unicode in variables
        ("line", "unicode_func", "test.py", 10, "{'msg': 'Hello 世界 🌍'}"),
        # Very large line number
        ("line", "big_file", "huge.py", 99999, "{'i': 99999}"),
        # Nested dict in variables
        ("return", "nested", "test.py", 20, str({"a": {"b": {"c": [1, 2, 3]}}})),
        # SQL-injection-like content in variables
        ("line", "sql_test", "test.py", 5, "{'q': \"'; DROP TABLE events; --\"}"),
        # Empty string function name
        ("call", "", "test.py", 1, "{}"),
        # Very long file path
        ("line", "deep", "a/" * 100 + "test.py", 1, "{'depth': 100}"),
    ]

    # Insert all edge cases
    insert_errors = 0
    for case in edge_cases:
        try:
            db.insert_event(*case)
        except Exception as e:
            insert_errors += 1
            audit.add_error(f"Edge case insert: {case[1]}", e)

    audit.add_result(
        "All edge cases inserted without error",
        insert_errors == 0,
        f"{len(edge_cases)} cases, {insert_errors} errors"
    )

    # Verify retrieval
    all_events = db.get_all_events()
    audit.add_result(
        "All edge case records retrievable",
        len(all_events) == len(edge_cases),
        f"Expected {len(edge_cases)}, got {len(all_events)}"
    )

    # Verify data wasn't corrupted
    for i, case in enumerate(edge_cases):
        stored = all_events[i]
        if stored[1] != case[0] or stored[5] != case[4]:
            audit.add_result(
                f"Edge case '{case[1]}' data integrity",
                False,
                f"Data mismatch on retrieval"
            )
            break
    else:
        audit.add_result(
            "Edge case data integrity (all records)",
            True,
            "All edge case data matches on retrieval"
        )

    db.close()
    os.remove(edge_db_path)


def test_index_performance(audit):
    """Test 8: Measure impact of adding indexes."""
    print("\n" + "=" * 60)
    print("TEST 8: Index Performance Impact")
    print("=" * 60)

    idx_db_path = os.path.join(os.path.dirname(__file__), "index_test.db")
    if os.path.exists(idx_db_path):
        os.remove(idx_db_path)

    db = Database(idx_db_path)
    db.create_table()

    # Insert 3000 events for testing
    events = [generate_event() for _ in range(3000)]
    db.cursor.execute("BEGIN TRANSACTION")
    for event in events:
        db.cursor.execute("""
            INSERT INTO events(event, function, file, line, variables, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event["event"], event["function"], event["file"],
              event["line"], event["variables"], datetime.now().isoformat()))
    db.conn.commit()

    # Query WITHOUT indexes
    queries_no_index = []
    for _ in range(50):
        func = random.choice(FUNCTION_NAMES)
        start = time.perf_counter()
        db.get_events_by_function(func)
        queries_no_index.append(time.perf_counter() - start)

    avg_no_index = statistics.mean(queries_no_index) * 1000

    # Add indexes
    db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_event ON events(event)")
    db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_function ON events(function)")
    db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_file ON events(file)")
    db.cursor.execute("CREATE INDEX IF NOT EXISTS idx_line ON events(line)")
    db.conn.commit()

    # Query WITH indexes
    queries_with_index = []
    for _ in range(50):
        func = random.choice(FUNCTION_NAMES)
        start = time.perf_counter()
        db.get_events_by_function(func)
        queries_with_index.append(time.perf_counter() - start)

    avg_with_index = statistics.mean(queries_with_index) * 1000
    improvement = ((avg_no_index - avg_with_index) / avg_no_index * 100) if avg_no_index > 0 else 0

    audit.add_result(
        "Index improves query performance",
        avg_with_index <= avg_no_index * 1.1,  # Allow 10% margin for small datasets
        f"Without index: {avg_no_index:.3f}ms | With index: {avg_with_index:.3f}ms | Improvement: {improvement:.1f}%"
    )
    audit.add_metric("query_no_index_avg_ms", round(avg_no_index, 3), "ms")
    audit.add_metric("query_with_index_avg_ms", round(avg_with_index, 3), "ms")
    audit.add_metric("index_improvement_pct", round(improvement, 1), "%")

    db.close()
    os.remove(idx_db_path)


# --- Main Audit Runner ---
def run_audit():
    """Execute the full storage audit."""
    print("=" * 60)
    print("  PyChronicle Storage Audit")
    print("  Author: Rohit Jain (SQLite Module)")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Events to generate: {NUM_EVENTS:,}")
    print("=" * 60)

    audit = AuditResults()

    # Clean up any previous audit DB
    if os.path.exists(AUDIT_DB):
        try:
            os.remove(AUDIT_DB)
        except PermissionError:
            pass  # Timestamped name ensures uniqueness; ignore if still locked

    # Create audit database
    db = Database(AUDIT_DB)
    db.create_table()

    # Run tests
    events_generated = test_bulk_insert(db, audit)
    test_record_integrity(db, audit, events_generated)
    test_query_performance(db, audit)
    test_batch_insert_performance(audit)
    test_database_size_and_scaling(db, audit)
    test_concurrent_read_write(audit)
    test_data_types_and_edge_cases(audit)
    test_index_performance(audit)

    # Final summary
    summary = audit.summary()
    print("\n" + "=" * 60)
    print("  AUDIT SUMMARY")
    print("=" * 60)
    print(f"  Total Tests:  {summary['total_tests']}")
    print(f"  Passed:       {summary['passed']}")
    print(f"  Failed:       {summary['failed']}")
    print(f"  Errors:       {summary['errors']}")
    print()
    print("  Performance Metrics:")
    print("  " + "-" * 50)
    for name, data in summary["metrics"].items():
        print(f"    {name}: {data['value']} {data['unit']}")

    print()
    print("  Optimization Recommendations:")
    print("  " + "-" * 50)

    # Check if batch optimization is significant
    speedup = summary["metrics"].get("batch_transaction_speedup", {}).get("value", 1)
    if speedup and speedup > 2:
        print(f"    [HIGH] Use transaction batching for bulk inserts ({speedup}x speedup)")
        print(f"           Current: commit per insert | Recommended: batch commit")

    idx_improvement = summary["metrics"].get("index_improvement_pct", {}).get("value", 0)
    if idx_improvement and idx_improvement > 5:
        print(f"    [MED]  Add indexes on event, function, file columns ({idx_improvement:.1f}% faster)")

    bytes_per = summary["metrics"].get("bytes_per_row", {}).get("value", 0)
    if bytes_per and bytes_per > 500:
        print(f"    [LOW]  Consider variable compression (currently {bytes_per:.0f} bytes/row)")

    print()

    # Cleanup
    db.close()
    time.sleep(0.5)  # Allow Windows to release file handle
    try:
        if os.path.exists(AUDIT_DB):
            os.remove(AUDIT_DB)
        print("  Audit complete. Test database cleaned up.")
    except PermissionError:
        print("  Audit complete. (Test DB file retained due to file lock.)")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_audit()
