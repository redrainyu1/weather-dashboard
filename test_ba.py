import httpx, re
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)
h={'User-Agent':'Mozilla/5.0','Accept-Language':'en-GB'}

for q in ['Buenos Aires Airport','Ezeiza Airport','Buenos Aires Ezeiza','Aeroparque']:
    r=c.get("https://www.meteoblue.com/en/weather/search/index",params={"query":q},headers=h)
    links=re.findall(r'/en/weather/week/([^"]+)',r.text)
    ba=[l for l in links if 'buenos' in l.lower() or 'ezeiza' in l.lower() or 'aeroparque' in l.lower()]
    print(f"'{q}': {len(links)} links, {len(ba)} BA matches")
    for l in ba[:3]:
        print(f"  {l}")
