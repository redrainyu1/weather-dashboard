import httpx, re
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36','Accept-Language':'en'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)

from rp5_scraper import parse_rp5, RP5_URLS

for city in ['Jeddah', 'Warsaw']:
    url = RP5_URLS[city]
    r = c.get(url, headers=HEADERS)
    fc = parse_rp5(r.text)
    days = len(fc)
    has_table = 'forecastTable' in r.text
    print(f"{city}: status={r.status_code}, has_forecastTable={has_table}, days={days}")
    if fc:
        for dt in sorted(fc.keys())[:2]:
            print(f"  {dt}: max={fc[dt]['max']}C")
