"""Quick check: see raw Gamma API response structure for one event."""
import httpx, json, os

PROXY = os.getenv("PROXY_URL", "http://127.0.0.1:7897")

c = httpx.Client(http1=True, http2=False, verify=False, timeout=15, proxy=PROXY, follow_redirects=True)
r = c.get("https://gamma-api.polymarket.com/events/slug/highest-temperature-in-amsterdam-on-july-19-2026")
data = r.json()

# Print first market in detail
markets = data.get("markets", [])
print(f"Event: {data.get('title')}")
print(f"Total markets: {len(markets)}")
print(f"\nFirst market keys: {list(markets[0].keys()) if markets else 'N/A'}")
print(f"\nFull first market:")
print(json.dumps(markets[0], indent=2, ensure_ascii=False)[:1500])

print(f"\n\nAll market slugs:")
for m in markets:
    print(f"  {m.get('slug')}")
    if m.get('tokens'):
        for t in m['tokens']:
            print(f"    token: {t.get('token_id','')[:40]}... | out: {t.get('outcome','')}")
