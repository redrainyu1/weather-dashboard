import httpx, re

h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36','Accept-Language':'en-GB','Accept':'text/html,application/xhtml+xml'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)

tests = [
    ("Beijing ZBAA", "Beijing Capital"),
    ("Amsterdam EHAM", "Schiphol"),
    ("Tokyo RJTT", "Haneda"),
    ("London EGLL", "Heathrow"),
    ("New York KJFK", "JFK"),
    ("Atlanta KATL", "Atlanta"),
]

for query, expect in tests:
    r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": query}, headers=h)
    links = re.findall(r'/en/weather/week/([^"]+)', r.text)
    matches = [l for l in links if any(w.lower() in l.lower() for w in query.lower().split())]
    print(f"{query:20s} -> {len(links)} links, {len(matches)} matching: {matches[:2]}")
