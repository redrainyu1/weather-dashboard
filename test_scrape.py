"""Test meteoblue scraping with city+airport search."""
import httpx
import re
from bs4 import BeautifulSoup

PROXY = 'http://127.0.0.1:7897'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

def search_airport(client, city):
    """Search meteoblue for city airport and return week URL + geonameId."""
    for query in [f"{city} Airport", city]:
        r = client.get(
            'https://www.meteoblue.com/en/weather/search/index',
            params={'query': query},
            headers=HEADERS
        )
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find('table', class_='datatable')
        if not table:
            continue
        links = table.find_all('a', href=re.compile(r'/weather/week/'))
        for link in links:
            href = link['href']
            text = link.get_text(strip=True).lower()
            # Prioritize results with "airport" in name
            if 'airport' in text or city.lower().replace(' ', '') in text.replace(' ', ''):
                m = re.search(r'/(\d+)$', href)
                geoid = m.group(1) if m else None
                if not href.startswith('http'):
                    href = 'https://www.meteoblue.com' + href
                return {'week_url': href, 'geoid': geoid}
        # Fallback: first result
        if links:
            href = links[0]['href']
            if not href.startswith('http'):
                href = 'https://www.meteoblue.com' + href
            m = re.search(r'/(\d+)$', href)
            return {'week_url': href, 'geoid': m.group(1) if m else None}
    return None


def scrape_forecast(client, url):
    """Scrape daily max/min from meteoblue week page."""
    r = client.get(url, headers=HEADERS)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    tabs = soup.select('#tabs .tab a')
    forecast = {}
    for tab in tabs:
        temp_max = tab.select_one('.tab-temp-max')
        temp_min = tab.select_one('.tab-temp-min')
        day_name = tab.select_one('.tab-day-long')
        date_text = tab.select_one('time')
        if temp_max and temp_min:
            max_t = int(re.sub(r'[^\d]', '', temp_max.get_text(strip=True)) or '0')
            min_t = int(re.sub(r'[^\d]', '', temp_min.get_text(strip=True)) or '0')
            # Get date from time element if available
            dt = date_text.get('datetime', '') if date_text else ''
            # Parse the date
            if dt:
                from datetime import datetime
                d = datetime.fromisoformat(dt.split('T')[0])
                key = d.strftime('%Y-%m-%d')
            else:
                label = day_name.get_text(strip=True) if day_name else ''
                key = label
            forecast[key] = {'max': max_t, 'min': min_t}
    return forecast


if __name__ == '__main__':
    c = httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=PROXY, follow_redirects=True)

    for city in ['Amsterdam', 'Beijing', 'New York', 'London', 'Tokyo']:
        print(f"\n=== {city} ===")
        result = search_airport(c, city)
        if result:
            print(f"  URL: ...{result['week_url'][-50:]}")
            fc = scrape_forecast(c, result['week_url'])
            if fc:
                for day, data in sorted(fc.items())[:5]:
                    print(f"    {day}: max={data['max']}C, min={data['min']}C")
        else:
            print("  Not found")
