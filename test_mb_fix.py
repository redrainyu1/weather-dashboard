import httpx, re
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)
h={'User-Agent':'Mozilla/5.0','Accept-Language':'en-GB'}

tests = [
    ("New York KLGA", "Nyc"),
    ("New York LaGuardia", "Nyc"),
    ("KLGA", "Nyc"),
    ("Panama MPMG", "Panama City"),
    ("Tocumen MPMG", "Panama City"),
    ("Panama City Tocumen", "Panama City"),
]

for query, label in tests:
    r=c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": query}, headers=h)
    links = re.findall(r'/en/weather/week/([^"]+)', r.text)
    city_pat = label.lower().replace(" ", "-")
    matches = [l for l in links if any(w in l.lower() for w in ['laguardia','new-york','tocumen','panama'])]
    print(f"{label:15s} '{query:25s}' -> matches={len(matches)}, all={len(links)}")
    if matches: print(f"    {matches[0]}")
