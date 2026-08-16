"""Test meteoblue search with corrected ICAO codes."""
import httpx, re

h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36','Accept-Language':'en-GB','Accept':'text/html,application/xhtml+xml'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)

ICAO_MAP = {
    "Nyc": "KLGA", "London": "EGLC", "Dallas": "KDAL",
    "Houston": "KHOU", "Panama City": "MPMG",
    "Beijing": "ZBAA", "Amsterdam": "EHAM", "Tokyo": "RJTT",
    "Atlanta": "KATL", "Miami": "KMIA", "Singapore": "WSSS",
    "Istanbul": "LTFM", "Toronto": "CYYZ",
}

for city, icao in ICAO_MAP.items():
    query = f"{city} {icao}"
    r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": query}, headers=h)
    links = re.findall(r'/en/weather/week/([^"]+)', r.text)
    
    # Find best matching link
    city_pat = city.lower().replace(" ", "-")
    matches = [l for l in links if city_pat in l.lower()]
    
    if matches:
        best = matches[0]
        status = "OK"
    elif links:
        best = links[0]
        status = "FALLBACK"
    else:
        best = ""
        status = "NONE"
    
    print(f"{city:15s} {icao:5s} -> {status:8s} {best[:60]}")
