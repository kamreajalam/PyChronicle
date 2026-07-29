"""Invoice calculation service — tax, discounts, rounding, payment terms.

Includes deliberate failure paths (unknown tax jurisdiction, negative line
totals) so the trace contains genuine `exception` events alongside the
happy-path `call` / `line` / `return` events.
"""

import os
import random

# Real-world VAT / GST / sales-tax rates by jurisdiction.
TAX_TABLE = {
    "DE": 0.19,
    "NL": 0.21,
    "GB": 0.20,
    "IN": 0.18,
    "SG": 0.09,
    "US-CA": 0.0725,
    "US-TX": 0.0625,
    "AE": 0.05,
}

CUSTOMERS = [
    ("Meridian Logistics BV", "NL", "NET30", 0.05),
    ("Halberstadt Werke GmbH", "DE", "NET45", 0.08),
    ("Trent & Fielding Ltd", "GB", "NET15", 0.00),
    ("Kavery Freight Pvt Ltd", "IN", "NET60", 0.12),
    ("Straits Cold Storage Pte", "SG", "NET30", 0.03),
    ("Rio Grande Distributors", "US-TX", "NET30", 0.06),
    ("Pacific Crest Grocers", "US-CA", "NET45", 0.10),
    ("Gulf Marine Supply LLC", "AE", "NET90", 0.02),
]

CATALOGUE = [
    ("SVC-INSTALL", "On-site installation day rate", 850.00),
    ("SVC-SUPPORT", "Priority support, per month", 420.00),
    ("HW-SENSOR", "Cold-chain sensor tag", 12.25),
    ("HW-GATEWAY", "Dock gateway appliance", 655.75),
    ("LIC-PLATFORM", "Platform licence, per seat", 96.00),
    ("SVC-TRAINING", "Operator training, per head", 310.00),
]


def resolve_tax_rate(jurisdiction):
    """Looks up the tax rate, refusing to guess for unknown jurisdictions."""
    if jurisdiction not in TAX_TABLE:
        raise KeyError(f"no tax rate configured for jurisdiction {jurisdiction!r}")
    return TAX_TABLE[jurisdiction]


def build_line_items(rng, count):
    """Creates the billable lines for one invoice."""
    lines = []
    for _ in range(count):
        code, description, unit_price = rng.choice(CATALOGUE)
        quantity = rng.randint(1, 24)
        lines.append({
            "code": code,
            "description": description,
            "unit_price": unit_price,
            "quantity": quantity,
        })
    return lines


def line_subtotal(line):
    """Subtotal for a single line, guarding against corrupt input."""
    subtotal = round(line["unit_price"] * line["quantity"], 2)
    if subtotal < 0:
        raise ArithmeticError(f"negative subtotal on line {line['code']}")
    return subtotal


def apply_volume_discount(subtotal, contract_discount):
    """Contract discount plus an extra tier for large orders."""
    tier_discount = 0.0
    if subtotal > 10000:
        tier_discount = 0.04
    elif subtotal > 5000:
        tier_discount = 0.02

    effective = round(contract_discount + tier_discount, 4)
    discount_value = round(subtotal * effective, 2)
    return round(subtotal - discount_value, 2), effective, discount_value


def calculate_invoice(customer, lines):
    """Full invoice calculation: net, discount, tax, gross."""
    name, jurisdiction, terms, contract_discount = customer

    gross_lines = 0.0
    for line in lines:
        gross_lines = round(gross_lines + line_subtotal(line), 2)

    net_after_discount, effective_discount, discount_value = apply_volume_discount(
        gross_lines, contract_discount
    )

    tax_rate = resolve_tax_rate(jurisdiction)
    tax_value = round(net_after_discount * tax_rate, 2)
    total_due = round(net_after_discount + tax_value, 2)

    return {
        "customer": name,
        "jurisdiction": jurisdiction,
        "payment_terms": terms,
        "line_count": len(lines),
        "gross_lines": gross_lines,
        "discount_rate": effective_discount,
        "discount_value": discount_value,
        "net": net_after_discount,
        "tax_rate": tax_rate,
        "tax_value": tax_value,
        "total_due": total_due,
    }


def summarise_batch(invoices):
    """Aggregates a run of invoices for the finance dashboard."""
    summary = {"count": len(invoices), "net": 0.0, "tax": 0.0, "total": 0.0}
    by_terms = {}
    for invoice in invoices:
        summary["net"] = round(summary["net"] + invoice["net"], 2)
        summary["tax"] = round(summary["tax"] + invoice["tax_value"], 2)
        summary["total"] = round(summary["total"] + invoice["total_due"], 2)
        by_terms[invoice["payment_terms"]] = by_terms.get(invoice["payment_terms"], 0) + 1
    summary["by_payment_terms"] = by_terms
    return summary


def main():
    scale = int(os.environ.get("PYCHRONICLE_SCALE", "8"))
    seed = int(os.environ.get("PYCHRONICLE_SEED", "11"))
    rng = random.Random(seed)

    invoices = []
    failures = 0

    for index in range(scale):
        customer = list(rng.choice(CUSTOMERS))
        # Every few invoices, an unmapped jurisdiction slips through from CRM.
        if index and index % 7 == 0:
            customer[1] = "ZZ"

        lines = build_line_items(rng, rng.randint(1, 5))
        try:
            invoices.append(calculate_invoice(tuple(customer), lines))
        except (KeyError, ArithmeticError):
            failures += 1

    summary = summarise_batch(invoices)
    print(f"invoiced={summary['count']} failed={failures} "
          f"net={summary['net']} tax={summary['tax']} total={summary['total']}")
    print(f"terms_mix={summary['by_payment_terms']}")
    return summary


if __name__ == "__main__":
    main()
