"""Fetch weather market data from Polymarket and output JSON."""
import json
import re
import asyncio
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

GAMMA_HOST = "https://gamma-api.polymarket.com"
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:7897")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http1=True, http2=False, verify=False, timeout=30.0,
        proxy=PROXY_URL, follow_redirects=True,
        limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=15),
    )


def parse_city_date(slug: str) -> dict:
    m = re.match(
        r'(highest|lowest)-temperature-in-(.+?)-on-(july-\d{1,2}-2026)',
        slug
    )
    if not m:
        return {}
    direction = m.group(1)
    city = m.group(2).replace("-", " ").title()
    date_str = m.group(3)
    dt = datetime.strptime(date_str, "%B-%d-%Y")
    return {
        "city": city,
        "date": dt.strftime("%Y-%m-%d"),
        "date_display": dt.strftime("%m/%d"),
        "direction": direction,
    }


def parse_temp(slug: str) -> dict | None:
    """Extract temperature info from a market slug.
    
    Returns dict with temp_display (e.g., "16°C"), temp_value (int), 
    and type: "exact", "below", or "above".
    """
    # Pattern: ...-16c, ...-15corbelow, ...-25corhigher, ...-92-93f
    m = re.search(r'-(\d{2,3}(?:-\d{2,3})?(?:pt\d+)?(?:c|f))(?:orbelow|orhigher)?$', slug)
    if not m:
        return None
    
    raw = m.group(1)
    unit = "°C" if raw.endswith("c") else ("°F" if raw.endswith("f") else "")
    raw_num = raw.rstrip("cf")
    raw_num = raw_num.replace("pt", ".")
    
    ttype = "exact"
    if "orbelow" in slug:
        ttype = "below"
    elif "orhigher" in slug:
        ttype = "above"
    
    try:
        temp_value = float(raw_num)
    except ValueError:
        temp_value = float(raw_num.split("-")[0]) if "-" in raw_num else 0
    
    return {
        "temp_display": raw_num + unit,
        "temp_value": temp_value,
        "type": ttype,
    }


def extract_event_slugs(html: str) -> list[str]:
    seen = set()
    slugs = []
    for m in re.finditer(r'/event/((?:highest|lowest)-temperature-in-[a-z0-9\-]+-2026)', html):
        s = m.group(1)
        if s not in seen:
            seen.add(s)
            slugs.append(s)
    return slugs


async def fetch_event(client: httpx.AsyncClient, slug: str) -> dict | None:
    try:
        r = await client.get(f"{GAMMA_HOST}/events/slug/{slug}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Failed: {slug}: {e}")
        return None


def _parse_outcome_prices(raw) -> list[float]:
    """Parse outcomePrices field (can be string JSON or list)."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, list):
        return [float(x) for x in raw]
    return []


def _parse_clob_token_ids(raw) -> list[str]:
    """Parse clobTokenIds field."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    return raw if isinstance(raw, list) else []


def build_event_data(slug: str, event: dict) -> dict:
    info = parse_city_date(slug)
    markets_raw = event.get("markets", [])

    markets_out = []
    for m in markets_raw:
        market_slug = m.get("slug", "")
        tinfo = parse_temp(market_slug)

        # Parse prices
        prices = _parse_outcome_prices(m.get("outcomePrices"))
        # outcomePrices: [YES_price, NO_price] matching outcomes order
        yes_price = None
        if len(prices) >= 2:
            yes_price = prices[0]
        elif len(prices) == 1:
            yes_price = prices[0]

        # Parse token IDs
        token_ids = _parse_clob_token_ids(m.get("clobTokenIds"))
        token_id = token_ids[0] if token_ids else ""

        markets_out.append({
            "slug": market_slug,
            "token_id": token_id,
            "question": m.get("question", ""),
            "temp": tinfo["temp_display"] if tinfo else None,
            "temp_value": tinfo["temp_value"] if tinfo else None,
            "temp_type": tinfo["type"] if tinfo else None,
            "yes_price": round(yes_price, 4) if yes_price is not None else None,
            "yes_pct": round(yes_price * 100, 1) if yes_price is not None else None,
            "volume": float(m.get("volume", 0) or 0),
        })

    markets_out.sort(key=lambda x: x.get("temp_value", 0) or 0)

    # Find the predicted temp (highest YES probability among "exact" markets)
    exact_markets = [m for m in markets_out if m.get("temp_type") == "exact" and m["yes_price"]]
    predicted = max(exact_markets, key=lambda x: x["yes_price"]) if exact_markets else None

    return {
        "city": info.get("city", ""),
        "date": info.get("date", ""),
        "date_display": info.get("date_display", ""),
        "direction": info.get("direction", ""),
        "slug": slug,
        "markets": markets_out,
        "predicted_temp": predicted["temp"] if predicted else None,
        "predicted_prob": predicted["yes_pct"] if predicted else None,
    }


def group_by_city(data: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for item in data:
        key = (item["city"], item["date"])
        if key not in groups:
            groups[key] = {
                "city": item["city"],
                "date": item["date"],
                "date_display": item["date_display"],
                "highest": None,
                "lowest": None,
            }
        groups[key][item["direction"]] = item

    return sorted(groups.values(), key=lambda x: (x["city"], x["date"]))


async def fetch_all() -> list[dict]:
    async with _client() as client:
        print("Fetching weather page...")
        r = await client.get("https://polymarket.com/zh/weather")
        html = r.text
        print(f"  Got {len(html):,} bytes")

        slugs = extract_event_slugs(html)
        print(f"\nFound {len(slugs)} event slugs")

        print(f"\nFetching event details (batch of 10)...")
        results: list[dict] = []
        batch_size = 10
        for i in range(0, len(slugs), batch_size):
            batch = slugs[i:i + batch_size]
            tasks = [fetch_event(client, s) for s in batch]
            batch_results = await asyncio.gather(*tasks)
            for slug, data in zip(batch, batch_results):
                if data:
                    results.append(build_event_data(slug, data))
            print(f"  {min(i + batch_size, len(slugs))}/{len(slugs)}")

        return results


async def main():
    print("=" * 60)
    print("Weather Dashboard - Data Fetcher")
    print("=" * 60)

    data = await fetch_all()
    grouped = group_by_city(data)

    output = {
        "updated_at": datetime.now().isoformat(),
        "count": len(grouped),
        "rows": grouped,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nDone! {len(grouped)} rows written to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
