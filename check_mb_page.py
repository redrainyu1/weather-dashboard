import httpx, re
from bs4 import BeautifulSoup

h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36','Accept-Language':'en-GB','Accept':'text/html,application/xhtml+xml'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)
r=c.get("https://www.meteoblue.com/en/weather/search/index",params={"query":"Beijing"},headers=h)
html=r.text
print(f"Status: {r.status_code}, Size: {len(html)}")

# Find all week links directly in HTML
links = re.findall(r'/en/weather/week/([^"]+)', html)
print(f"\nWeek forecast links in raw HTML: {len(links)}")
for l in links[:5]:
    print(f"  {l}")

# Check for table tag
tables = re.findall(r'<table[^>]*>', html)
print(f"\n<table> tags: {len(tables)}")
for t in tables[:3]:
    print(f"  {t[:80]}")

# Check for datatable
if 'datatable' in html:
    idx = html.index('datatable')
    print(f"\n'datatable' found at position {idx}:")
    print(html[max(0,idx-100):idx+200])
else:
    print("\n'datatable' NOT found in HTML")

# Find Beijing links
beijing = re.findall(r'href="(/en/weather/week/beijing[^"]*)"[^>]*>([^<]+)', html)
print(f"\nBeijing links: {len(beijing)}")
for href, text in beijing:
    print(f"  {text.strip()}: {href}")
