"""Generate the deterministic input used by the open table formats lab."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


OUTPUT = Path(__file__).with_name("orders.csv")
COUNTRIES = ("US", "CA", "GB", "DE", "NG")
PRODUCTS = ("P-100", "P-200", "P-300", "P-400", "P-500", "P-600")
STATUSES = ("PAID", "SHIPPED", "DELIVERED", "PENDING")
PRICES = tuple(Decimal(value) for value in ("12.50", "19.95", "27.40", "45.00", "63.75"))


def rows() -> list[dict[str, str | int]]:
    generated: list[dict[str, str | int]] = []
    start = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)

    for offset in range(100):
        order_id = 1001 + offset
        quantity = 1 + (offset % 4)
        unit_price = PRICES[(offset * 3) % len(PRICES)]
        status = (
            "PENDING"
            if offset < 5
            else "PAID"
            if offset < 8
            else STATUSES[(offset * 7) % len(STATUSES)]
        )
        generated.append(
            {
                "order_id": order_id,
                "customer_id": f"C-{201 + ((offset * 17) % 43):03d}",
                "order_timestamp": (start + timedelta(hours=offset * 6)).isoformat().replace(
                    "+00:00", "Z"
                ),
                "country": COUNTRIES[(offset * 3) % len(COUNTRIES)],
                "product_id": PRODUCTS[(offset * 5) % len(PRODUCTS)],
                "quantity": quantity,
                "unit_price": f"{unit_price:.2f}",
                "total_amount": f"{unit_price * quantity:.2f}",
                "status": status,
            }
        )

    return generated


def main() -> None:
    fieldnames = [
        "order_id",
        "customer_id",
        "order_timestamp",
        "country",
        "product_id",
        "quantity",
        "unit_price",
        "total_amount",
        "status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows())
    print(f"Generated {len(rows())} deterministic orders at {OUTPUT}")


if __name__ == "__main__":
    main()
