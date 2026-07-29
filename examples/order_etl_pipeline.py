"""Order ingestion ETL — extract, validate, normalise, deduplicate, aggregate.

Traced by PyChronicle to produce realistic pipeline execution timelines.
Workload size comes from PYCHRONICLE_SCALE so the same program can produce a
short trace or a long one.
"""

import os
import random

REGIONS = [
    ("EMEA", "Rotterdam", "NL", "EUR", 0.92),
    ("EMEA", "Frankfurt", "DE", "EUR", 0.92),
    ("EMEA", "Manchester", "GB", "GBP", 0.79),
    ("APAC", "Pune", "IN", "INR", 83.4),
    ("APAC", "Singapore", "SG", "SGD", 1.35),
    ("APAC", "Osaka", "JP", "JPY", 157.2),
    ("AMER", "Memphis", "US", "USD", 1.0),
    ("AMER", "Guadalajara", "MX", "MXN", 17.1),
    ("AMER", "Sao Paulo", "BR", "BRL", 5.4),
]

CHANNELS = ["web-storefront", "mobile-ios", "mobile-android", "partner-api", "edi-batch"]

PRODUCTS = [
    ("SKU-40119", "Thermal receipt printer", 189.00),
    ("SKU-40277", "Barcode scanner ring", 74.50),
    ("SKU-51302", "Cold-chain sensor tag", 12.25),
    ("SKU-51884", "Pallet label roll 4x6", 38.90),
    ("SKU-62015", "Forklift telemetry unit", 1240.00),
    ("SKU-62119", "Dock door controller", 655.75),
]


def build_raw_orders(count, seed):
    """Simulates the extract step: rows as they arrive from upstream systems."""
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        region, city, country, currency, fx_rate = rng.choice(REGIONS)
        sku, description, unit_price = rng.choice(PRODUCTS)
        quantity = rng.randint(1, 40)
        order_id = f"ORD-2025-{100000 + index + seed % 500:06d}"
        rows.append({
            "order_id": order_id,
            "region": region,
            "city": city,
            "country": country,
            "currency": currency,
            "fx_rate": fx_rate,
            "channel": rng.choice(CHANNELS),
            "sku": sku,
            "description": description,
            "unit_price": unit_price,
            "quantity": quantity,
            "captured_at": f"2025-0{rng.randint(1, 9)}-{rng.randint(10, 28)}T"
                           f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:00",
        })
    # Upstream duplicates are a real occurrence, so reproduce them.
    for _ in range(max(1, count // 12)):
        rows.append(dict(rng.choice(rows)))
    return rows


def validate_order(row):
    """Rejects rows that would corrupt downstream aggregates."""
    order_id = row.get("order_id")
    quantity = row.get("quantity", 0)
    unit_price = row.get("unit_price", 0)

    if not order_id or not order_id.startswith("ORD-"):
        raise ValueError(f"malformed order id: {order_id!r}")
    if quantity <= 0:
        raise ValueError(f"non-positive quantity on {order_id}: {quantity}")
    if unit_price <= 0:
        raise ValueError(f"non-positive unit price on {order_id}: {unit_price}")
    return True


def normalise_to_base_currency(row):
    """Converts local currency to USD using the row's FX rate."""
    gross_local = round(row["unit_price"] * row["quantity"], 2)
    fx_rate = row["fx_rate"]
    gross_usd = round(gross_local / fx_rate, 2)
    return {
        "order_id": row["order_id"],
        "region": row["region"],
        "city": row["city"],
        "channel": row["channel"],
        "sku": row["sku"],
        "quantity": row["quantity"],
        "gross_local": gross_local,
        "local_currency": row["currency"],
        "gross_usd": gross_usd,
    }


def deduplicate(records):
    """Keeps the first occurrence of each order id."""
    seen = set()
    unique = []
    duplicates = 0
    for record in records:
        key = record["order_id"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(record)
    return unique, duplicates


def aggregate_by_region(records):
    """Rolls the cleaned rows up into per-region revenue and volume."""
    totals = {}
    for record in records:
        region = record["region"]
        bucket = totals.setdefault(region, {"orders": 0, "units": 0, "revenue_usd": 0.0})
        bucket["orders"] += 1
        bucket["units"] += record["quantity"]
        bucket["revenue_usd"] = round(bucket["revenue_usd"] + record["gross_usd"], 2)
    return totals


def top_skus(records, limit=3):
    """Ranks SKUs by revenue so the pipeline emits a leaderboard too."""
    revenue_by_sku = {}
    for record in records:
        revenue_by_sku[record["sku"]] = round(
            revenue_by_sku.get(record["sku"], 0.0) + record["gross_usd"], 2
        )
    ranked = sorted(revenue_by_sku.items(), key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "12"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "7"))

    raw_rows = build_raw_orders(scale, seed)
    accepted = []
    rejected = 0

    for row in raw_rows:
        try:
            validate_order(row)
        except ValueError:
            rejected += 1
            continue
        accepted.append(normalise_to_base_currency(row))

    unique_records, duplicate_count = deduplicate(accepted)
    region_totals = aggregate_by_region(unique_records)
    leaders = top_skus(unique_records)

    total_revenue = round(sum(b["revenue_usd"] for b in region_totals.values()), 2)
    print(f"ingested={len(raw_rows)} accepted={len(accepted)} "
          f"rejected={rejected} duplicates={duplicate_count}")
    print(f"regions={sorted(region_totals)} revenue_usd={total_revenue}")
    print(f"top_skus={leaders}")
    return region_totals


if __name__ == "__main__":
    main()
