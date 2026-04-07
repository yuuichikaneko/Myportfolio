#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DEBUG: gaming+cost CPU selection tracking
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'django'))
django.setup()

from scraper.models import PCPart
from scraper.views import _pick_amd_gaming_cpu, _should_exclude_cpu_for_gaming_cost, _is_part_suitable, _is_gaming_excluded_creator_cpu

# Simulating _pick_part_by_target candidate generation
all_candidates = [p for p in PCPart.objects.filter(part_type='cpu').order_by('price') if _is_part_suitable('cpu', p)]

# Filter out creator excluded CPUs (like _pick_amd_gaming_cpu does first)
candidates = [p for p in all_candidates if not _is_gaming_excluded_creator_cpu(p)]

print(f"=== CPU Selection Debug for gaming+cost ===")
print(f"Total suitable CPUs: {len(all_candidates)}")
print(f"After creator exclusion: {len(candidates)}")

# gaming + cost filtering (like we added)
non_flagship_candidates = [
    p for p in candidates
    if not _should_exclude_cpu_for_gaming_cost(p)
]

print(f"Non-flagship candidates: {len(non_flagship_candidates)}")
if non_flagship_candidates:
    print("Top 5 non-flagship CPU options:")
    for cpu in sorted(non_flagship_candidates, key=lambda x: x.price)[:5]:
        price_str = f"{cpu.price:,}"
        print(f"  {cpu.name:<50} Price={price_str:>8}")

print("\nTesting _pick_amd_gaming_cpu directly:")
result = _pick_amd_gaming_cpu(candidates, 'cost', require_x3d=False)
print(f"Result: {result.name} (Price={result.price:,})")

print("\nTesting _pick_amd_gaming_cpu with non-flagship candidates:")
result2 = _pick_amd_gaming_cpu(non_flagship_candidates, 'cost', require_x3d=False)
if result2:
    print(f"Result: {result2.name} (Price={result2.price:,})")
else:
    print("No CPU selected from non-flagship candidates!")
