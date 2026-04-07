#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
gaming+spec vs gaming+cost config comparison（to visualize user request）
"""

import requests
import json

api_url = "http://localhost:8001/api/generate-config/"

configs = {
    "gaming_cost": {
        "usage": "gaming",
        "budget": 574980,
        "build_priority": "cost"
    },
    "gaming_spec": {
        "usage": "gaming",
        "budget": 574980,
        "build_priority": "spec"
    }
}

results = {}
for config_name, payload in configs.items():
    try:
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        parts_dict = {}
        for part in result.get('parts', []):
            parts_dict[part.get('category')] = part
        
        results[config_name] = {
            'total': result.get('total_price', 0),
            'cpu': parts_dict.get('cpu', {}).get('name', 'N/A'),
            'cpu_price': parts_dict.get('cpu', {}).get('price', 0),
            'mb': parts_dict.get('motherboard', {}).get('name', 'N/A'),
            'mb_price': parts_dict.get('motherboard', {}).get('price', 0),
            'mem': parts_dict.get('memory', {}).get('name', 'N/A'),
            'mem_price': parts_dict.get('memory', {}).get('price', 0),
        }
    except Exception as e:
        print(f"Error for {config_name}: {e}")

print("\n=== Configuration Comparison ===")
print(f"Budget: ¥{configs['gaming_cost']['budget']:,}\n")

for config_name in ['gaming_cost', 'gaming_spec']:
    if config_name not in results:
        continue
    r = results[config_name]
    print(f"[{config_name.upper()}] Total: ¥{r['total']:,}")
    print(f"  CPU: {r['cpu'][:40]:40} ¥{r['cpu_price']:>8,}")
    print(f"  MB:  {r['mb'][:40]:40} ¥{r['mb_price']:>8,}")
    print(f"  Mem: {r['mem'][:40]:40} ¥{r['mem_price']:>8,}")
    print()

# Calculate difference
if 'gaming_cost' in results and 'gaming_spec' in results:
    cost_config = results['gaming_cost']
    spec_config = results['gaming_spec']
    
    cost_cpu_mb_mem = cost_config['cpu_price'] + cost_config['mb_price'] + cost_config['mem_price']
    spec_cpu_mb_mem = spec_config['cpu_price'] + spec_config['mb_price'] + spec_config['mem_price']
    
    print("=== CPU+MB+Memory Total ===")
    print(f"Gaming+Cost: ¥{cost_cpu_mb_mem:,}")
    print(f"Gaming+Spec: ¥{spec_cpu_mb_mem:,}")
    print(f"Difference: ¥{spec_cpu_mb_mem - cost_cpu_mb_mem:,} (user requested ¥70-80k reduction)")
