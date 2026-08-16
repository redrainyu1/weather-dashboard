import httpx,re
from bs4 import BeautifulSoup
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)
h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36','Accept-Language':'en-GB','Accept':'text/html,application/xhtml+xml','Sec-Fetch-Site':'none','Sec-Fetch-Mode':'navigate','Sec-Fetch-Dest':'document'}

urls = [
    ("Capital Airport", "https://www.meteoblue.com/en/weather/week/beijing-capital-international-airport_china_6301354"),
    ("Daxing Airport", "https://www.meteoblue.com/en/weather/week/beijing-daxing-international-airport_china_12032353"),
]
for label, url in urls:
    try:
        r=c.get(url,headers=h)
        print(f"\n{label}: status={r.status_code}")
        s=BeautifulSoup(r.text,'html.parser')
        title = s.find('title')
        print(f"  Title: {title.get_text(strip=True) if title else 'N/A'}")
        tabs=s.select('#tabs .tab')
        print(f"  Found {len(tabs)} div.tab")
        if tabs:
            for t in tabs[:3]:
                a_tag = t.select_one('a')
                if a_tag:
                    tm=a_tag.select_one('time')
                    mx=a_tag.select_one('.tab-temp-max')
                    mn=a_tag.select_one('.tab-temp-min')
                    if tm and mx and mn:
                        dt=tm.get('datetime','')[:10]
                        mxt=mx.get_text(strip=True).replace('\xa0',' ')
                        mnt=mn.get_text(strip=True).replace('\xa0',' ')
                        print(f"  {dt} max={mxt} min={mnt}")
    except Exception as e:
        print(f"\n{label}: ERROR - {e}")
