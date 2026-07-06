import os
from real_momo_provider import RealMoMoDeckProvider

token = os.environ.get("MOMO_TOKEN") or os.environ.get("Maimemo_key")
if not token:
    print("No token provided. Please run with MOMO_TOKEN=... python3 desktop_mock/probe_limits.py")
    exit(1)

provider = RealMoMoDeckProvider(token=token)

try:
    print("Testing get_today_items with no limit...")
    raw = provider.get_today_items_raw()
    items = raw.get("data", {}).get("today_items", [])
    print(f"Count: {len(items)}")

    print("\nTesting get_today_items with limit=100...")
    raw = provider.get_today_items_raw(limit=100)
    items = raw.get("data", {}).get("today_items", [])
    print(f"Count: {len(items)}")

    print("\nTesting get_today_items with limit=500...")
    raw = provider.get_today_items_raw(limit=500)
    items = raw.get("data", {}).get("today_items", [])
    print(f"Count: {len(items)}")
except Exception as e:
    print("Error on get_today_items:", e)

try:
    print("\nTesting query_study_records_raw...")
    raw = provider.query_study_records_raw(limit=5000)
    records = raw.get("data", {}).get("records", [])
    print(f"study_records count: {len(records)}")
    
    responses = set()
    for r in records:
        f = r.get("first_response")
        if f: responses.add(f)
    print("first_responses in study_records:", responses)
except Exception as e:
    print("Error on query_study_records_raw:", e)
