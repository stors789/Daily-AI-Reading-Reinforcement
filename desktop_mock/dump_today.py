import os
from real_momo_provider import RealMoMoDeckProvider

token = os.environ.get("MOMO_TOKEN") or os.environ.get("Maimemo_key")
if not token:
    print("No token provided. Please run with MOMO_TOKEN=... python3 dump_today.py")
    exit(1)

provider = RealMoMoDeckProvider(token=token)
try:
    raw = provider.get_today_items_raw()
    items = raw.get("data", {}).get("today_items", [])
    
    first_resps = set()
    last_resps = set()
    for item in items:
        f = item.get("first_response")
        l = item.get("last_response")
        if f is not None: first_resps.add(f)
        if l is not None: last_resps.add(l)
        
    print(f"Total today items: {len(items)}")
    print(f"Unique first_response values: {first_resps}")
    print(f"Unique last_response values: {last_resps}")
    
except Exception as e:
    print("Error:", e)
