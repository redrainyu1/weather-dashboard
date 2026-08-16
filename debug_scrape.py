"""Debug: verify meteoblue scrape output for specific cities."""
import httpx, re, json
from bs4 import BeautifulSoup

PROXY = 'http://127.0.0.1:7897'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

c = httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=PROXY, follow_redirects=True)

for city, query in [("Amsterdam", "Amsterdam Airport"), ("Beijing", "Beijing Airport"), ("Tokyo", "Tokyo Airport"), ("London", "London Airport")]:
    print(f"\n{'='*60}")
    print(f"{city}  ({query})")
    print('='*60)
    
    # Search
    r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": query}, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', class_='datatable')
    
    if not table:
        print("  No search results table")
        continue
    
    links = table.find_all('a', href=re.compile(r'/weather/week/'))
    if not links:
        print("  No week forecast links")
        continue
    
    # Show first result
    first = links[0]
    href = first['href']
    text = first.get_text(strip=True)
    print(f"  Found: {text}")
    print(f"  URL: {href}")
    
    if not href.startswith('http'):
        href = 'https://www.meteoblue.com' + href
    
    # Scrape forecast
    r2 = c.get(href, headers=HEADERS)
    soup2 = BeautifulSoup(r2.text, 'html.parser')
    tabs = soup2.select('#tabs .tab a')
    
    print(f"\n  Forecast (first 7 days):")
    for tab in tabs[:7]:
        tmax = tab.select_one('.tab-temp-max')
        tmin = tab.select_one('.tab-temp-min')
        time_e = tab.select_one('time')
        day_long = tab.select_one('.tab-day-long')
        
        date_str = time_e.get('datetime', '') if time_e else ''
        max_t = tmax.get_text(strip=True) if tmax else '?'
        min_t = tmin.get_text(strip=True) if tmin else '?'
        day = day_long.get_text(strip=True) if day_long else '?'
        
        print(f"    [{date_str[:10]}] {day:12s} max={max_t:>5s} min={min_t:>5s}")
