"""Check what rp5.ru returns for London, New York, Singapore - disambiguation page?"""
import httpx, re
from bs4 import BeautifulSoup

h={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)

for city, url in [
    ("London", "https://rp5.ru/Weather_in_London"),
    ("New York", "https://rp5.ru/Weather_in_New_York"),
    ("Singapore", "https://rp5.ru/Weather_in_Singapore"),
]:
    r=c.get(url,headers=h)
    soup=BeautifulSoup(r.text,'html.parser')
    title=soup.find('title')
    print(f"\n{city}: {title.get_text(strip=True) if title else 'N/A'}")
    
    # Look for links to city weather pages
    links=re.findall(r'href="(/Weather_in_[^"]+)"',r.text)
    print(f"  Weather links found: {len(links)}")
    for l in links[:5]:
        print(f"    {l}")
    
    # Check for forecast table
    has_fc='forecastTable' in r.text
    print(f"  Has forecastTable: {has_fc}")
    
    # If no forecast, check for disambiguation / station list
    if not has_fc:
        # Look for station IDs
        ids=re.findall(r'id=(\d+)',r.text)
        print(f"  Station IDs: {ids[:5]}")
        
        # Look for "choose" or "select" text
        body=soup.find('body')
        if body:
            text=body.get_text()
            for line in text.split('\n'):
                line=line.strip()
                if 'London' in line or 'Heathrow' in line or 'Airport' in line or 'choose' in line.lower():
                    print(f"  -> {line[:120]}")
