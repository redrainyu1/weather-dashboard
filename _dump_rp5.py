import sys, re
sys.stdout.reconfigure(encoding='utf-8')
src = open('rp5_scraper.py', encoding='utf-8').read()
m = re.search(r'RP5_URLS = \{(.*?)\n\}', src, re.S)
pairs = re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1))
print(f'共 {len(pairs)} 个城市')
for c, u in pairs:
    print(f'{c} | {u}')