import sys
sys.path.insert(0, r'D:\Opencode Code\weather_dashboard')
from rp5_scraper import scrape_rp5

for city in ['Beijing','Amsterdam','Tokyo','London','Paris','Moscow','Atlanta']:
    fc = scrape_rp5(city)
    if fc:
        items = sorted(fc.items())
        d19 = [v for dt,v in items if '07-19' in dt]
        d20 = [v for dt,v in items if '07-20' in dt]
        d21 = [v for dt,v in items if '07-21' in dt]
        parts = []
        if d19: parts.append(f"7/19:{d19[0]['max']}C")
        if d20: parts.append(f"7/20:{d20[0]['max']}C")
        if d21: parts.append(f"7/21:{d21[0]['max']}C")
        print(f"{city:18s} {' | '.join(parts)}")
    else:
        print(f"{city:18s} NO DATA")
