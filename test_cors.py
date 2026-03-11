import requests
import json

# Test CORS with browser simulation
headers = {
    'Origin': 'http://localhost:8080',
    'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'Content-Type'
}

print('=== Testing CORS preflight (OPTIONS) ===')
response = requests.options('http://localhost:8001/generate-config', headers=headers)
print(f'Status: {response.status_code}')
print(f'CORS Headers:')
for key in ['Access-Control-Allow-Origin', 'Access-Control-Allow-Methods', 'Access-Control-Allow-Headers']:
    print(f'  {key}: {response.headers.get(key, "NOT SET")}')

print('\n=== Testing POST request ===')
response = requests.post('http://localhost:8001/generate-config', json={'budget': 150000, 'usage': 'gaming'})
print(f'Status: {response.status_code}')
result = response.json()
print(f'Response keys: {list(result.keys())}')
print(f'Total price: {result["total_price"]} JPY')
print(f'Parts count: {len(result["parts"])}')
