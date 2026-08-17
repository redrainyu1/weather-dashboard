"""最高温度预测准确度统计（METEO/RP5）：历史快照 vs Polymarket 已结算市场"""
import json, os, glob, sys, asyncio, argparse, re
import httpx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:7897")
GAMMA_HOST = "https://gamma-api.polymarket.com"
ACTUALS_FILE = os.path.join(SCRIPT_DIR, "history", "actuals.json")

def load_actuals():
    """本地已结算温度存档 {slug: temp}，避免每次重查 gamma"""
    try:
        with open(ACTUALS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_actuals(a):
    with open(ACTUALS_FILE, "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=1)

def snapshot_hour(path):
    """从历史文件名/内容提取快照生成的小时(0-23)，无法判断返回 None"""
    base = os.path.basename(path)
    m = re.search(r'_(\d{2})\d{2}\.json$', base)
    if m:
        return int(m.group(1))
    return None

from datetime import datetime, timedelta

def snapshot_time(path):
    """快照生成时刻 HH:MM（从文件名），无则返回空串"""
    base = os.path.basename(path)
    m = re.search(r'_(\d{4})\.json$', base)
    if m:
        return f"{m.group(1)[:2]}:{m.group(1)[2:]}"
    return ""

BUCKETS = [(6, 9, "06-09"), (9, 12, "09-12"), (12, 15, "12-15"),
           (15, 18, "15-18"), (18, 21, "18-21"), (21, 24, "21-24")]

def bucket_of(hour):
    if hour is None:
        return "其他"
    for a, b, name in BUCKETS:
        if a <= hour < b:
            return name
    return "其他"

def snap_abs(snap_date_str, hour):
    """快照（北京时区）绝对时刻"""
    try:
        return datetime.strptime(snap_date_str, "%Y-%m-%d").replace(hour=hour)
    except Exception:
        return None

def tz_of(noon_bj):
    """noon_bj -> 当地时区偏移（当地-UTC 小时）"""
    if noon_bj is None:
        return None
    t = (20 - noon_bj) % 24
    if t > 12:
        t -= 24
    return t

def bj_to_local(bj_dt, noon_bj):
    """北京绝对时刻 -> 当地时刻"""
    tz = tz_of(noon_bj)
    if tz is None:
        return None
    return bj_dt + timedelta(hours=tz - 8)

def noon_abs(date_str, noon_bj):
    """事件当地正午12点对应的北京绝对时刻（datetetime）"""
    if noon_bj is None:
        return None
    d = datetime.strptime(date_str, "%Y-%m-%d")
    # 当地正午的北京钟点 noon_bj ∈ [0,7] 时落在北京次日（美东/美西等 tz<=-4 城市），
    # ∈ [8,23] 时落在北京当日（UTC+8 及以上城市，如东京/首尔 noon_bj=11）
    if noon_bj < 8:
        d += timedelta(days=1)
    return d.replace(hour=noon_bj, minute=0)

def peak_abs(date_str, noon_bj, peak_off_h=3.0):
    """事件当天最高温出现的北京绝对时刻：
    noon_bj 定位当地正午的北京时刻，peak_off_h = 最高温时刻 - 正午（小时），
    默认 3.0 = 当地 15:00"""
    nd = noon_abs(date_str, noon_bj)
    if nd is None:
        return None
    return nd + timedelta(hours=peak_off_h)

AM_PM_RE = re.compile(r'^(\d{1,2}):(\d{2}) (AM|PM)$')

def parse_wg_peak(html):
    """从 Wunderground Daily Observations 页 HTML 取最高温时刻（相对正午的小时偏移）
    返回 peak_off_h（如 -1.0=上午11点、3.6=下午3点36），解析失败返回 None"""
    rows = re.findall(r'<td>(\d{1,2}:\d{2} (?:AM|PM))</td>\s*<td[^>]*>([\d.]+)', html)
    mx = None
    for tm, v in rows:
        m = AM_PM_RE.match(tm)
        if not m:
            continue
        h = int(m.group(1)) % 12 + (12 if m.group(3) == 'PM' else 0)
        tv = float(v)
        if mx is None or tv > mx[2]:
            mx = (h, int(m.group(2)), tv)
    if mx is None:
        return None
    return mx[0] + mx[1] / 60.0 - 12.0

async def fetch_wg_peak(client, resolution_source, date_str, noon_bj=None):
    """抓取站点该日观测，返回最高温出现时的北京绝对时刻（ISO 字符串）"""
    if not resolution_source:
        return None
    y, mo, d = date_str.split('-')
    url = f"{resolution_source}/date/{y}-{int(mo)}-{int(d)}"
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        off_h = parse_wg_peak(r.content.decode('latin-1'))
        if off_h is None:
            return None
        if noon_bj is None:
            return None
        nd = noon_abs(date_str, noon_bj)
        if nd is None:
            return None
        return (nd + timedelta(hours=off_h)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

SITE_RE = re.compile(r'timeseries\?site=([A-Za-z0-9]{3,5})', re.IGNORECASE)

async def fetch_metar_peak(client, description, event_date, noon_bj=None):
    """NOAA METAR（aviationweather.gov，与 WRH timeseries 同源）：
    取事件当地日期内温度最高观测的时刻（UTC+8=北京绝对时刻，ISO 字符串）"""
    m = SITE_RE.search(description or "")
    if not m:
        if "weather.gov.hk" in (description or ""):
            site = "vhhh"
        else:
            return None
    else:
        site = m.group(1).lower()
    off = None
    if noon_bj is not None:
        off = (20 - noon_bj) % 24
        if off > 12:
            off -= 24
    url = f"https://aviationweather.gov/api/data/metar?ids={site}&date={event_date}T00:00:00Z&hours=48&format=json&taf=false"
    if off is not None:
        # NOAA date 参数是窗口"结束"时间（往前 hours 小时）。
        # 本地 event_date 00:00 对应 UTC = event_dateT00:00Z - off，
        # 窗口结束 = 本地 event_date 次日 00:00 的 UTC = event_dateT00:00Z + (24-off)h，
        # hours=48 后仍比本地全天多出 off+24h，保证当地一整天观测都在窗口内。
        end_utc = (datetime.strptime(event_date, "%Y-%m-%d") + timedelta(hours=48 - off)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"https://aviationweather.gov/api/data/metar?ids={site}&date={end_utc}&hours=48&format=json&taf=false"
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return None
        obs = r.json()
        if not isinstance(obs, list) or not obs:
            return None
        best = None
        for ob in obs:
            t = ob.get("temp")
            ts = ob.get("obsTime")
            if t is None or ts is None:
                continue
            if off is not None:
                lokal = datetime.utcfromtimestamp(int(ts)) + timedelta(hours=off)
                if lokal.strftime("%Y-%m-%d") != event_date:
                    continue
            if best is None or t > best[1]:
                best = (int(ts), t)
        if best is None:
            return None
        return (datetime.utcfromtimestamp(best[0]) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

def load_history(period=None, model="meteo", peak_off_map=None):
    """返回 {slug: {city, date, temp, ...}}
    按 (slug, 快照日期) 去重：全部时段取每个日期最后一次快照；
    period 如 (6, 12) 只取每个日期 6-12 时生成（的最后一次）快照；
    只保留最高温时刻（peak_off_map 给出真实偏移，缺省按当地 15:00）之前作出的预测"""
    model_name = model.upper()
    out = {}
    for f in sorted(glob.glob(os.path.join(SCRIPT_DIR, "history", "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        hour = snapshot_hour(f)
        if hour is None:
            up = d.get("updated_at", "")
            try:
                hour = int(up[11:13])
            except Exception:
                hour = None
        if hour is None:
            continue  # 跳过无时刻的纯日期快照（旧格式，与 HHMM 快照重复）
        if period and not (period[0] <= hour < period[1]):
            continue
        snap_date = os.path.basename(f)[:10]
        for row in d.get("rows", []):
            h = row.get("highest")
            if not h or not h.get("slug"):
                continue
            # 只用事件日当地当天生成的预测（快照换算到当地日期后须等于事件日）
            nb = h.get("noon_bj")
            if nb is not None:
                tstr = snapshot_time(f)
                mm = int(tstr[3:5]) if len(tstr) >= 5 else 0
                local = bj_to_local(datetime.strptime(snap_date, "%Y-%m-%d") + timedelta(hours=hour, minutes=mm), nb)
                if local is None or local.strftime("%Y-%m-%d") != h.get("date", "")[:10]:
                    continue
                local_date = local.strftime("%Y-%m-%d")
                local_hhmm = local.strftime("%H:%M")
            else:
                if h.get("date", "")[:10] != snap_date:
                    continue
                local_date = snap_date
                local_hhmm = snapshot_time(f)
            temp = None
            for fc in h.get("forecasts", []):
                if fc.get("model") == model_name and fc.get("temp") is not None:
                    temp = fc["temp"]
                    break
            if temp is None:
                continue
            out.setdefault((h["slug"], local_date), []).append(
                {"city": row["city"], "date": h["date"], "temp": temp,
                 "date_display": row.get("date_display", ""),
                 "time": snapshot_time(f), "snap_bj": snap_date,
                 "local_date": local_date, "local_hhmm": local_hhmm,
                 "hour": hour, "noon_bj": h.get("noon_bj")})
    res = {}
    for (slug, local_date), lst in out.items():
        pk = None
        if peak_off_map:
            po = peak_off_map.get(slug)
            if isinstance(po, (int, float)):
                pk = peak_abs(lst[0]["date"], lst[0].get("noon_bj"), float(po))
            elif isinstance(po, dict):
                if po.get("peak_bj"):
                    try:
                        pk = datetime.strptime(po["peak_bj"], "%Y-%m-%d %H:%M")
                    except Exception:
                        pk = None
                elif po.get("peak_off_h") is not None:
                    pk = peak_abs(lst[0]["date"], lst[0].get("noon_bj"), float(po["peak_off_h"]))
        if pk is None:
            pk = peak_abs(lst[0]["date"], lst[0].get("noon_bj"), 3.0)
        # 取事件日当地当天、预测生成时刻早于峰值、
        # 且最接近"峰值首次出现时刻 - 1 小时"的那一条（用户规则）
        def bj_abs(v):
            return (datetime.strptime(v["snap_bj"], "%Y-%m-%d") + timedelta(hours=v["hour"],
                    minutes=int(v["time"][3:5]) if len(v.get("time", "")) >= 5 else 0))
        valid = [v for v in lst if pk is None or bj_abs(v) < pk]
        if not valid:
            continue
        if pk is None:
            best = valid[0]
        else:
            target = pk - timedelta(hours=1)
            # 容差 ±1h：峰前 1 小时左右没有预测快照的事件不参与统计
            near = [v for v in valid if abs((bj_abs(v) - target).total_seconds()) <= 3600]
            if not near:
                continue
            best = min(near, key=lambda v: abs((bj_abs(v) - target).total_seconds()))
        res[(slug, local_date)] = best
    return res

def get_actual_temp(slug, event):
    """从已结算事件找 YES=1 的市场温度档"""
    if not event:
        return None
    for m in event.get("markets", []):
        try:
            prices = json.loads(m.get("outcomePrices", "[]"))
        except Exception:
            continue
        if prices and (prices[0] == 1 or prices[0] == "1"):
            # 从 market slug 解析温度档
            import re
            mt = re.search(r'-(\d{2,3}(?:pt\d+)?)[cf](?:orbelow|orhigher)?$', m.get("slug", ""))
            if mt:
                return float(mt.group(1).replace("pt", "."))
    return None

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--period', default=None, help='快照时段筛选，如 6-12 = 只统计早上6:00-12:00生成的预测')
    parser.add_argument('--model', default='meteo', choices=['meteo', 'rp5'], help='预报模型：meteo 或 rp5')
    parser.add_argument('--out', default=None, help='输出文件名')
    args = parser.parse_args()
    period = None
    if args.period:
        a, b = args.period.split('-')
        period = (int(a), int(b))
    out_file = args.out or f"accuracy_{args.model}{'_morning' if args.period == '6-12' else ''}.json"
    actuals = load_actuals()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
    async with httpx.AsyncClient(http1=True, http2=False, verify=False, timeout=30,
                                 proxy=(PROXY_URL or None), follow_redirects=True, headers=headers,
                                 limits=httpx.Limits(max_keepalive_connections=5)) as client:
        hist = load_history(period, model=args.model)
        noon_map = {slug: v.get("noon_bj") for (slug, _), v in hist.items()}
        slugs = sorted({slug for slug, _ in hist.keys()})
        todo = [s for s in slugs if s not in actuals]
        print(f"本地已存档结算: {len(actuals)}，本次需查询: {len(todo)}")
        for i in range(0, len(todo), 3):
            batch = todo[i:i + 3]
            rs = await asyncio.gather(*[
                client.get(f"{GAMMA_HOST}/events/slug/{s}") for s in batch
            ], return_exceptions=True)
            for s, r in zip(batch, rs):
                if isinstance(r, Exception) or r.status_code != 200:
                    continue
                evt = r.json()
                t = get_actual_temp(s, evt)
                if t is not None:
                    ev_date = evt.get("eventDate", "")
                    pb = await fetch_wg_peak(client, evt.get("resolutionSource"), ev_date, noon_map.get(s))
                    if pb is None:
                        pb = await fetch_metar_peak(client, evt.get("description"), ev_date, noon_map.get(s))
                    actuals[s] = {"temp": t, "peak_bj": pb}
            print(f"  {min(i+3, len(todo))}/{len(todo)}")
    save_actuals(actuals)
    print(f"已结算: {len(actuals)}（本次新增 {len(set(actuals) - set(load_actuals()))}）")

    hist = load_history(period, model=args.model, peak_off_map=actuals)
    print(f"[{args.model.upper()}] 历史预测条目(峰前): {len(hist)}")

    # 汇总
    rows = []
    for (slug, snap_date), v in hist.items():
        act = actuals.get(slug)
        if act is None:
            continue
        peak_local = None
        if isinstance(act, dict):
            pb = act.get("peak_bj")
            if pb and v.get("noon_bj") is not None:
                try:
                    peak_local = bj_to_local(datetime.strptime(pb, "%Y-%m-%d %H:%M"), v["noon_bj"]).strftime("%H:%M")
                except Exception:
                    peak_local = None
            act = act.get("temp")
        if act is None:
            continue
        err = v["temp"] - act
        rows.append({"city": v["city"], "date": v["date"], "date_display": v["date_display"],
                     "snap_date": snap_date, "time": v.get("time", ""),
                     "local_hhmm": v.get("local_hhmm", ""), "hour": v.get("hour"),
                     "meteo": v["temp"], "actual": act, "err": round(err, 1),
                     "peak_local": peak_local})

    if not rows:
        print("无已结算数据")
        return

    from collections import defaultdict
    abs_errs = [abs(r["err"]) for r in rows]
    errs = [r["err"] for r in rows]
    mae = sum(abs_errs) / len(abs_errs)
    bias = sum(errs) / len(errs)

    by_city = defaultdict(list)
    for r in rows:
        by_city[r["city"]].append(r)
    city_stats = []
    for city, lst in sorted(by_city.items()):
        ae = [abs(x["err"]) for x in lst]
        periods = {}
        for x in lst:
            b = bucket_of(x.get("hour"))
            if b not in periods:
                periods[b] = {"n": 0, "errs": []}
            periods[b]["n"] += 1
            periods[b]["errs"].append(abs(x["err"]))
        pstat = {}
        for b, v in periods.items():
            pstat[b] = {"n": v["n"], "mae": round(sum(v["errs"]) / len(v["errs"]), 2)}
        best = None
        for b, v in pstat.items():
            if v["n"] >= 3 and (best is None or pstat[b]["mae"] < pstat[best]["mae"]):
                best = b
        city_stats.append({"city": city, "n": len(lst),
                           "mae": round(sum(ae) / len(ae), 2),
                           "periods": pstat, "best_period": best})

    report = {
        "model": args.model.upper(),
        "n": len(rows),
        "mae": round(mae, 2),
        "bias": round(bias, 2),
        "rows": rows,
        "cities": city_stats,
    }
    with open(os.path.join(SCRIPT_DIR, out_file), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"\n[{args.model.upper()}] 样本 {report['n']} | MAE {report['mae']}°C | 偏差 {report['bias']:+.1f}°C")
    print("\n=== 每城市 ===")
    for c in city_stats:
        print(f"{c['city']:15s} n={c['n']:2d} MAE={c['mae']:4.2f}")

if __name__ == "__main__":
    asyncio.run(main())
