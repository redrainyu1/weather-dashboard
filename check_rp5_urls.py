import json
from rp5_scraper import RP5_URLS

# From the last check_data output, cities that might miss RP5
# Let me just show which 49 cities are in/out of RP5_URLS

# All cities from AIRPORT_CODES in serve.py
all_cities = [
    "Amsterdam", "Ankara", "Atlanta", "Austin", "Beijing", "Buenos Aires",
    "Busan", "Cape Town", "Chengdu", "Chicago", "Chongqing", "Dallas",
    "Denver", "Guangzhou", "Helsinki", "Hong Kong", "Houston", "Istanbul",
    "Jeddah", "Karachi", "Kuala Lumpur", "London", "Los Angeles", "Lucknow",
    "Madrid", "Manila", "Mexico City", "Miami", "Milan", "Moscow",
    "Munich", "Nyc", "Panama City", "Paris", "Qingdao", "San Francisco",
    "Sao Paulo", "Seattle", "Seoul", "Shanghai", "Shenzhen", "Singapore",
    "Taipei", "Tel Aviv", "Tokyo", "Toronto", "Warsaw", "Wellington", "Wuhan",
]

missing_url = [c for c in all_cities if c not in RP5_URLS]
print(f"Missing RP5 URL ({len(missing_url)}):")
for c in missing_url:
    print(f"  {c}")
