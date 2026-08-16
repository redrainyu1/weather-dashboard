import asyncio, sys
sys.path.insert(0, r'D:\Opencode Code\weather_dashboard')
from serve import fetch_meteoblue

async def test():
    for city in ['Beijing', 'Amsterdam', 'Tokyo', 'London', 'Atlanta']:
        print(f'--- {city} ---')
        r = await fetch_meteoblue(None, city)
        if r:
            for dt, data in sorted(r.items())[:3]:
                print(f'  {dt}: max={data["max"]} min={data["min"]}')
        else:
            print('  FAILED')
        print()

asyncio.run(test())
