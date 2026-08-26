"""从 Open-Meteo 获取当日峰值时间预测"""
import asyncio
import httpx
from datetime import datetime
from city_coords import CITY_COORDS


async def get_forecast_peak(client, city, date=None):
    """获取指定城市当天的预测峰值时间（最高温出现的当地小时）

    Args:
        client: httpx.AsyncClient
        city: 城市名（如 "Beijing", "Nyc"）
        date: 日期字符串 YYYY-MM-DD（默认今天）

    Returns:
        dict: {
            "city": 城市名,
            "date": 日期,
            "peak_hour": 预计峰值当地小时（0-23）,
            "peak_time": 预计峰值当地时刻（HH:MM）,
            "peak_temp": 预计最高温,
            "best_bet_hour": 最佳下注时间（峰值前1.5小时）,
            "hourly": 逐小时预测（可选）
        }
        失败返回 None
    """
    coords = CITY_COORDS.get(city)
    if not coords:
        return None

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={coords[0]}&longitude={coords[1]}"
        f"&hourly=temperature_2m"
        f"&start_date={date}&end_date={date}"
        f"&timezone=auto"
    )

    try:
        r = await client.get(url, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        times = data.get("hourly", {}).get("time") or []
        temps = data.get("hourly", {}).get("temperature_2m") or []

        if not times or not temps:
            return None

        # 找最高温及其时间
        max_temp = max(temps)
        max_idx = temps.index(max_temp)

        # 解析时间（格式：2026-08-23T14:00）
        peak_time_str = times[max_idx]
        peak_hour = int(peak_time_str.split("T")[1].split(":")[0])

        # 计算最佳下注时间（峰值前1.5小时）
        best_bet_hour = peak_hour - 1.5
        if best_bet_hour < 0:
            best_bet_hour += 24

        return {
            "city": city,
            "date": date,
            "peak_hour": peak_hour,
            "peak_time": f"{peak_hour:02d}:00",
            "peak_temp": max_temp,
            "best_bet_hour": best_bet_hour,
            "best_bet_time": f"{int(best_bet_hour):02d}:{30 if best_bet_hour % 1 else '00'}",
        }

    except Exception as e:
        print(f"获取 {city} 预测失败: {e}")
        return None


async def get_all_cities_forecast(date=None):
    """批量获取所有城市的峰值预测"""
    async with httpx.AsyncClient() as client:
        tasks = []
        for city in CITY_COORDS.keys():
            tasks.append(get_forecast_peak(client, city, date))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid = []
        for r in results:
            if isinstance(r, dict):
                valid.append(r)

        return valid


async def main():
    """演示：获取几个城市的预测"""
    cities = ["Beijing", "Nyc", "London", "Tokyo", "Sydney", "Paris"]

    async with httpx.AsyncClient() as client:
        print(f"{'城市':<15} {'预测峰值':<12} {'最高温':<10} {'最佳下注时间'}")
        print("-" * 60)

        for city in cities:
            result = await get_forecast_peak(client, city)
            if result:
                print(
                    f"{result['city']:<15} "
                    f"{result['peak_time']:<12} "
                    f"{result['peak_temp']:<10} "
                    f"{result['best_bet_time']}"
                )
            else:
                print(f"{city:<15} 获取失败")


if __name__ == "__main__":
    asyncio.run(main())
