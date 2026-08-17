"""Weather Dashboard - GFS GEM ICON meteoblue RP5 + Polymarket prices."""
import json, re, asyncio, os, webbrowser
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from city_coords import CITY_COORDS, FAHRENHEIT_CITIES
from rp5_scraper import scrape_rp5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

GAMMA_HOST = "https://gamma-api.polymarket.com"
METEOC_API = "https://api.open-meteo.com/v1/forecast"
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:7897")
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "template.html")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "weather_dashboard.html")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}

FORECAST_MODELS = [("GFS", "gfs_seamless"), ("GEM", "gem_seamless"), ("ICON", "icon_seamless")]

AIRPORT_CODES = {
    "Amsterdam": "EHAM", "Ankara": "LTAC", "Atlanta": "KATL", "Austin": "KAUS",
    "Beijing": "ZBAA", "Buenos Aires": "SAEZ", "Busan": "RKPK", "Cape Town": "FACT",
    "Chengdu": "ZUUU", "Chicago": "KORD", "Chongqing": "ZUCK", "Dallas": "KDAL",
    "Denver": "KDEN", "Guangzhou": "ZGGG", "Helsinki": "EFHK", "Hong Kong": "VHHH",
    "Houston": "KHOU", "Istanbul": "LTFM", "Jeddah": "OEJN", "Jinan": "ZSJN", "Karachi": "OPKC",
    "Kuala Lumpur": "WMKK", "London": "EGLC", "Los Angeles": "KLAX", "Lucknow": "VILK",
    "Madrid": "LEMD", "Manila": "RPLL", "Mexico City": "MMMX", "Miami": "KMIA",
    "Milan": "LIMC", "Moscow": "UUWW", "Munich": "EDDM", "Nyc": "KLGA",
    "Panama City": "MPMG", "Paris": "LFPB", "Qingdao": "ZSQD", "San Francisco": "KSFO",
    "Sao Paulo": "SBGR", "Seattle": "KSEA", "Seoul": "RKSI", "Shanghai": "ZSPD",
    "Shenzhen": "ZGSZ", "Singapore": "WSSS", "Taipei": "RCTP", "Tel Aviv": "LLBG",
    "Tokyo": "RJTT", "Toronto": "CYYZ", "Warsaw": "EPWA", "Wellington": "NZWN", "Wuhan": "ZHHH", "Zhengzhou": "ZHCC",
}

# 每个机场夏季利于升温的风向（静态气候经验）
WIND_HEAT_MAP = {
    "Amsterdam": "西南", "Ankara": "南", "Atlanta": "西南", "Austin": "南",
    "Beijing": "东南", "Buenos Aires": "北", "Busan": "南", "Cape Town": "北",
    "Chengdu": "东南", "Chicago": "西南", "Chongqing": "东南", "Dallas": "南",
    "Denver": "西", "Guangzhou": "南", "Helsinki": "南", "Hong Kong": "南",
    "Houston": "南", "Istanbul": "南", "Jeddah": "北", "Jinan": "东南",
    "Karachi": "南", "Kuala Lumpur": "东南", "London": "西南", "Los Angeles": "东北",
    "Lucknow": "东南", "Madrid": "西南", "Manila": "东南", "Mexico City": "南",
    "Miami": "西", "Milan": "南", "Moscow": "南", "Munich": "南",
    "Nyc": "西南", "Panama City": "静风", "Paris": "西南", "Qingdao": "东南",
    "San Francisco": "东北", "Sao Paulo": "北", "Seattle": "东北", "Seoul": "南",
    "Shanghai": "东南", "Shenzhen": "南", "Singapore": "南", "Taipei": "南",
    "Tel Aviv": "东", "Tokyo": "南", "Toronto": "西南", "Warsaw": "南",
    "Wellington": "西北", "Wuhan": "东南", "Zhengzhou": "东南",
}

METEO_CITY_NAMES = {"Nyc": "New York"}

CITY_CN = {
    "Amsterdam": "阿姆斯特丹", "Ankara": "安卡拉", "Atlanta": "亚特兰大", "Austin": "奥斯汀",
    "Beijing": "北京", "Buenos Aires": "布宜诺斯艾利斯", "Busan": "釜山", "Cape Town": "开普敦",
    "Chengdu": "成都", "Chicago": "芝加哥", "Chongqing": "重庆", "Dallas": "达拉斯",
    "Denver": "丹佛", "Guangzhou": "广州", "Helsinki": "赫尔辛基", "Hong Kong": "香港",
    "Houston": "休斯顿", "Istanbul": "伊斯坦布尔", "Jeddah": "吉达", "Jinan": "济南",
    "Karachi": "卡拉奇", "Kuala Lumpur": "吉隆坡", "London": "伦敦", "Los Angeles": "洛杉矶",
    "Lucknow": "勒克瑙", "Madrid": "马德里", "Manila": "马尼拉", "Mexico City": "墨西哥城",
    "Miami": "迈阿密", "Milan": "米兰", "Moscow": "莫斯科", "Munich": "慕尼黑",
    "Nyc": "纽约", "Panama City": "巴拿马城", "Paris": "巴黎", "Qingdao": "青岛",
    "San Francisco": "旧金山", "Sao Paulo": "圣保罗", "Seattle": "西雅图", "Seoul": "首尔",
    "Shanghai": "上海", "Shenzhen": "深圳", "Singapore": "新加坡", "Taipei": "台北",
    "Tel Aviv": "特拉维夫", "Tokyo": "东京", "Toronto": "多伦多", "Warsaw": "华沙",
    "Wellington": "惠灵顿", "Wuhan": "武汉", "Zhengzhou": "郑州",
}
METEO_URL_OVERRIDE = {
    "Amsterdam": "https://www.meteoblue.com/en/weather/week/amsterdam-airport-schiphol_the-netherlands_6296680",
    "Ankara": "https://www.meteoblue.com/en/weather/week/ankara-esenbo%C4%9Fa-international-airport_republic-of-t%C3%BCrkiye_6299725",
    "Atlanta": "https://www.meteoblue.com/en/weather/week/hartsfield-jackson-atlanta-international-airport_united-states_4199556",
    "Austin": "https://www.meteoblue.com/en/weather/week/austin-bergstrom-international-airport_united-states_4673601",
    "Beijing": "https://www.meteoblue.com/en/weather/week/beijing-capital-international-airport_china_6301354",
    "Buenos Aires": "https://www.meteoblue.com/en/weather/week/buenos-aires_argentina_3435910",
    "Busan": "https://www.meteoblue.com/en/weather/week/busan-%2F-gimhae-international-airport_south-korea_6300424",
    "Cape Town": "https://www.meteoblue.com/en/weather/week/cape-town-international-airport_south-africa_3368972",
    "Chengdu": "https://www.meteoblue.com/en/weather/week/chengdu-shuangliu-international-airport_china_6301392",
    "Chicago": "https://www.meteoblue.com/en/weather/week/chicago-o%27hare-international-airport_united-states_4887479",
    "Chongqing": "https://www.meteoblue.com/en/weather/week/chongqing-jiangbei-international-airport_china_6301390",
    "Dallas": "https://www.meteoblue.com/en/weather/week/dallas-love-field_united-states_4684922",
    "Denver": "https://www.meteoblue.com/en/weather/week/denver-international-airport_united-states_5419401",
    "Guangzhou": "https://www.meteoblue.com/en/weather/week/guangzhou-baiyun-international-airport_china_6301359",
    "Helsinki": "https://www.meteoblue.com/en/weather/week/helsinki-airport_finland_6301511",
    "Hong Kong": "https://www.meteoblue.com/en/weather/week/chek-lap-kok-airport_hong-kong_6301089",
    "Houston": "https://www.meteoblue.com/en/weather/week/houston-hobby_united-states_4741989",
    "Istanbul": "https://www.meteoblue.com/en/weather/week/istanbul-airport_republic-of-t%c3%bcrkiye_11838481",
    "Jeddah": "https://www.meteoblue.com/en/weather/week/jeddah-king-abdul-aziz-international-airport_saudi-arabia_6300018",
    "Jinan": "https://www.meteoblue.com/en/weather/week/jinan-yaoqiang-international-airport_china_6453420",
    "Karachi": "https://www.meteoblue.com/en/weather/week/karachi-airport_pakistan_6300111",
    "Kuala Lumpur": "https://www.meteoblue.com/en/weather/week/kuala-lumpur-international-airport_malaysia_6301255",
    "London": "https://www.meteoblue.com/en/weather/week/london-city-airport_united-kingdom_6296599",
    "Los Angeles": "https://www.meteoblue.com/en/weather/week/los-angeles-international-airport_united-states_5368418",
    "Lucknow": "https://www.meteoblue.com/en/weather/week/chaudhary-charan-singh-airport_india_6301873",
    "Madrid": "https://www.meteoblue.com/en/weather/week/adolfo-su%C3%A1rez-madrid%E2%80%93barajas-airport_spain_6299345",
    "Manila": "https://www.meteoblue.com/en/weather/week/ninoy-aquino-international-airport_philippines_1701661",
    "Mexico City": "https://www.meteoblue.com/en/weather/week/benito-ju%C3%A1rez-international-airport_mexico_6299859",
    "Miami": "https://www.meteoblue.com/en/weather/week/miami-international-airport_united-states_4164181",
    "Milan": "https://www.meteoblue.com/en/weather/week/milano-malpensa-airport_italy_3174133",
    "Moscow": "https://www.meteoblue.com/en/weather/week/vnukovo-international-airport_russia_6301018",
    "Munich": "https://www.meteoblue.com/en/weather/week/munich-international-airport_germany_3208399",
    "Nyc": "https://www.meteoblue.com/en/weather/week/laguardia-airport_united-states_5123698",
    "Panama City": "https://www.meteoblue.com/en/weather/week/albrook-marcos-a.-gelabert-international-airport_panama_3704579",
    "Paris": "https://www.meteoblue.com/en/weather/week/paris%E2%80%93le-bourget-airport_france_2988502",
    "Qingdao": "https://www.meteoblue.com/en/weather/week/qingdao-liuting-international-airport_china_6301387",
    "San Francisco": "https://www.meteoblue.com/en/weather/week/san-francisco-international-airport_united-states_5391989",
    "Sao Paulo": "https://www.meteoblue.com/en/weather/week/s%C3%A3o-paulo%E2%80%93guarulhos-international-airport_brazil_6300629",
    "Seattle": "https://www.meteoblue.com/en/weather/week/seattle-tacoma-international-airport_united-states_5809876",
    "Seoul": "https://www.meteoblue.com/en/weather/week/incheon-international-airport_south-korea_6300433",
    "Shanghai": "https://www.meteoblue.com/en/weather/week/shanghai-pudong-international-airport_china_6301386",
    "Shenzhen": "https://www.meteoblue.com/en/weather/week/shenzhen-bao%27an-international-airport_china_6301365",
    "Singapore": "https://www.meteoblue.com/en/weather/week/singapore-changi-airport_singapore_1880725",
    "Taipei": "https://www.meteoblue.com/en/weather/week/taiwan-taoyuan-international-airport_taiwan_1980018",
    "Tel Aviv": "https://www.meteoblue.com/en/weather/week/ben-gurion-airport_israel_390285",
    "Tokyo": "https://www.meteoblue.com/en/weather/week/tokyo-international-airport_japan_6300412",
    "Toronto": "https://www.meteoblue.com/en/weather/week/toronto-pearson-international-airport_canada_6296338",
    "Warsaw": "https://www.meteoblue.com/en/weather/week/warsaw-chopin-airport_poland_6296786",
    "Wellington": "https://www.meteoblue.com/en/weather/week/wellington-international-airport_new-zealand_6244688",
    "Wuhan": "https://www.meteoblue.com/en/weather/week/wuhan-tianhe-international-airport_china_6301368",
    "Zhengzhou": "https://www.meteoblue.com/en/weather/week/zhengzhou-xinzheng-international-airport_china_6301367",
}

def _client():
    return httpx.AsyncClient(http1=True, http2=False, verify=False, timeout=30,
                             proxy=(PROXY_URL or None), follow_redirects=True,
                             limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=15))

# ── Polymarket ──────────────────────────────────────────────────────────────

def parse_city_date(slug):
    m = re.match(r'(highest|lowest)-temperature-in-(.+?)-on-([a-z]+-\d{1,2}-2026)', slug)
    if not m: return {}
    return {"city": m.group(2).replace("-", " ").title(), "date": datetime.strptime(m.group(3), "%B-%d-%Y").strftime("%Y-%m-%d"),
            "date_display": datetime.strptime(m.group(3), "%B-%d-%Y").strftime("%m/%d"), "direction": m.group(1)}

def parse_temp(slug):
    m = re.search(r'-(\d{2,3}(?:-\d{2,3})?(?:pt\d+)?(?:c|f))(?:orbelow|orhigher)?$', slug)
    if not m: return None
    raw = m.group(1); unit = "C" if raw.endswith("c") else ("F" if raw.endswith("f") else "")
    num = raw.rstrip("cf").replace("pt", ".")
    ttype = "exact"
    if "orbelow" in slug: ttype = "below"
    elif "orhigher" in slug: ttype = "above"
    try: tv = float(num.split("-")[0])
    except ValueError: tv = 0
    return {"temp_display": num + "\u00b0" + unit, "temp_value": tv, "type": ttype}

def extract_slugs(html):
    seen = set(); slugs = []
    for m in re.finditer(r'/event/((?:highest|lowest)-temperature-in-[a-z0-9\-]+-2026)', html):
        s = m.group(1)
        if s not in seen: seen.add(s); slugs.append(s)
    return slugs

async def fetch_event(client, slug):
    try:
        r = await client.get(f"{GAMMA_HOST}/events/slug/{slug}"); r.raise_for_status()
        return r.json()
    except: return None

def _prices(raw):
    if not raw: return []
    if isinstance(raw, str):
        try: raw = json.loads(raw)
        except: return []
    return [float(x) for x in raw] if isinstance(raw, list) else []

def build_event(slug, event):
    info = parse_city_date(slug)
    mkts = []
    for m in event.get("markets", []):
        t = parse_temp(m.get("slug", "")); p = _prices(m.get("outcomePrices"))
        mkts.append({"slug": m.get("slug", ""), "temp": t["temp_display"] if t else None,
                      "temp_value": t["temp_value"] if t else None, "temp_type": t["type"] if t else None,
                      "yes_price": round(p[0], 4) if p else None, "yes_pct": round(p[0]*100, 1) if p else None})
    mkts.sort(key=lambda x: x.get("temp_value", 0) or 0)
    return {**info, "slug": slug, "markets": mkts}

def group(data):
    groups = {}
    for item in data:
        k = (item["city"], item["date"])
        if k not in groups:
            groups[k] = {"city": item["city"], "city_cn": CITY_CN.get(item["city"], ""), "date": item["date"], "date_display": item["date_display"],
                         "icao": AIRPORT_CODES.get(item["city"], ""), "noon_bj": item.get("noon_bj"),
                         "wind_heat": WIND_HEAT_MAP.get(item["city"], ""), "highest": None, "lowest": None}
        groups[k][item["direction"]] = item
    return sorted(groups.values(), key=lambda x: (x["city"], x["date"]))

# ── Open-Meteo ──────────────────────────────────────────────────────────────

async def _fetch_om(client, lat, lon, model):
    try:
        r = await client.get(f"{METEOC_API}?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min&hourly=temperature_2m,wind_direction_10m,wind_speed_10m&models={model}&forecast_days=5&timezone=auto")
        r.raise_for_status(); j = r.json()
        d = j["daily"]; htime = j["hourly"]["time"]; htemp = j["hourly"]["temperature_2m"]
        hdir = j["hourly"].get("wind_direction_10m") or [None] * len(htime)
        hspd = j["hourly"].get("wind_speed_10m") or [None] * len(htime)
        off = j.get("utc_offset_seconds", 0)
        out = {}
        for t, mx, mn in zip(d["time"], d["temperature_2m_max"], d["temperature_2m_min"]):
            day_i = [i for i, tm in enumerate(htime) if tm.startswith(t)]
            max_h = min_h = None
            wind_deg = wind_kmh = None
            if day_i:
                vals = [htemp[i] for i in day_i]
                def _bj(idx):
                    lh = int(htime[day_i[idx]][11:13])
                    return ((lh * 3600 - off + 8 * 3600) % 86400) // 3600
                mxi = max(range(len(vals)), key=lambda k: vals[k])
                mni = min(range(len(vals)), key=lambda k: vals[k])
                max_h = _bj(mxi); min_h = _bj(mni)
                if hdir[day_i[mxi]] is not None:
                    wind_deg = int(hdir[day_i[mxi]])
                    wind_kmh = round(hspd[day_i[mxi]], 1)
            out[t] = {"max": mx, "min": mn, "max_hour_bj": max_h, "min_hour_bj": min_h,
                      "wind_deg": wind_deg, "wind_kmh": wind_kmh}
        return out, off
    except: return {}, None

# ── Meteoblue ───────────────────────────────────────────────────────────────

def _parse_mb_page(html):
    """Parse meteoblue forecast page HTML -> {date: {max, min}} in Celsius."""
    soup = BeautifulSoup(html, "html.parser")
    tabs = soup.select("#tabs .tab a")
    if not tabs: return {}

    is_f = any("\u00b0F" in (t.select_one(".tab-temp-max") or "").get_text() for t in tabs if t.select_one(".tab-temp-max"))
    
    fc = {}
    for t in tabs:
        mx = t.select_one(".tab-temp-max"); mn = t.select_one(".tab-temp-min"); tm = t.select_one("time")
        if not mx or not mn or not tm: continue
        dt = tm.get("datetime", "").split("T")[0]
        if not dt: continue
        mx_v = int(re.sub(r"[^\d]", "", mx.get_text(strip=True)) or "0")
        mn_v = int(re.sub(r"[^\d]", "", mn.get_text(strip=True)) or "0")
        if is_f:
            mx_v = round((mx_v - 32) * 5.0 / 9.0)
            mn_v = round((mn_v - 32) * 5.0 / 9.0)
        fc[dt] = {"max": mx_v, "min": mn_v}
    return fc

def scrape_meteoblue(city):
    """Scrape meteoblue forecast using ICAO code search or direct URL."""
    icao = AIRPORT_CODES.get(city, "")
    search_city = METEO_CITY_NAMES.get(city, city)

    try:
        with httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=(PROXY_URL or None), follow_redirects=True) as c:
            # Direct URL override
            if city in METEO_URL_OVERRIDE:
                r = c.get(METEO_URL_OVERRIDE[city], headers=HEADERS)
                if r.status_code == 200: return _parse_mb_page(r.text)
                return {}

            city_pat = search_city.lower().replace(" ", "-")

            # Try 1: city + ICAO
            best = None
            if icao:
                r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": f"{search_city} {icao}"}, headers=HEADERS)
                if r.status_code == 200:
                    links = re.findall(r'/en/weather/week/([^"]+)', r.text)
                    for slug in links:
                        if city_pat in slug.lower():
                            best = slug
                            if "international" in slug.lower() and "daxing" not in slug.lower():
                                break

            # Try 2: city name only
            if not best:
                r = c.get("https://www.meteoblue.com/en/weather/search/index", params={"query": search_city}, headers=HEADERS)
                if r.status_code == 200:
                    links = re.findall(r'/en/weather/week/([^"]+)', r.text)
                    for slug in links:
                        if city_pat in slug.lower():
                            best = slug; break
                    if not best and links: best = links[0]

            if not best: return {}
            url = f"https://www.meteoblue.com/en/weather/week/{best}"
            r2 = c.get(url, headers=HEADERS)
            if r2.status_code != 200: return {}
            return _parse_mb_page(r2.text)
    except: return {}

async def fetch_meteoblue(client, city):
    for _ in range(2):
        r = await asyncio.to_thread(scrape_meteoblue, city)
        if r: return r
        await asyncio.sleep(1)
    return {}

# ── Matching ────────────────────────────────────────────────────────────────

def calc_temp(city, c_val, direction):
    return c_val * 9.0 / 5.0 + 32.0 if city in FAHRENHEIT_CITIES else c_val

def match_market(forecast, markets):
    if not markets: return None
    fi = int(round(forecast))
    for m in markets:
        if m.get("temp_type") != "exact" or m.get("temp_value") is None: continue
        tv = m["temp_value"]
        if "F" in (m.get("temp") or ""):
            if tv <= fi <= tv + 1: return m
        elif tv == fi: return m
    exact = [m for m in markets if m.get("temp_type") == "exact" and m.get("temp_value") is not None]
    return min(exact, key=lambda m: abs(m["temp_value"] - fi)) if exact else None

# ── Main ────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("Weather Dashboard  |  GFS GEM ICON meteoblue RP5")
    print("=" * 60)

    async with _client() as client:
        print("\n--- Polymarket ---")
        r = await client.get("https://polymarket.com/zh/weather")
        slugs = extract_slugs(r.text)
        print(f"Found {len(slugs)} event slugs (page)")
        # 补全: 页面某日期城市不全时, 按已知城市表生成该日期全部 slug 再查 gamma
        city_set = {info["city"] for s in slugs if (info := parse_city_date(s))} | set(AIRPORT_CODES.keys())
        date_cnt = {}
        for s in slugs:
            info = parse_city_date(s)
            if info: date_cnt[info["date"]] = date_cnt.get(info["date"], 0) + 1
        seen = set(slugs)
        added = 0
        for s in list(slugs):
            info = parse_city_date(s)
            if not info: continue
            dt = datetime.strptime(info["date"], "%Y-%m-%d")
            dstr = f"{dt.strftime('%B').lower()}-{dt.day}-{dt.year}"
            if date_cnt.get(info["date"], 0) >= 2 * len(city_set):
                continue  # 该日期已全量
            for city in city_set:
                base = city.lower().replace(" ", "-")
                for direction in ("highest", "lowest"):
                    ns = f"{direction}-temperature-in-{base}-on-{dstr}"
                    if ns not in seen:
                        seen.add(ns); slugs.append(ns); added += 1
        print(f"Added {added} generated slugs")
        pm = []
        for i in range(0, len(slugs), 10):
            batch = slugs[i:i+10]
            for s, d in zip(batch, await asyncio.gather(*[fetch_event(client, s) for s in batch])):
                if d: pm.append(build_event(s, d))
            print(f"  {min(i+10, len(slugs))}/{len(slugs)}")

        cities = sorted({r["city"] for r in pm})
        print(f"\n--- {len(cities)} cities, 5 models each ---")

        forecasts = {}
        sem = asyncio.Semaphore(4)
        async def do_city(city, lat, lon):
            om_tasks = [asyncio.create_task(_fetch_om(client, lat, lon, mk)) for _, mk in FORECAST_MODELS]
            async with sem:
                await asyncio.sleep(0.5)
                mb_task = asyncio.create_task(fetch_meteoblue(client, city))
                rp5_task = asyncio.create_task(asyncio.to_thread(scrape_rp5, city))
            om_results = await asyncio.gather(*om_tasks)
            off = None
            for d, o in om_results:
                if o is not None: off = o; break
            return {"om": [d for d, _ in om_results], "off": off,
                    "mb": await mb_task, "rp5": await rp5_task}

        for i, city in enumerate(cities):
            coords = CITY_COORDS.get(city, (0, 0))
            res = await do_city(city, *coords)
            results = res["om"] + [res["mb"], res["rp5"]]
            names = [mn for mn, _ in FORECAST_MODELS] + ["METEO", "RP5"]
            all_dates = set()
            for r in results: all_dates.update(r.keys())
            fc = {}
            for dt in sorted(all_dates):
                models = []
                for nm, r in zip(names, results):
                    e = r.get(dt, {})
                    if e.get("max") is not None: models.append({"name": nm, "max": e["max"], "min": e["min"],
                                                                  "max_hour_bj": e.get("max_hour_bj"), "min_hour_bj": e.get("min_hour_bj"),
                                                                  "wind_deg": e.get("wind_deg"), "wind_kmh": e.get("wind_kmh")})
                if models: fc[dt] = {"models": models}
            forecasts[city] = {"off": res["off"], "days": fc}
            if (i+1) % 5 == 0: print(f"  {i+1}/{len(cities)}")

        print("\n--- Matching ---")
        for evt in pm:
            city, dt, direction = evt["city"], evt["date"], evt["direction"]
            fcd = forecasts.get(city, {})
            off = fcd.get("off")
            evt["noon_bj"] = ((12 * 3600 - off + 8 * 3600) % 86400) // 3600 if off is not None else None
            fc = fcd.get("days", {}).get(dt, {}).get("models", [])
            mf = []
            for m in fc:
                raw = m["max"] if direction == "highest" else m["min"]
                at = calc_temp(city, raw, direction)
                matched = match_market(at, evt["markets"])
                url = None
                if m["name"] == "METEO":
                    url = METEO_URL_OVERRIDE.get(city, f"https://www.meteoblue.com/en/weather/search/index?query={METEO_CITY_NAMES.get(city,city)}")
                elif m["name"] == "RP5":
                    from rp5_scraper import get_rp5_url
                    url = get_rp5_url(city)
                mf.append({"model": m["name"], "temp": round(at), "pct": matched["yes_pct"] if matched else None, "url": url,
                           "max_hour_bj": m.get("max_hour_bj"), "min_hour_bj": m.get("min_hour_bj"),
                           "wind_deg": m.get("wind_deg"), "wind_kmh": m.get("wind_kmh")})
            evt["forecasts"] = mf
        print(f"  Matched {sum(1 for e in pm if e.get('forecasts'))}/{len(pm)}")

    grouped = group(pm)
    for row in grouped:
        for d in ("highest", "lowest"):
            obj = row.get(d)
            if not obj: continue
            ex = [m for m in obj.get("markets", []) if m.get("temp_type") == "exact" and m.get("yes_price")]
            best = max(ex, key=lambda x: x["yes_price"]) if ex else None
            obj["predicted_temp"] = best["temp"] if best else None
            obj["predicted_prob"] = best["yes_pct"] if best else None

    output = {"updated_at": datetime.now().isoformat(), "count": len(grouped), "rows": grouped}
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f: template = f.read()
    html = template.replace("__DATA_PLACEHOLDER__", json.dumps(output, ensure_ascii=False))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f: f.write(html)
    # Also save for Flask API
    with open(os.path.join(SCRIPT_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    # Save historical copy
    history_dir = os.path.join(SCRIPT_DIR, "history")
    os.makedirs(history_dir, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    hist_file = os.path.join(history_dir, f"{today_str}.json")
    with open(hist_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    # Save timestamped snapshot (keep multiple runs per day, e.g. morning + evening)
    ts_file = os.path.join(history_dir, f"{today_str}_{datetime.now().strftime('%H%M')}.json")
    with open(ts_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    fc_count = sum(1 for r in grouped for d in ("highest", "lowest") if r.get(d) and r[d].get("forecasts"))
    print(f"\nDone! {len(grouped)} rows, {fc_count} forecasts")
    webbrowser.open("file:///" + OUTPUT_FILE.replace("\\", "/"))

if __name__ == "__main__":
    asyncio.run(main())
