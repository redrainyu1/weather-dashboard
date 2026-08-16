import httpx
PROXY = 'http://127.0.0.1:7897'
c = httpx.Client(http1=True, http2=False, verify=False, timeout=15, proxy=PROXY)

# Test geocoding
r = c.get('https://geocoding-api.open-meteo.com/v1/search?name=Amsterdam&count=1')
print('Geo status:', r.status_code)
d = r.json()
r2 = d['results'][0]
print(f"Amsterdam: lat={r2['latitude']}, lon={r2['longitude']}")

# Test forecast
lat, lon = r2['latitude'], r2['longitude']
r3 = c.get(f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min&forecast_days=5&timezone=auto')
print('Forecast:', r3.json())
