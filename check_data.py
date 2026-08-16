import json, re
html = open(r'D:\Opencode Code\weather_dashboard\weather_dashboard.html', 'r', encoding='utf-8').read()
m = re.search(r'var ALL_DATA = ({.*?});', html, re.DOTALL)
d = json.loads(m.group(1))

print(f"Total rows: {d['count']}\n")

for r in d['rows'][:8]:
    h = r.get('highest')
    l = r.get('lowest')
    
    print(f"{r['city']:20s} {r['date_display']}")
    
    if h and h.get('forecasts'):
        for fc in h['forecasts']:
            pct = f"{fc['pct']:.0f}%" if fc.get('pct') is not None else '--'
            print(f"  H {fc['model']:6s} -> {fc['temp']:>3d}  Poly: {pct}")
    
    if l and l.get('forecasts'):
        for fc in l['forecasts']:
            pct = f"{fc['pct']:.0f}%" if fc.get('pct') is not None else '--'
            print(f"  L {fc['model']:6s} -> {fc['temp']:>3d}  Poly: {pct}")
    print()
