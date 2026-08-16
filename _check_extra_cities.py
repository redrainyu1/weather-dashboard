import sys, httpx
from datetime import date, timedelta
sys.stdout.reconfigure(encoding='utf-8')
PROXY = "http://127.0.0.1:7897"
GAMMA = "https://gamma-api.polymarket.com"

cities = ['austin', 'buenos-aires', 'chicago', 'denver', 'jinan', 'miami', 'panama-city', 'zhengzhou']
today = date(2026, 8, 11)
with httpx.Client(http1=True, http2=False, verify=False, timeout=30, proxy=PROXY, follow_redirects=True) as c:
    for city in cities:
        found = []
        for d in (today + timedelta(days=i) for i in range(0, 3)):
            ds = d.strftime("%B").lower() + "-" + str(d.day) + "-" + str(d.year)
            slug1 = f"highest-temperature-in-{city}-on-{ds}"
            slug2 = f"lowest-temperature-in-{city}-on-{ds}"
            for s in (slug1, slug2):
                try:
                    r = c.get(f"{GAMMA}/events/slug/{s}")
                    j = r.json()
                    if j and j.get("id"):
                        mkts = j.get("markets") or []
                        found.append((s, "active" if not j.get("closed") else "closed", len(mkts)))
                except Exception as e:
                    found.append((s, "ERR " + str(e)))
        status = "; ".join(f"{s} [{st}/{n}]" for s, st, n in found)
        print(f"{city:14s} {status}")