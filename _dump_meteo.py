import sys, re
sys.stdout.reconfigure(encoding='utf-8')
src = open('serve.py', encoding='utf-8').read()
m = re.search(r'METEO_URL_OVERRIDE = \{(.*?)\n\}', src, re.S)
body = m.group(1)
pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', body)
iap = re.search(r'AIRPORT_CODES = \{(.*?)\n\}', src, re.S)
icao = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', iap.group(1)))
cn = re.search(r'CITY_CN = \{(.*?)\n\}', src, re.S)
cnmap = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', cn.group(1)))
print(f'共 {len(pairs)} 个城市')
for c, u in pairs:
    print(f'{cnmap.get(c, ""):4s} {c:16s} {icao.get(c, ""):5s} | {u}')