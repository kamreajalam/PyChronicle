"""API gateway simulation — routing, status codes, latency, retries.

Generates the request-flavoured trace data: endpoints, HTTP methods, status
codes (200 / 401 / 404 / 500 / 503), payload sizes, response times, retry
backoff and latency percentiles, all as real traced variables.
"""

import os
import random

ROUTES = [
    ("GET", "/v1/shipments", 220, "shipment-service"),
    ("GET", "/v1/shipments/{id}/events", 180, "shipment-service"),
    ("POST", "/v1/orders", 340, "order-service"),
    ("PATCH", "/v1/orders/{id}", 260, "order-service"),
    ("GET", "/v1/inventory/availability", 150, "inventory-service"),
    ("POST", "/v1/invoices", 410, "billing-service"),
    ("GET", "/v1/reports/throughput", 780, "analytics-service"),
    ("DELETE", "/v1/webhooks/{id}", 120, "integration-service"),
    ("POST", "/v1/auth/token", 95, "auth-service"),
]

USER_AGENTS = [
    "Chrome/141.0 (Windows NT 11.0)",
    "Safari/18.2 (Macintosh; Apple Silicon)",
    "okhttp/4.12.0 (Android 15)",
    "PyChronicle-Agent/1.4 (Debian 12)",
    "curl/8.11.1",
    "Postman/11.18.0",
]

EDGE_LOCATIONS = [
    ("fra1", "Frankfurt", "DE"),
    ("ams1", "Amsterdam", "NL"),
    ("bom1", "Mumbai", "IN"),
    ("sin1", "Singapore", "SG"),
    ("iad1", "Ashburn", "US"),
    ("gru1", "Sao Paulo", "BR"),
]

RETRYABLE = (503, 500)


def source_address(rng):
    return f"{rng.choice([10, 172, 192, 203])}.{rng.randint(0, 254)}." \
           f"{rng.randint(0, 254)}.{rng.randint(1, 254)}"


def classify_status(rng, route):
    """Decides the response status for one request."""
    method, path, base_latency, service = route
    roll = rng.random()

    if roll < 0.80:
        return 200
    if roll < 0.86:
        return 401 if path.endswith("/token") or method != "GET" else 404
    if roll < 0.92:
        return 404
    if roll < 0.97:
        return 500
    return 503


def measure_latency(rng, base_latency, status_code):
    """Latency in milliseconds, inflated for failures and cold paths."""
    jitter = rng.randint(-40, 160)
    latency = base_latency + jitter
    if status_code == 503:
        latency = latency + rng.randint(400, 2200)
    elif status_code == 500:
        latency = latency + rng.randint(120, 900)
    return max(8, latency)


def payload_size(rng, method, status_code):
    """Response payload size in bytes."""
    if status_code >= 400:
        return rng.randint(90, 420)
    if method == "GET":
        return rng.randint(1200, 48000)
    return rng.randint(300, 4200)


def handle_request(rng, route, request_index):
    """Routes one request and returns its access-log record."""
    method, path, base_latency, service = route
    concrete_path = path.replace("{id}", str(rng.randint(100000, 999999)))
    edge_code, edge_city, edge_country = rng.choice(EDGE_LOCATIONS)

    status_code = classify_status(rng, route)
    latency_ms = measure_latency(rng, base_latency, status_code)
    bytes_out = payload_size(rng, method, status_code)

    return {
        "request_id": f"req-{request_index:06d}",
        "method": method,
        "path": concrete_path,
        "upstream": service,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "bytes_out": bytes_out,
        "client_ip": source_address(rng),
        "user_agent": rng.choice(USER_AGENTS),
        "edge": edge_code,
        "edge_city": edge_city,
        "edge_country": edge_country,
    }


def retry_with_backoff(rng, route, request_index, max_attempts=3):
    """Retries a failed request with exponential backoff."""
    attempts = []
    delay_ms = 50
    for attempt in range(1, max_attempts + 1):
        record = handle_request(rng, route, request_index)
        record["attempt"] = attempt
        record["backoff_ms"] = delay_ms
        attempts.append(record)
        if record["status_code"] not in RETRYABLE:
            break
        delay_ms = delay_ms * 2
    return attempts


def percentile(values, fraction):
    """Nearest-rank percentile over the collected latencies."""
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summarise(records):
    """Builds the gateway's rolling metrics window."""
    by_status = {}
    by_upstream = {}
    latencies = []
    total_bytes = 0

    for record in records:
        status = record["status_code"]
        by_status[status] = by_status.get(status, 0) + 1
        by_upstream[record["upstream"]] = by_upstream.get(record["upstream"], 0) + 1
        latencies.append(record["latency_ms"])
        total_bytes += record["bytes_out"]

    error_count = sum(count for status, count in by_status.items() if status >= 500)
    return {
        "requests": len(records),
        "by_status": by_status,
        "by_upstream": by_upstream,
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "egress_bytes": total_bytes,
        "error_rate": round(error_count / max(1, len(records)), 4),
    }


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "14"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "17"))
    rng = random.Random(seed)

    access_log = []
    for request_index in range(scale):
        route = rng.choice(ROUTES)
        first = handle_request(rng, route, request_index)

        if first["status_code"] in RETRYABLE:
            access_log.extend(retry_with_backoff(rng, route, request_index))
        else:
            access_log.append(first)

    metrics = summarise(access_log)
    print(f"requests={metrics['requests']} statuses={metrics['by_status']}")
    print(f"p50={metrics['p50_ms']}ms p95={metrics['p95_ms']}ms "
          f"p99={metrics['p99_ms']}ms error_rate={metrics['error_rate']}")
    return metrics


if __name__ == "__main__":
    main()
