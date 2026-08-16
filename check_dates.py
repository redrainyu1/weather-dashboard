import json, re
h=open(r'D:\Opencode Code\weather_dashboard\weather_dashboard.html','r',encoding='utf-8').read()
m=re.search(r'var ALL_DATA = ({.*?});', h, re.DOTALL)
d=json.loads(m.group(1))

from collections import Counter
dates=Counter()
for r in d['rows']:
    dates[r['date_display']]+=1

print(f"Total rows: {d['count']}")
print(f"\nDate distribution:")
for dt, cnt in sorted(dates.items()):
    print(f"  {dt}: {cnt} cities")

# Check which cities have 07/19
cities_19=[r['city'] for r in d['rows'] if r['date_display']=='07/19']
print(f"\nCities with 07/19 ({len(cities_19)}):")
for c in sorted(cities_19):
    print(f"  {c}")
