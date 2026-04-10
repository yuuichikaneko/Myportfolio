#!/usr/bin/env python
"""Debug API response format"""
import requests
import json

url = 'http://127.0.0.1:8001/api/generate-config/'
payload = {'budget': 60478, 'usage': 'general'}

response = requests.post(url, json=payload, timeout=30)
print(f"Status: {response.status_code}")
print(f"Response type: {type(response.json())}")
print("Keys/Structure:")
data = response.json()
if isinstance(data, dict):
    print(f"  Keys: {list(data.keys())}")
    if 'parts' in data:
        print(f"  parts type: {type(data['parts'])}")
        if isinstance(data['parts'], dict):
            print(f"  parts keys: {list(data['parts'].keys())}")
elif isinstance(data, list):
    print(f"  List with {len(data)} items")
    if len(data) > 0:
        print(f"  First item type: {type(data[0])}")

# Show pretty JSON
print("\nFull response (first 1000 chars):")
print(json.dumps(response.json(), indent=2, ensure_ascii=False)[:1000])
