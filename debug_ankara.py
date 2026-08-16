import httpx, re
from bs4 import BeautifulSoup

h={'User-Agent':'Mozilla/5.0','Accept-Language':'en'}
c=httpx.Client(http1=True,http2=False,verify=False,timeout=20,proxy='http://127.0.0.1:7897',follow_redirects=True)
r=c.get('https://rp5.ru/Weather_in_Ankara',headers=h)
soup=BeautifulSoup(r.text,'html.parser')

# Check ALL forecast tables
for tid in ['forecastTable', 'forecastTable_1_3']:
    table=soup.find('table',id=tid)
    if not table: continue
    rows=table.find_all('tr')
    print(f"\n=== Table: {tid} ===")
    print(f"Rows: {len(rows)}")
    
    # Row 0: headers
    header_tds=rows[0].find_all('td')
    day_slots={}
    col_idx=0
    for td in header_tds:
        colspan=int(td.get('colspan',1))
        text=td.get_text(strip=True).split(',')[-1].strip()
        for _ in range(colspan):
            day_slots[col_idx]=text
            col_idx+=1
    
    # Row 4: temperature
    if len(rows)>4:
        temp_tds=rows[4].find_all('td')
        daily={}
        for i,td in enumerate(temp_tds):
            text=td.get_text(strip=True)
            m=re.match(r'([+-]\d+)',text)
            if not m: continue
            t=int(m.group(1))
            day=day_slots.get(i,'?')
            if day and day not in ('Sat','Sun','Mon','Tue','Wed','Thu','Fri',''):
                if day not in daily: daily[day]={'max':t,'min':t}
                else:
                    if t>daily[day]['max']: daily[day]['max']=t
                    if t<daily[day]['min']: daily[day]['min']=t
        
        for day,vals in sorted(daily.items()):
            print(f"  {day}: max={vals['max']}C, min={vals['min']}C")
