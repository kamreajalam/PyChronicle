"""Inventory replenishment planner — safety stock, reorder points, backorders.

Nested loops over warehouses and SKUs, so this program is the one that
produces the long trace sessions used to exercise timeline pagination.
"""

import os
import random

WAREHOUSES = [
    ("WH-RTM", "Rotterdam", "NL", 3, 0.97),
    ("WH-BOM", "Mumbai", "IN", 7, 0.93),
    ("WH-MEM", "Memphis", "US", 2, 0.98),
    ("WH-SIN", "Singapore", "SG", 5, 0.95),
    ("WH-GDL", "Guadalajara", "MX", 6, 0.91),
]

# (sku, description, units_on_hand, weekly_demand_mean)
# On-hand levels are deliberately mixed: some lines sit comfortably above
# their reorder point, others are short, so the plan contains both outcomes.
SKUS = [
    ("SKU-40119", "Thermal receipt printer", 6, 12),
    ("SKU-40277", "Barcode scanner ring", 130, 30),
    ("SKU-51302", "Cold-chain sensor tag", 90, 200),
    ("SKU-51884", "Pallet label roll 4x6", 610, 150),
    ("SKU-62015", "Forklift telemetry unit", 3, 4),
    ("SKU-62119", "Dock door controller", 27, 6),
    ("SKU-70441", "RF handheld cradle", 14, 20),
]

SERVICE_FACTORS = {0.91: 1.34, 0.93: 1.48, 0.95: 1.65, 0.97: 1.88, 0.98: 2.05}


def daily_demand(rng, weekly_mean):
    """Draws a plausible day of demand around the weekly mean."""
    mean_per_day = weekly_mean / 7
    variation = rng.uniform(-0.35, 0.45)
    return max(0, round(mean_per_day * (1 + variation), 2))


def demand_series(rng, weekly_mean, days):
    """Builds a demand history the planner can measure variability from."""
    series = []
    for _ in range(days):
        series.append(daily_demand(rng, weekly_mean))
    return series


def mean(values):
    return round(sum(values) / len(values), 3) if values else 0.0


def standard_deviation(values):
    if len(values) < 2:
        return 0.0
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
    return round(variance ** 0.5, 3)


def safety_stock(std_dev, lead_time_days, service_factor):
    """Classic safety-stock formula: z * sigma * sqrt(lead time)."""
    return round(service_factor * std_dev * (lead_time_days ** 0.5), 2)


def reorder_point(avg_daily_demand, lead_time_days, buffer_units):
    """Reorder point = expected demand over lead time + safety stock."""
    return round(avg_daily_demand * lead_time_days + buffer_units, 2)


def plan_sku(rng, warehouse, sku, days):
    """Produces the replenishment plan for one warehouse/SKU pair."""
    code, city, country, lead_time_days, service_level = warehouse
    sku_code, description, on_hand, weekly_mean = sku

    history = demand_series(rng, weekly_mean, days)
    avg_daily = mean(history)
    std_dev = standard_deviation(history)
    service_factor = SERVICE_FACTORS.get(service_level, 1.65)

    buffer_units = safety_stock(std_dev, lead_time_days, service_factor)
    trigger = reorder_point(avg_daily, lead_time_days, buffer_units)

    position = on_hand - round(avg_daily * 2, 2)
    shortfall = round(max(0.0, trigger - position), 2)
    suggested_order = round(shortfall + avg_daily * 7, 2) if shortfall else 0.0

    return {
        "warehouse": code,
        "city": city,
        "country": country,
        "sku": sku_code,
        "description": description,
        "on_hand": on_hand,
        "avg_daily_demand": avg_daily,
        "demand_std_dev": std_dev,
        "lead_time_days": lead_time_days,
        "safety_stock": buffer_units,
        "reorder_point": trigger,
        "inventory_position": position,
        "shortfall": shortfall,
        "suggested_order_qty": suggested_order,
        "status": "reorder" if shortfall else "healthy",
    }


def summarise_plan(plans):
    """Aggregates the plan into the numbers a planner actually reads."""
    reorders = [plan for plan in plans if plan["status"] == "reorder"]
    by_warehouse = {}
    for plan in plans:
        bucket = by_warehouse.setdefault(
            plan["warehouse"], {"lines": 0, "reorders": 0, "units": 0.0}
        )
        bucket["lines"] += 1
        if plan["status"] == "reorder":
            bucket["reorders"] += 1
            bucket["units"] = round(bucket["units"] + plan["suggested_order_qty"], 2)
    return {
        "lines": len(plans),
        "reorder_lines": len(reorders),
        "by_warehouse": by_warehouse,
    }


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "3"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "23"))
    rng = random.Random(seed)

    # scale controls how many warehouses and how much demand history to walk,
    # which is what makes this program's trace long.
    warehouses = WAREHOUSES[:max(1, min(len(WAREHOUSES), scale))]
    days = 7 + scale * 2

    plans = []
    for warehouse in warehouses:
        for sku in SKUS:
            plans.append(plan_sku(rng, warehouse, sku, days))

    summary = summarise_plan(plans)
    print(f"planned_lines={summary['lines']} reorders={summary['reorder_lines']}")
    for code, bucket in summary["by_warehouse"].items():
        print(f"  {code}: {bucket['reorders']}/{bucket['lines']} lines, "
              f"{bucket['units']} units suggested")
    return summary


if __name__ == "__main__":
    main()
