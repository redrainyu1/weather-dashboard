"""Map city -> rp5.ru URL. Unlisted cities try Weather_in_{City} pattern."""
import os, re
from datetime import datetime

# Verified working URLs
RP5_URLS = {
    "Amsterdam": "https://rp5.ru/Weather_in_Amsterdam_(airport)",
    "Ankara": "https://rp5.ru/Weather_in_Ankara,_Esenboga_(airport)",
    "Atlanta": "https://rp5.ru/Weather_in_Hartsfield%E2%80%93Jackson_Atlanta_(airport)",
    "Austin": "https://rp5.ru/Weather_in_West_Lake_Hills_(airport)",
    "Beijing": "https://rp5.ru/Weather_in_Beijing,_Peking_(airport)",
    "Buenos Aires": "https://rp5.ru/Weather_in_Ezeiza_(airport)",
    "Busan": "https://rp5.ru/Weather_in_Busan_(airport)",
    "Cape Town": "https://rp5.ru/Weather_in_Cape_Town_(airport)",
    "Chengdu": "https://rp5.ru/Weather_in_Chengdu_(airport)",
    "Chicago": "https://rp5.ru/Weather_in_Chicago,_O%27Hare_(airport)",
    "Chongqing": "https://rp5.ru/Weather_in_Chongqing,_Jiulongpo_(airport)",
    "Dallas": "https://rp5.ru/Weather_in_Dallas,_Love_Field_(airport)",
    "Denver": "https://rp5.ru/Weather_in_Denver_(airport),_Colorado",
    "Guangzhou": "https://rp5.ru/Weather_in_Guangzhou_(airport)",
    "Helsinki": "https://rp5.ru/Weather_in_Helsinki,_Vantaa_(airport)",
    "Hong Kong": "https://rp5.ru/Weather_in_Hong_Kong_(airport)",
    "Houston": "https://rp5.ru/Weather_in_Houston,_William_P._Hobby_(airport)",
    "Istanbul": "https://rp5.ru/Weather_in_Istanbul_(airport)",
    "Jeddah": "https://rp5.ru/Weather_in_Jeddah_(airport)",
    "Jinan": "https://rp5.ru/Weather_in_Jinan_Yaoqiang_(airport)",
    "Karachi": "https://rp5.ru/Weather_in_Karachi_(airport)",
    "Kuala Lumpur": "https://rp5.ru/Weather_in_Kuala_Lumpur_(airport)",
    "London": "https://rp5.ru/Weather_in_London_City_(airport)",
    "Los Angeles": "https://rp5.ru/Weather_in_Los_Angeles_(airport)",
    "Lucknow": "https://rp5.ru/Weather_in_Lucknow,_Amausi_(airport)",
    "Madrid": "https://rp5.ru/Weather_in_Madrid,_Barajas_(airport)",
    "Manila": "https://rp5.ru/Weather_in_Ninoy_(airport)",
    "Mexico City": "https://rp5.ru/Weather_in_Mexico_(airport)",
    "Miami": "https://rp5.ru/Weather_in_Miami_(airport),_Florida",
    "Milan": "https://rp5.ru/Weather_in_Malpensa_(airport)",
    "Moscow": "https://rp5.ru/Weather_in_Vnukovo_(airport)",
    "Munich": "https://rp5.ru/Weather_in_Munich_(airport)",
    "Nyc": "https://rp5.ru/Weather_in_New_York,_La_Guardia_(airport)",
    "Panama City": "https://rp5.ru/Weather_in_Panama,_Albrook_(airport)",
    "Paris": "https://rp5.ru/Weather_in_Paris,_France",
    "Qingdao": "https://rp5.ru/Weather_in_Qingdao_(airport)",
    "San Francisco": "https://rp5.ru/Weather_in_San_Francisco_(airport)",
    "Sao Paulo": "https://rp5.ru/Weather_in_Guarulhos_(airport)",
    "Seattle": "https://rp5.ru/Weather_in_Seattle,_Tacoma_(airport)",
    "Seoul": "https://rp5.ru/Weather_in_Incheon_(airport)",
    "Shanghai": "https://rp5.ru/Weather_in_Shanghai_Pudong_(airport)",
    "Shenzhen": "https://rp5.ru/Weather_in_Shenzhen_Bao%27an_(airport)",
    "Singapore": "https://rp5.ru/Weather_in_Singapore_(airport)",
    "Taipei": "https://rp5.ru/Weather_in_Taiwan_Taoyuan_(airport)",
    "Tel Aviv": "https://rp5.ru/Weather_in_Tel_Aviv,_Ben-Gurion_(airport)",
    "Tokyo": "https://rp5.ru/Weather_in_Tokyo",
    "Toronto": "https://rp5.ru/Weather_in_Toronto_Pearson_(airport)",
    "Warsaw": "https://rp5.ru/Weather_in_Warsaw,_Okecie_(airport)",
    "Wellington": "https://rp5.ru/Weather_in_Wellington_(airport),_New_Zealand",
    "Wuhan": "https://rp5.ru/Weather_in_Wuhan_(airport)",
    "Zhengzhou": "https://rp5.ru/Weather_in_Zhengzhou_(airport)",
}

def get_rp5_url(city):
    if city in RP5_URLS:
        return RP5_URLS[city]
    clean = city.replace(" ", "_")
    return f"https://rp5.ru/Weather_in_{clean}"


def parse_rp5(html, target_year=2026):
    """Extract daily max/min from rp5.ru forecast table."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    # Prefer 3-hour table for finer resolution, fall back to 6-hour
    table = soup.find('table', id='forecastTable_1_3') or soup.find('table', id='forecastTable')
    if not table:
        return {}
    
    rows = table.find_all('tr')
    if len(rows) < 5:
        return {}
    
    # Row 0: date headers with colspan
    header_tds = rows[0].find_all('td')
    days = []
    for td in header_tds:
        colspan = int(td.get('colspan', 1))
        for _ in range(colspan):
            days.append(td.get_text(strip=True))
    
    # Row 4: temperatures (+CC+FF format)
    temp_tds = rows[4].find_all('td')
    
    daily_max = {}
    daily_min = {}
    for i, td in enumerate(temp_tds):
        text = td.get_text(strip=True)
        m = re.match(r'([+-]\d+)([+-]\d+)', text)
        if not m or i >= len(days):
            continue
        c_temp = int(m.group(1))
        day_raw = days[i]
        # Clean: "Tomorrow, Sun, July 19" or "Mon, July 20" -> "July 19" / "July 20"
        parts = day_raw.split(',')
        date_str = parts[-1].strip() if len(parts) > 1 else day_raw
        # Skip day-only entries ("Sat" without date)
        if date_str in ('Sat','Sun','Mon','Tue','Wed','Thu','Fri','Today','Tomorrow'):
            continue
        
        if date_str not in daily_max or c_temp > daily_max[date_str]:
            daily_max[date_str] = c_temp
        if date_str not in daily_min or c_temp < daily_min[date_str]:
            daily_min[date_str] = c_temp
    
    # Convert "July 19" -> "2026-07-19"
    result = {}
    for day_str, mx in daily_max.items():
        try:
            dt = datetime.strptime(f"{day_str} {target_year}", "%B %d %Y")
            key = dt.strftime("%Y-%m-%d")
            result[key] = {"max": mx, "min": daily_min.get(day_str, mx)}
        except ValueError:
            pass
    return result


def scrape_rp5(city):
    """Scrape rp5.ru forecast for a city. Returns {date: {max, min}}."""
    import httpx
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en',
    }
    PROXY = os.getenv("PROXY_URL", "http://127.0.0.1:7897")
    
    try:
        with httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=PROXY, follow_redirects=True) as c:
            url = get_rp5_url(city)
            r = c.get(url, headers=HEADERS)
            if r.status_code != 200:
                return {}
            fc = parse_rp5(r.text)
            return fc
    except Exception:
        return {}


if __name__ == '__main__':
    # Test with integrated method
    for city in ["Beijing", "Amsterdam", "Tokyo", "Paris", "Moscow", "London"]:
        fc = scrape_rp5(city)
        if fc:
            print(f"\n{city}: {len(fc)} days")
            for dt in sorted(fc.keys())[:3]:
                print(f"  {dt}: max={fc[dt]['max']}C min={fc[dt]['min']}C")
        else:
            print(f"\n{city}: NO DATA")
