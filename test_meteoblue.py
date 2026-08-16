"""Check meteoblue API for min temperature."""
import httpx, json, os

APIKEY = "ZNbqYnaveXFJjt37"
PROXY = os.getenv("PROXY_URL", "http://127.0.0.1:7897")

c = httpx.Client(http1=True, http2=False, verify=False, timeout=15, proxy=PROXY)

url = f"https://my.meteoblue.com/packages/basic-1h_basic-day?apikey={APIKEY}&lat=52.37&lon=4.89&asl=0&format=json"
r = c.get(url)
data = r.json()

# Show all keys in data_day
day = data.get("data_day", {})
print("data_day keys:", list(day.keys()))
for k, v in day.items():
    print(f"  {k}: {v[:4] if isinstance(v, list) else v}")
