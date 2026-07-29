"""Populate the PyChronicle database with a large, realistic trace history.

    python tools/seed_database.py                 # seed up to the default target
    python tools/seed_database.py --target 25000  # seed more events
    python tools/seed_database.py --reset         # rebuild from scratch (destructive)
    python tools/seed_database.py --dry-run       # show the plan, write nothing

How this differs from generating rows with INSERT statements: every event here
is produced by actually running the programs in examples/ under the real
tracer. So each row's file path, line number, function name, variable snapshot
and variable diff are genuine execution data. That matters because

  * the UI's source viewer opens the traced file from disk and highlights the
    recorded line — fabricated paths and line numbers would show
    "source not available" or point at the wrong code;
  * the variable diffs have to be internally consistent with the snapshots for
    the diff inspector to make sense.

Only the timestamps are synthetic: a trace can only be recorded "now", so each
session is retimed afterwards onto a chosen point in the last three years to
give the timeline, charts and date filters a realistic history to work with.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACER_DIR = os.path.join(ROOT, "src", "tracer")
sys.path.insert(0, TRACER_DIR)

from config import get_db_path          # noqa: E402
from database import Database           # noqa: E402
from tracer import Tracer               # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples")

# Default volume: enough sessions for the history to look like a real run log,
# and comfortably more than the 10,000 timeline events the review asks for.
# The ceiling keeps the shipped .db file small enough to hand over.
# Measured cost is ~950 bytes per event row (JSON variable snapshot plus its
# diff), so 60 sessions lands around 16,000 events / ~16 MB: well past the
# 10,000 timeline events the review asks for, while still small enough to hand
# the .db file to a teammate. Raise --sessions for a bigger history.
DEFAULT_SESSIONS = 60
DEFAULT_MAX_EVENTS = 20000

# Three years of history, ending today.
HISTORY_YEARS = 3


# ---------------------------------------------------------------------------
# Workload catalogue
# ---------------------------------------------------------------------------
# Each entry is a real program in examples/ plus the shape of the jobs that
# "run" it. `scales` feed PYCHRONICLE_SCALE, which sizes each program's
# workload and therefore how many events its trace produces.

# `scales` are given per size class. The event counts in the comments were
# measured with tools/_calibrate-style trial runs, so the planner can predict
# roughly how big the database will get before it writes anything.
WORKLOADS = [
    {
        "script": "order_etl_pipeline.py",
        "pipeline": "nightly-order-etl",
        "environments": ["prod", "prod", "staging", "ci"],
        "scales": {"small": 1, "medium": 6, "large": 20},   # ~130 / 506 / 1405
        "window": "batch",          # runs overnight
        "weight": 6,
    },
    {
        "script": "invoice_service.py",
        "pipeline": "billing-invoice-run",
        "environments": ["prod", "prod", "staging"],
        "scales": {"small": 1, "medium": 5, "large": 14},   # ~150 / 574 / 1455
        "window": "batch",
        "weight": 5,
    },
    {
        "script": "auth_service.py",
        "pipeline": "auth-regression-sweep",
        "environments": ["ci", "ci", "staging", "prod"],
        "scales": {"small": 1, "medium": 8, "large": 20},   # ~90 / 465 / 1131
        "window": "business",
        "weight": 5,
    },
    {
        "script": "api_gateway_sim.py",
        "pipeline": "gateway-load-probe",
        "environments": ["prod", "staging", "ci"],
        "scales": {"small": 1, "medium": 6, "large": 16},   # ~110 / 403 / 1071
        "window": "any",            # synthetic monitoring runs around the clock
        "weight": 6,
    },
    {
        "script": "inventory_planner.py",
        "pipeline": "replenishment-planner",
        "environments": ["prod", "prod", "staging"],
        "scales": {"small": 1, "medium": 2, "large": 5},    # 1112 / 2463 / 8192
        "window": "batch",
        "weight": 1,                # heaviest workload, so it runs rarely
    },
    {
        "script": "recommendation_engine.py",
        "pipeline": "recommender-rebuild",
        "environments": ["prod", "staging", "ci"],
        "scales": {"small": 1, "medium": 3, "large": 5},    # ~400 / 1565 / 3272
        "window": "business",
        "weight": 2,
    },
    {
        "script": "sample_program.py",
        "pipeline": "smoke-check",
        "environments": ["ci"],
        "scales": {"small": 1, "medium": 1, "large": 1},    # 113
        "window": "any",
        "weight": 7,                # cheapest and most frequent, like real CI
    },
]

TRIGGERS = ["scheduler", "scheduler", "scheduler", "manual", "webhook", "ci-pipeline"]

# Most real runs are small smoke/CI runs; full batch jobs are the minority.
SIZE_CLASSES = (["small"] * 78) + (["medium"] * 18) + (["large"] * 4)

# --heavy flips the mix toward full batch runs. Reaching a very large event
# count with the default mix would need thousands of tiny sessions, which makes
# the session list unusable; heavy runs get there with far fewer, bigger ones.
HEAVY_SIZE_CLASSES = (["small"] * 15) + (["medium"] * 40) + (["large"] * 45)

# --compact tightens the variable-snapshot bounds the tracer applies. Row cost
# is dominated by the JSON snapshot and its diff, so this is the lever that
# decides how big the file gets at high event counts.
COMPACT_LIMITS = {
    "PYCHRONICLE_MAX_STR": "60",
    "PYCHRONICLE_MAX_ITEMS": "3",
    "PYCHRONICLE_MAX_DEPTH": "2",
}


def build_choice_pool():
    """Expand the weights into a flat list the sampler can pick from."""
    pool = []
    for workload in WORKLOADS:
        pool.extend([workload] * workload["weight"])
    return pool


# ---------------------------------------------------------------------------
# Realistic scheduling
# ---------------------------------------------------------------------------

def pick_start_time(rng, window, now):
    """Choose a plausible wall-clock start time within the last N years.

    Recent activity is denser than old activity (u ** 1.7 skews toward zero
    days ago), which is what a real project's history looks like.
    """
    total_days = int(365.25 * HISTORY_YEARS)
    days_ago = int((rng.random() ** 1.7) * total_days)
    day = now - timedelta(days=days_ago)

    # Weekend runs happen, but far less often for interactive workloads.
    if day.weekday() >= 5 and window == "business" and rng.random() < 0.8:
        day = day - timedelta(days=rng.randint(1, 2))

    if window == "batch":
        hour = rng.choice([0, 1, 1, 2, 2, 3, 4, 22, 23])
    elif window == "business":
        hour = rng.choice([8, 9, 10, 10, 11, 13, 14, 15, 16, 16, 17, 18])
    else:
        hour = rng.randint(0, 23)

    return day.replace(
        hour=hour,
        minute=rng.randint(0, 59),
        second=rng.randint(0, 59),
        microsecond=rng.randint(0, 999999),
    )


def session_duration(rng, event_count):
    """Plausible wall-clock duration for a run of this size, in seconds."""
    per_event_ms = rng.uniform(0.6, 3.4)
    overhead = rng.uniform(0.4, 6.0)
    return round((event_count * per_event_ms) / 1000.0 + overhead, 3)


def build_plan(rng, session_count, now, heavy=False):
    """Decide the sessions to record before any tracing happens.

    Planning is driven by the number of sessions rather than by an event
    target, because the history has to look like a project's real run log:
    many small runs, fewer big ones, spread across three years. The actual
    event counts come from tracing.
    """
    pool = build_choice_pool()
    size_classes = HEAVY_SIZE_CLASSES if heavy else SIZE_CLASSES
    run_counters = {}
    plan = []

    for _ in range(session_count):
        workload = rng.choice(pool)
        script = workload["script"]
        size_class = rng.choice(size_classes)
        scale = workload["scales"][size_class]
        environment = rng.choice(workload["environments"])

        run_counters[script] = run_counters.get(script, 0) + 1
        run_number = 400 + run_counters[script] * rng.randint(1, 3)

        started_at = pick_start_time(rng, workload["window"], now)
        name = (f"{workload['pipeline']} #{run_number} "
                f"({environment}) {started_at.strftime('%Y-%m-%d %H:%M')}")

        plan.append({
            "script": script,
            "path": os.path.join(EXAMPLES, script),
            "name": name,
            "pipeline": workload["pipeline"],
            "environment": environment,
            "size_class": size_class,
            "scale": scale,
            "seed": rng.randint(1, 10_000_000),
            "trigger": rng.choice(TRIGGERS),
            "started_at": started_at,
        })

    # Record oldest first so session ids climb with time, the way they would
    # if these runs had happened in sequence.
    plan.sort(key=lambda item: item["started_at"])
    return plan


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def seed(session_count, max_events, seed_value, reset, dry_run,
         heavy=False, compact=False, max_bytes=None):
    db_path = get_db_path()
    rng = random.Random(seed_value)
    now = datetime.now()

    if compact:
        # Applied before any tracing so the tracer picks them up.
        os.environ.update(COMPACT_LIMITS)
        print("compact payloads: " + ", ".join(
            f"{k.replace('PYCHRONICLE_', '').lower()}={v}"
            for k, v in COMPACT_LIMITS.items()))

    if reset and not dry_run:
        for suffix in ("", "-wal", "-shm"):
            candidate = db_path + suffix
            if os.path.exists(candidate):
                os.remove(candidate)
        print(f"reset: removed {os.path.basename(db_path)}")

    plan = build_plan(rng, session_count, now, heavy=heavy)
    print(f"database      : {db_path}")
    print(f"planned runs  : {len(plan)} sessions"
          f"{' (heavy mix)' if heavy else ''}")
    print(f"event ceiling : {max_events:,} (stops early if exceeded)")
    if max_bytes:
        print(f"size ceiling  : {max_bytes / 1e9:.2f} GB (stops early if exceeded)")
    print(f"history window: {plan[0]['started_at'].date()} .. "
          f"{plan[-1]['started_at'].date()}")

    if dry_run:
        print("\n-- dry run, nothing written --")
        by_script = {}
        by_class = {}
        for item in plan:
            by_script[item["script"]] = by_script.get(item["script"], 0) + 1
            by_class[item["size_class"]] = by_class.get(item["size_class"], 0) + 1
        for script, count in sorted(by_script.items()):
            print(f"  {count:>4} sessions  {script}")
        print(f"  size mix: {by_class}")
        return 0

    baseline = Database(db_path)
    baseline.create_table()
    events_before = baseline.get_event_count()
    sessions_before = len(baseline.get_all_sessions())
    baseline.close()

    tracer = Tracer(db_path=db_path, verbose=False)
    recorded = 0
    failures = 0
    largest = (None, 0)
    started = datetime.now()

    print(f"\nrecording (existing rows: {events_before:,})")
    for index, item in enumerate(plan, start=1):
        # The example programs read these to size their workload.
        os.environ["PYCHRONICLE_SCALE"] = str(item["scale"])
        os.environ["PYCHRONICLE_SEED"] = str(item["seed"])

        try:
            session_id, count = tracer.trace_file(item["path"],
                                                  session_name=item["name"])
        except Exception as exc:                      # keep seeding on failure
            failures += 1
            print(f"  [{index:>3}] FAILED {item['script']}: "
                  f"{type(exc).__name__}: {exc}")
            continue

        # Shift this session onto its historical slot.
        duration = session_duration(rng, count)
        tracer.db.retime_session(session_id, item["started_at"],
                                 duration_seconds=duration, rng=rng)

        recorded += count
        if count > largest[1]:
            largest = (item["name"], count)

        if index % 10 == 0 or index == len(plan):
            elapsed = (datetime.now() - started).total_seconds()
            rate = recorded / elapsed if elapsed else 0
            print(f"  [{index:>3}/{len(plan)}] {recorded:>7,} events "
                  f"({rate:,.0f}/s) last: {item['script']} scale={item['scale']}")

        if recorded >= max_events:
            print(f"  event ceiling reached after {index} sessions")
            break

        # Size ceiling: checked periodically so a large seed cannot quietly
        # fill the disk. Committed pages are what count, so checkpoint first.
        if max_bytes and index % 10 == 0:
            tracer.db.checkpoint()
            current = os.path.getsize(db_path)
            if current >= max_bytes:
                print(f"  size ceiling reached after {index} sessions "
                      f"({current / 1e9:.2f} GB)")
                break

    # Session bookkeeping, then compact and fold the WAL into the .db file.
    tracer.db.refresh_session_counts()
    tracer.db.prune_empty_sessions()
    tracer.db.vacuum()
    tracer.db.checkpoint()

    events_after = tracer.db.get_event_count()
    sessions_after = len(tracer.db.get_all_sessions())
    ast_files = len(tracer.db.get_all_ast_files())
    elapsed = (datetime.now() - started).total_seconds()

    print("\n" + "=" * 64)
    print("SEED COMPLETE")
    print("=" * 64)
    print(f"events written   : {recorded:,} in {elapsed:.1f}s "
          f"({recorded / elapsed:,.0f}/s)")
    print(f"events total     : {events_before:,} -> {events_after:,}")
    print(f"sessions total   : {sessions_before:,} -> {sessions_after:,}")
    print(f"AST files stored : {ast_files}")
    print(f"largest session  : {largest[1]:,} events ({largest[0]})")
    print(f"failed runs      : {failures}")
    print(f"database size    : {os.path.getsize(db_path):,} bytes")

    histogram = tracer.db.get_timeline_histogram("month")
    if histogram:
        print(f"months covered   : {len(histogram)} "
              f"({histogram[0][0]} .. {histogram[-1][0]})")

    tracer.close()
    return 0 if events_after > 0 and failures == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Populate PyChronicle with a large, realistic trace history."
    )
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS,
                        help=f"trace sessions to record (default {DEFAULT_SESSIONS})")
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS,
                        help=f"stop early past this many events "
                             f"(default {DEFAULT_MAX_EVENTS})")
    parser.add_argument("--seed", type=int, default=20260729,
                        help="RNG seed, so a run is reproducible")
    parser.add_argument("--reset", action="store_true",
                        help="delete the database first (destructive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan without writing anything")
    parser.add_argument("--heavy", action="store_true",
                        help="favour large batch runs, so a big event count "
                             "needs far fewer sessions")
    parser.add_argument("--compact", action="store_true",
                        help="tighter variable snapshots, roughly a third of "
                             "the bytes per row")
    parser.add_argument("--max-gb", type=float, default=None,
                        help="stop once the database reaches this size in GB")
    args = parser.parse_args()

    max_bytes = int(args.max_gb * 1e9) if args.max_gb else None
    return seed(args.sessions, args.max_events, args.seed,
                args.reset, args.dry_run, heavy=args.heavy,
                compact=args.compact, max_bytes=max_bytes)


if __name__ == "__main__":
    sys.exit(main())
