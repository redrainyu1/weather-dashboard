"""Generate clean RP5 coverage report."""
import json, re
h=open(r'D:\Opencode Code\weather_dashboard\weather_dashboard.html','r',encoding='utf-8').read()
m=re.search(r'var ALL_DATA = ({.*?});', h, re.DOTALL)
d=json.loads(m.group(1))

all_cities = sorted(set(r['city'] for r in d['rows']))
has_rp5 = set()
for r in d['rows']:
    # Any row for this city has RP5?
    for k in ('highest', 'lowest'):
        obj = r.get(k)
        if obj and any(f.get('model') == 'RP5' for f in (obj.get('forecasts') or [])):
            has_rp5.add(r['city'])

missing = [c for c in all_cities if c not in has_rp5]
has = [c for c in all_cities if c in has_rp5]

print(f"Total: {len(all_cities)} cities")
print(f"\n=== 有 RP5 ({len(has)}) ===")
for c in has:
    print(f"  {c}")

print(f"\n=== 需要手动找 ({len(missing)}) ===")
for c in missing:
    print(f"  {c}")
