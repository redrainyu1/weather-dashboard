import json, re
h=open(r'D:\Opencode Code\weather_dashboard\weather_dashboard.html','r',encoding='utf-8').read()
m=re.search(r'var ALL_DATA = ({.*?});', h, re.DOTALL)
d=json.loads(m.group(1))

for r in d['rows']:
    if r['city'] == 'Buenos Aires':
        print(f"  {r['date_display']}:")
        h = r.get('highest')
        if h and h.get('forecasts'):
            for f in h['forecasts']:
                pct = f"{f['pct']:.0f}%" if f.get('pct') is not None else '--'
                print(f"    H {f['model']:6s} -> {f['temp']:>3d}  Poly: {pct}")
        l = r.get('lowest')
        if l and l.get('forecasts'):
            for f in l['forecasts']:
                pct = f"{f['pct']:.0f}%" if f.get('pct') is not None else '--'
                print(f"    L {f['model']:6s} -> {f['temp']:>3d}  Poly: {pct}")
