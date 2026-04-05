#!/usr/bin/env python
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, 'django')
django.setup()

from scraper.models import PCPart
from scraper.views import (
    _pick_part_by_target, BUDGET_TIER_THRESHOLDS,
    _is_gaming_gpu_within_priority_cap, _infer_gaming_gpu_perf_score
)

budget = 169980
usage = 'gaming'
build_priority = 'cost'

print(f"=== Debug _pick_part_by_target for GPU ===")
print(f"Budget: JPY {budget:,}")
print(f"BUDGET_TIER_THRESHOLDS['low']: JPY {BUDGET_TIER_THRESHOLDS['low']:,}")
print(f"budget < BUDGET_TIER_THRESHOLDS['low']: {budget < BUDGET_TIER_THRESHOLDS['low']}")

# Call _pick_part_by_target directly
options = {'usage': usage, 'build_priority': build_priority}
picked_gpu = _pick_part_by_target('gpu', budget, usage, options=options)

print(f"\nPicked GPU:")
print(f"  Name: {picked_gpu.name if picked_gpu else 'None'}")
print(f"  Price: JPY {picked_gpu.price if picked_gpu else 'N/A'}")

# Check candidates pool
all_gpus = PCPart.objects.filter(part_type='gpu').order_by('price')
suitable_gpus = [p for p in all_gpus if p not in (None,)]  # placeholder filter

rtx_3050_in_db = [p for p in all_gpus if 'rtx 3050' in f'{p.name} {p.url}'.lower()]
print(f"\nRTX 3050 in database: {len(rtx_3050_in_db)}")
for p in rtx_3050_in_db:
    priority_cap = _is_gaming_gpu_within_priority_cap(p, build_priority)
    price_cap = max(34980, int(budget * 0.21))
    print(f'  {p.name[:35]}: JPY {p.price}, priority_cap={priority_cap}, <= {price_cap}={p.price <= price_cap}')
