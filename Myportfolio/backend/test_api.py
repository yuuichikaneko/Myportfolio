import requests
import json

BASE_URL = "http://127.0.0.1:8000"

# Test healthcheck
print("=== Healthcheck ===")
response = requests.get(f"{BASE_URL}/")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

# Test generate config - gaming PC
print("\n=== Generate Config (Gaming, 150,000 JPY) ===")
payload = {"budget": 150000, "usage": "gaming"}
response = requests.post(f"{BASE_URL}/generate-config", json=payload)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Total Price: {result['total_price']} JPY")
    print(f"Estimated Power: {result['estimated_power_w']}W")
    print(f"Parts ({len(result['parts'])} items):")
    for part in result["parts"]:
        print(f"  - {part['category']}: {part['name']} ({part['price']} JPY)")
else:
    print(f"Error: {response.json()}")

# Test generate config - video editing
print("\n=== Generate Config (Video Editing, 200,000 JPY) ===")
payload = {"budget": 200000, "usage": "video_editing"}
response = requests.post(f"{BASE_URL}/generate-config", json=payload)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Total Price: {result['total_price']} JPY")
    print(f"Parts ({len(result['parts'])} items):")
    for part in result["parts"]:
        print(f"  - {part['category']}: {part['name']} ({part['price']} JPY)")
else:
    print(f"Error: {response.json()}")

# Test generate config - general purpose
print("\n=== Generate Config (General, 180,000 JPY) ===")
payload = {"budget": 180000, "usage": "general"}
response = requests.post(f"{BASE_URL}/generate-config", json=payload)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    result = response.json()
    print(f"Total Price: {result['total_price']} JPY")
    print(f"Parts ({len(result['parts'])} items):")
    for part in result["parts"]:
        print(f"  - {part['category']}: {part['name']} ({part['price']} JPY)")
else:
    print(f"Error: {response.json()}")
