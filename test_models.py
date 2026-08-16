import httpx
import json

PROXY = 'http://127.0.0.1:7897'
c = httpx.Client(http1=True, http2=False, verify=False, timeout=15, proxy=PROXY)

# Test: multiple weather models in one call
lat, lon = 52.37, 4.89  # Amsterdam
url = (
    f'https://api.open-meteo.com/v1/forecast'
    f'?latitude={lat}&longitude={lon}'
    f'&daily=temperature_2m_max,temperature_2m_min'
    f'&models=gfs_seamless,ecmwf_ifs04,icon_seamless'
    f'&forecast_days=4&timezone=auto'
)
r = c.get(url)
print("Status:", r.status_code)
data = r.json()
# Show all keys to see model nesting
print("\nTop keys:", list(data.keys()))

# Check if models are nested or flat
for key in data:
    if isinstance(data[key], dict) and 'daily' in data[key]:
        model_data = data[key]
        daily = model_data['daily']
        times = daily['time']
        tmax = daily['temperature_2m_max']
        tmin = daily['temperature_2m_min']
        print(f"\n--- Model: {key} ---")
        for t, mx, mn in zip(times[:3], tmax[:3], tmin[:3]):
            print(f"  {t}: max={mx}C, min={mn}C")
