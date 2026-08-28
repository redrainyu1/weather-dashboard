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
    """从 GitHub 仓库同步最新抓取数据"""
    ok, msg = git_pull()
    try:
        with open(_cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tail = [ln for ln in msg.strip().splitlines() if ln.strip()][-1:] or [""]
        return jsonify({"status": "ok", "data": data, "sync": tail[0]})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == '__main__':
    print("=" * 50)
    print("Weather Dashboard Server  |  http://127.0.0.1:5002")
    print("Manual mode: 刷新数据 = git pull 同步云端, 修复缺失 = 本地抓取")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5002, debug=False)
