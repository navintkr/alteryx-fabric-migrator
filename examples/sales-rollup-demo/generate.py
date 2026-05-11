"""Generate synthetic sales-rollup-demo data.

Run with `python examples/sales-rollup-demo/generate.py`. Outputs are written
to `inputs/` and `reference_outputs/` alongside this script.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
HERE = Path(__file__).parent
INPUTS = HERE / "inputs"
REFOUT = HERE / "reference_outputs"
INPUTS.mkdir(exist_ok=True)
REFOUT.mkdir(exist_ok=True)

REGIONS = [
    ("R01", "North",   "USA"),
    ("R02", "South",   "USA"),
    ("R03", "East",    "USA"),
    ("R04", "West",    "USA"),
    ("R05", "Central", "Canada"),
    ("R06", "Pacific", "Canada"),
]
PRODUCTS = [
    ("Widget",   12.50),
    ("Gadget",   29.99),
    ("Sprocket",  4.75),
    ("Cog",       8.25),
]


def main() -> None:
    rng = random.Random(SEED)
    start = date(2024, 1, 1)
    end = date(2024, 12, 31)
    span_days = (end - start).days

    # regions.csv
    with (INPUTS / "regions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["RegionCode", "RegionName", "Country"])
        for r in REGIONS:
            w.writerow(r)

    # sales.csv
    sales = []
    for i in range(1, 501):
        region = rng.choice(REGIONS)[0]
        prod, price = rng.choice(PRODUCTS)
        qty = rng.randint(1, 10)
        d = start + timedelta(days=rng.randint(0, span_days))
        sales.append({
            "OrderID": f"O{i:05d}",
            "RegionCode": region,
            "Product": prod,
            "Quantity": qty,
            "UnitPrice": price,
            "OrderDate": d.isoformat(),
        })

    with (INPUTS / "sales.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sales[0].keys()))
        w.writeheader()
        w.writerows(sales)

    # reference_outputs/quarterly_rollup.csv
    region_lookup = {code: (name, country) for code, name, country in REGIONS}
    agg: dict[tuple, dict] = {}
    for s in sales:
        name, country = region_lookup[s["RegionCode"]]
        d = date.fromisoformat(s["OrderDate"])
        q = f"Q{(d.month - 1) // 3 + 1}-{d.year}"
        key = (country, name, q)
        rec = agg.setdefault(key, {"TotalRevenue": 0.0, "OrderCount": 0})
        rec["TotalRevenue"] += s["Quantity"] * s["UnitPrice"]
        rec["OrderCount"] += 1

    rows = []
    for (country, name, q), v in agg.items():
        rows.append({
            "Country": country, "RegionName": name, "Quarter": q,
            "TotalRevenue": round(v["TotalRevenue"], 2),
            "OrderCount": v["OrderCount"],
        })
    rows.sort(key=lambda r: (r["Country"], r["RegionName"], r["Quarter"]))

    with (REFOUT / "quarterly_rollup.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Country", "RegionName", "Quarter", "TotalRevenue", "OrderCount"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(sales)} sales rows, {len(rows)} aggregated rows.")


if __name__ == "__main__":
    main()
