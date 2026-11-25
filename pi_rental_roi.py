import requests
import os
import statistics
from datetime import datetime, timezone

API_KEY = os.environ.get("TORN_API_KEY") or input("Enter your Torn API key: ").strip()
PROPERTY_ID = 13  # Private Island
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "pi_rental_roi.md")

BASE_URL = "https://api.torn.com/v2"
HEADERS = {"User-Agent": "curl/8.0"}  # Torn's WAF blocks the default python-requests UA


def fetch(path, extra_params=""):
    url = f"{BASE_URL}/{path}?key={API_KEY}{extra_params}"
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_all_listings(path, response_key):
    listings = []
    offset = 0
    while True:
        data = fetch(f"market/{PROPERTY_ID}/{path}", f"&limit=100&offset={offset}")
        page = data[response_key]["listings"]
        listings.extend(page)
        if not page or not data["_metadata"]["links"]["next"]:
            break
        offset += 100
    return listings


def get_upkeep():
    data = fetch("torn/properties")
    private_island = next(p for p in data["properties"] if p["id"] == PROPERTY_ID)
    return private_island["upkeep"]


def bundle_key(modifications):
    return frozenset(modifications)


def compute_roi(rentals, sales, upkeep):
    period_100 = [listing for listing in rentals if listing["rental_period"] == 100]

    sale_prices_by_bundle = {}
    for listing in sales:
        sale_prices_by_bundle.setdefault(bundle_key(listing["modifications"]), []).append(listing["cost"])
    sale_median_by_bundle = {k: statistics.median(v) for k, v in sale_prices_by_bundle.items()}

    listings_by_bundle = {}
    for listing in period_100:
        listings_by_bundle.setdefault(bundle_key(listing["modifications"]), []).append(listing)

    rows = []
    for mods, listings in listings_by_bundle.items():
        cheapest = min(listings, key=lambda l: l["cost_per_day"])
        net_per_day = cheapest["cost_per_day"] - upkeep
        sale_price = sale_median_by_bundle.get(mods)
        yield_per_year = (net_per_day * 365 / sale_price * 100) if sale_price else None
        rows.append({
            "mods": mods,
            "happy": cheapest["happy"],
            "n": len(listings),
            "cost_per_day": cheapest["cost_per_day"],
            "sale_price": sale_price,
            "yield_per_year": yield_per_year,
        })

    rows.sort(key=lambda r: (r["yield_per_year"] is None, -(r["yield_per_year"] or 0)))
    return rows


def render_markdown(rows, rental_count, sale_count, generated_at):
    lines = [
        "# Private Island Rental ROI",
        "",
        f"Generated: {generated_at} UTC from {rental_count} live rental listings and {sale_count} sale listings "
        f"(Torn API `market/{PROPERTY_ID}`).",
        "",
        "Cheapest listing per buildout, filtered to `rental_period == 100` days, net of $100K/day upkeep, "
        "matched against the median sale price for the same modification bundle.",
        "",
        "| Yield/yr | n | Build cost | Happy | Cost/day | Buildout |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        yield_str = f"{row['yield_per_year']:.1f}%" if row["yield_per_year"] is not None else "n/a"
        sale_str = f"${row['sale_price'] / 1e6:.0f}M" if row["sale_price"] else "no sale match"
        mods_str = ", ".join(sorted(row["mods"])) if row["mods"] else "(bare)"
        lines.append(
            f"| {yield_str} | {row['n']} | {sale_str} | {row['happy']} | ${row['cost_per_day']:,.0f} | {mods_str} |"
        )
    lines += [
        "",
        "`n` < 3 is a single seller's asking price, not a market rate — treat those rows as a lead, not a conclusion.",
    ]
    return "\n".join(lines)


upkeep = get_upkeep()
rentals = fetch_all_listings("rentals", "rentals")
sales = fetch_all_listings("properties", "properties")
rows = compute_roi(rentals, sales, upkeep)

generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
markdown = render_markdown(rows, len(rentals), len(sales), generated_at)

with open(OUTPUT_FILE, "w") as f:
    f.write(markdown)

print(f"Written {OUTPUT_FILE}  ({len(rows)} buildouts from {len(rentals)} rentals, {len(sales)} sales)")
