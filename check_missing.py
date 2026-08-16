import json
d=json.load(open(r'D:\Opencode Code\weather_dashboard\data.json','r',encoding='utf-8'))

missing_meteo = set()
missing_rp5 = set()
for row in d['rows']:
    for dk in ('highest','lowest'):
        obj = row.get(dk)
        if not obj or not obj.get('forecasts'): continue
        has_met = has_rp = False
        for f in obj['forecasts']:
            if f.get('temp') is None: continue
            if f['model'] == 'METEO': has_met = True
            if f['model'] == 'RP5': has_rp = True
        if not has_met: missing_meteo.add(row['city'])
        if not has_rp: missing_rp5.add(row['city'])

print("METEO 缺失:")
for c in sorted(missing_meteo): print(f"  {c}")
print(f"\nRP5 缺失:")
for c in sorted(missing_rp5): print(f"  {c}")
