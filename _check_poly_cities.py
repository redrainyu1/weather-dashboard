import sys, re, httpx
sys.stdout.reconfigure(encoding='utf-8')
PROXY = "http://127.0.0.1:7897"
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'}

def norm(city):
    return re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')

with httpx.Client(http1=True, http2=False, verify=False, timeout=30, proxy=PROXY, follow_redirects=True) as c:
    r = c.get("https://polymarket.com/zh/weather", headers=H)
    seen = set(); slugs = []
    for m in re.finditer(r'/event/((?:highest|lowest)-temperature-in-[a-z0-9\-]+-2026)', r.text):
        s = m.group(1)
        if s not in seen:
            seen.add(s); slugs.append(s)

page_cities = {}
for s in slugs:
    m = re.match(r'(?:highest|lowest)-temperature-in-(.+)-on-(.+)$', s)
    if m:
        page_cities.setdefault(m.group(1), set()).add(s)

src = open('serve.py', encoding='utf-8').read()
iap = re.search(r'AIRPORT_CODES = \{(.*?)\n\}', src, re.S)
ours = set(dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', iap.group(1))).keys())

page_norm = {norm(k): k for k in page_cities}
ours_norm = {norm(k): k for k in ours}

print(f"页面唯一城市: {len(page_cities)}")
print(f"我们配置: {len(ours)}")
print(f"页面有、我们无: {sorted(set(page_norm) - set(ours_norm))}")
print(f"我们有、页面无: {sorted(set(ours_norm) - set(page_norm))}")
print(f"一致: {len(set(ours_norm) & set(page_norm))} 个")
