"""Simple Flask server - serves static dashboard + fix missing data."""
import subprocess, sys, os, json, re, asyncio, time
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import httpx
from bs4 import BeautifulSoup
from rp5_scraper import scrape_rp5

app = Flask(__name__)

_cache_file = os.path.join(SCRIPT_DIR, "data.json")
PROXY_URL = os.getenv("PROXY_URL", "http://127.0.0.1:7897")

# Import METEO_URL_OVERRIDE from serve module
from serve import METEO_URL_OVERRIDE

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-GB,en;q=0.9'}

def _parse_mb_page(html):
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

def scrape_meteoblue_city(city):
    url = METEO_URL_OVERRIDE.get(city)
    if not url: return {}
    try:
        with httpx.Client(http1=True, http2=False, verify=False, timeout=20, proxy=(PROXY_URL or None), follow_redirects=True) as c:
            r = c.get(url, headers=HEADERS)
            if r.status_code == 200:
                return _parse_mb_page(r.text)
    except: pass
    return {}

@app.route('/')
def index():
    resp = send_from_directory(SCRIPT_DIR, 'template.html')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

def _attach_actual_peaks(data):
    """给快照行附实际峰值时刻（来自 actuals.json 的 peak_bj，当地 HH:MM）"""
    try:
        import accuracy as acc
        from datetime import datetime
        actuals = acc.load_actuals()
        for row in data.get("rows", []):
            for key in ("highest", "lowest"):
                h = row.get(key)
                if not h or not h.get("slug"):
                    continue
                act = actuals.get(h["slug"])
                pb = act.get("peak_bj") if isinstance(act, dict) else None
                if not pb or h.get("noon_bj") is None:
                    continue
                try:
                    local = acc.bj_to_local(datetime.strptime(pb, "%Y-%m-%d %H:%M"), h["noon_bj"])
                    h["actual_peak"] = local.strftime("%H:%M") if local else None
                except Exception:
                    h["actual_peak"] = None
    except Exception:
        pass

def _attach_forecast_peaks(data):
    """给快照行附预测峰值时刻（来自 Open-Meteo Forecast API）"""
    try:
        import asyncio
        from forecast_peak import get_forecast_peak
        import httpx
        
        async def fetch_all():
            peaks = {}
            async with httpx.AsyncClient(timeout=15) as client:
                tasks = []
                cities = set()
                for row in data.get("rows", []):
                    city = row.get("city")
                    if city:
                        cities.add(city)
                
                for city in cities:
                    tasks.append(get_forecast_peak(client, city))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, dict) and r.get("city"):
                        peaks[r["city"]] = r
            return peaks
        
        peaks = asyncio.run(fetch_all())
        
        for row in data.get("rows", []):
            city = row.get("city")
            if city in peaks:
                for key in ("highest", "lowest"):
                    h = row.get(key)
                    if h:
                        h["forecast_peak"] = peaks[city].get("peak_time")
                        h["forecast_temp"] = peaks[city].get("peak_temp")
                        h["best_bet_time"] = peaks[city].get("best_bet_time")
    except Exception:
        pass

@app.route('/api/data')
def api_data():
    try:
        with open(_cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _attach_actual_peaks(data)
        _attach_forecast_peaks(data)
        return jsonify({"status": "ready", "data": data, "updated_at": data.get("updated_at"), "errors": []})
    except FileNotFoundError:
        return jsonify({"status": "no_data", "data": None})

def find_missing():
    """Analyze data.json and return list of cities with missing models."""
    try:
        with open(_cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except: return {"missing_meteo": [], "missing_rp5": [], "total": 0}
    
    cities_meteo = set()
    cities_rp5 = set()
    all_cities = set()
    
    for row in data.get("rows", []):
        for dir_key in ("highest", "lowest"):
            obj = row.get(dir_key)
            if not obj: continue
            fcs = obj.get("forecasts") or []
            for f in fcs:
                if f.get("temp") is None: continue
                if f["model"] == "METEO":
                    cities_meteo.add(row["city"])
                elif f["model"] == "RP5":
                    cities_rp5.add(row["city"])
        all_cities.add(row["city"])
    
    return {
        "missing_meteo": sorted(all_cities - cities_meteo),
        "missing_rp5": sorted(all_cities - cities_rp5),
        "total": len(all_cities),
    }

@app.route('/api/fix', methods=['POST'])
def api_fix():
    """Non-blocking: start serve.py in background, return immediately."""
    import threading
    def _run():
        python = sys.executable
        serve_py = os.path.join(SCRIPT_DIR, "serve.py")
        ok = subprocess.run([python, serve_py], cwd=SCRIPT_DIR, capture_output=True, timeout=900).returncode == 0
        git_pull()
        subprocess.run(["git", "add", "history", "data.json"], cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", "local: manual fix", "--no-gpg-sign"],
                       cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=SCRIPT_DIR,
                       capture_output=True, timeout=180)
        subprocess.run(["git", "push"], cwd=SCRIPT_DIR, capture_output=True, timeout=180)
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "ok", "message": "后台修复中，约3-5分钟"})

@app.route('/api/missing', methods=['GET'])
def api_missing():
    """Return list of cities with missing data."""
    return jsonify(find_missing())

@app.route('/api/history', methods=['GET'])
def api_history():
    """List available historical data files."""
    history_dir = os.path.join(SCRIPT_DIR, "history")
    if not os.path.exists(history_dir):
        return jsonify({"dates": []})
    files = sorted([f.replace('.json','') for f in os.listdir(history_dir) if f.endswith('.json')], reverse=True)
    return jsonify({"dates": files})

@app.route('/api/data/<date_str>')
def api_data_date(date_str):
    """Return historical data for a specific date."""
    hist_file = os.path.join(SCRIPT_DIR, "history", f"{date_str}.json")
    if not os.path.exists(hist_file):
        return jsonify({"status": "not_found"})
    with open(hist_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify({"status": "ready", "data": data, "updated_at": date_str})

@app.route('/api/accuracy', methods=['GET'])
def api_accuracy():
    """预测准确度统计（accuracy.py 生成）；?period=morning 早上预测"""
    period = request.args.get('period')
    fname = "accuracy_morning.json" if period == "morning" else "accuracy.json"
    acc_file = os.path.join(SCRIPT_DIR, fname)
    if not os.path.exists(acc_file):
        return jsonify({"status": "not_found"})
    with open(acc_file, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))

@app.route('/api/daydetail')
def api_daydetail():
    """返回指定城市+日期的完整预测数据和实际数据"""
    city = request.args.get('city', '')
    date = request.args.get('date', '')
    if not city or not date:
        return jsonify({"status": "error", "message": "missing city/date"})

    result = {"city": city, "date": date, "highest": None, "lowest": None, "actual": {}}

    hist_dir = os.path.join(SCRIPT_DIR, "history")
    if os.path.exists(hist_dir):
        for fn in sorted(os.listdir(hist_dir), reverse=True):
            if not fn.endswith('.json') or fn == 'actuals.json' or fn == 'actuals_backup.json':
                continue
            if not fn.startswith(date[:7]):
                continue
            try:
                fp = os.path.join(hist_dir, fn)
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for row in data.get("rows", []):
                    if row.get("city") == city and row.get("date") == date:
                        result["highest"] = row.get("highest")
                        result["lowest"] = row.get("lowest")
                        break
                if result["highest"] or result["lowest"]:
                    break
            except Exception:
                continue

    actuals_file = os.path.join(hist_dir, "actuals.json")
    if os.path.exists(actuals_file):
        try:
            with open(actuals_file, 'r', encoding='utf-8') as f:
                actuals = json.load(f)
            city_slug = city.lower().replace(" ", "-")
            month_names = {"1":"january","2":"february","3":"march","4":"april","5":"may","6":"june",
                           "7":"july","8":"august","9":"september","10":"october","11":"november","12":"december"}
            parts = date.split("-")
            day = str(int(parts[2]))
            month_name = month_names.get(parts[1], "")
            year = parts[0]
            for direction in ("highest", "lowest"):
                slug = f"{direction}-temperature-in-{city_slug}-on-{month_name}-{day}-{year}"
                if slug in actuals:
                    result["actual"][direction] = actuals[slug]
        except Exception:
            pass

    return jsonify(result)

@app.route('/api/hourly')
def api_hourly():
    """返回指定城市+日期的逐小时温度数据"""
    from city_coords import CITY_COORDS
    city = request.args.get('city', '')
    date = request.args.get('date', '')
    if not city or not date:
        return jsonify({"hourly": []})

    hist_dir = os.path.join(SCRIPT_DIR, "history")
    if os.path.exists(hist_dir):
        for fn in sorted(os.listdir(hist_dir), reverse=True):
            if not fn.endswith('.json') or 'actuals' in fn: continue
            if not fn.startswith(date[:7]): continue
            try:
                fp = os.path.join(hist_dir, fn)
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for row in data.get("rows", []):
                    if row.get("city") == city and row.get("date") == date:
                        for key in ("highest", "lowest"):
                            obj = row.get(key)
                            if not obj: continue
                            hourly = obj.get("hourly", [])
                            if hourly:
                                return jsonify({"hourly": hourly, "source": "GFS"})
                        break
            except Exception:
                continue

    try:
        lat, lon = CITY_COORDS.get(city, (0, 0))
        with httpx.Client(http1=True, http2=False, verify=False, timeout=15,
                          proxy=os.getenv("PROXY_URL", "http://127.0.0.1:7897") or None) as client:
            r = client.get("https://archive-api.open-meteo.com/v1/archive",
                params={"latitude": lat, "longitude": lon,
                        "start_date": date, "end_date": date,
                        "hourly": "temperature_2m"},
                headers=HEADERS)
            data = r.json()
            temps = data.get("hourly", {}).get("temperature_2m", [])
            times = data.get("hourly", {}).get("time", [])
            result = []
            for i, t in enumerate(times):
                if i < len(temps) and temps[i] is not None:
                    hour = int(t.split("T")[1].split(":")[0])
                    result.append({"hour": hour, "temp": temps[i]})
            return jsonify({"hourly": result, "source": "Open-Meteo"})
    except Exception:
        return jsonify({"hourly": []})

def git_pull():
    """从 GitHub 仓库同步最新数据（云端 Actions 每 30 分钟抓取）"""
    try:
        r = subprocess.run(["git", "pull", "--rebase"], cwd=SCRIPT_DIR, capture_output=True,
                           text=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, str(e)

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """本地抓取 meteoblue 数据并更新"""
    if _bg_status["running"]:
        return jsonify({"status": "busy", "error": "正在抓取中，请稍后"})
    
    python = sys.executable
    serve_py = os.path.join(SCRIPT_DIR, "serve.py")
    try:
        result = subprocess.run([python, serve_py], cwd=SCRIPT_DIR,
                                capture_output=True, text=True, timeout=900,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        # Reload data after fetch
        with open(_cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({"status": "ok", "data": data, "sync": "本地抓取完成"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

import threading

_bg_status = {"running": False, "last_run": None, "next_run": None, "log": ""}

def _bg_fetch():
    _bg_status["running"] = True
    _bg_status["log"] = "抓取中..."
    try:
        python = sys.executable
        serve_py = os.path.join(SCRIPT_DIR, "serve.py")
        result = subprocess.run([python, serve_py], cwd=SCRIPT_DIR,
                                capture_output=True, text=True, timeout=900,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        _bg_status["log"] = result.stdout[-500:] if result.stdout else (result.stderr[-500:] if result.stderr else "done")
        subprocess.run(["git", "add", "history", "data.json"], cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", "auto: local fetch", "--no-gpg-sign"],
                       cwd=SCRIPT_DIR, capture_output=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=SCRIPT_DIR, capture_output=True, timeout=180)
        subprocess.run(["git", "push"], cwd=SCRIPT_DIR, capture_output=True, timeout=180)
    except Exception as e:
        _bg_status["log"] = f"error: {e}"
    finally:
        _bg_status["running"] = False
        _bg_status["last_run"] = datetime.now().strftime("%H:%M:%S")

def _bg_loop(interval=1800):
    while True:
        _bg_status["next_run"] = datetime.now().timestamp() + interval
        time.sleep(interval)
        if not _bg_status["running"]:
            _bg_fetch()

@app.route('/api/auto-status')
def api_auto_status():
    return jsonify(_bg_status)

@app.route('/api/auto-start', methods=['POST'])
def api_auto_start():
    if not any(t.name == 'bg_fetch' for t in threading.enumerate()):
        t = threading.Thread(target=_bg_loop, kwargs={"interval": 1800}, daemon=True, name='bg_fetch')
        t.start()
        _bg_status["next_run"] = datetime.now().timestamp() + 1800
    return jsonify({"status": "ok"})

@app.route('/api/auto-now', methods=['POST'])
def api_auto_now():
    if not _bg_status["running"]:
        threading.Thread(target=_bg_fetch, daemon=True).start()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    print("=" * 50)
    print("Weather Dashboard Server  |  http://127.0.0.1:5002")
    print("Local auto-fetch: every 30 min + git push")
    print("=" * 50)
    t = threading.Thread(target=_bg_loop, kwargs={"interval": 1800}, daemon=True, name='bg_fetch')
    t.start()
    _bg_status["next_run"] = datetime.now().timestamp() + 1800
    app.run(host='0.0.0.0', port=5002, debug=False)
