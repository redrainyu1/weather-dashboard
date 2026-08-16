"""Check exact meteoblue output for Beijing."""
import httpx, re
from bs4 import BeautifulSoup

PROXY = 'http://127.0.0.1:7897'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'en-GB,en;q=0.9',
}

c = httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=PROXY, follow_redirects=True)

# Step 1: search
r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": "Beijing Airport"}, headers=HEADERS)
soup = BeautifulSoup(r.text, 'html.parser')
table = soup.find('table', class_='datatable')
links = table.find_all('a', href=re.compile(r'/weather/week/'))
print("Search results:")
for i, link in enumerate(links[:5]):
    print(f"  {i+1}. {link.get_text(strip=True):40s}  {link['href']}")

# Step 2: use first result
href = links[0]['href']
if not href.startswith('http'):
    href = 'https://www.meteoblue.com' + href
print(f"\nUsing: {href}")

# Step 3: scrape
r2 = c.get(href, headers=HEADERS)
soup2 = BeautifulSoup(r2.text, 'html.parser')

# Show ALL tabs with their raw HTML
tabs = soup2.select('#tabs .tab')
print(f"\nFound {len(tabs)} day tabs:\n")
for tab in tabs:
    a = tab.select_one('a')
    if not a:
        continue
    time_e = a.select_one('time')
    day_long = a.select_one('.tab-day-long')
    day_short = a.select_one('.tab-day-short')
    tmax = a.select_one('.tab-temp-max')
    tmin = a.select_one('.tab-temp-min')
    
    dt = time_e.get('datetime', '?') if time_e else '?'
    dl = day_long.get_text(strip=True) if day_long else '?'
    ds = day_short.get_text(strip=True) if day_short else '?'
    mx_raw = tmax.get_text(strip=True).replace('\xa0', ' ') if tmax else '?'
    mn_raw = tmin.get_text(strip=True).replace('\xa0', ' ') if tmin else '?'
    
    print(f"  {ds} {dl} [{dt[:10]}] max={mx_raw} min={mn_raw}")
