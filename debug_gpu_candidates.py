#!/usr/bin/env python
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent / 'django'))

django.setup()

from scraper.models import PCPart
from scraper.views import _is_part_suitable

# 初期 candidates フィルタ
all_gpus = PCPart.objects.filter(part_type='gpu')
suitable_gpus = [p for p in all_gpus if _is_part_suitable('gpu', p)]

print(f'Total GPUs in DB: {len(list(all_gpus))}')
print(f'Suitable GPUs (via _is_part_suitable): {len(suitable_gpus)}')

rtx_3050_suitable = [p for p in suitable_gpus if 'rtx 3050' in f'{p.name} {p.url}'.lower()]
rx6400_suitable = [p for p in suitable_gpus if 'rx 6400' in f'{p.name} {p.url}'.lower()]

print(f'\nRTX 3050 suitable: {len(rtx_3050_suitable)}')
for p in rtx_3050_suitable:
    print(f'  {p.name[:40]}: JPY {p.price}, suitable={_is_part_suitable("gpu", p)}')

print(f'\nRX 6400 suitable: {len(rx6400_suitable)}')
for p in rx6400_suitable:
    print(f'  {p.name[:40]}: JPY {p.price}, suitable={_is_part_suitable("gpu", p)}')
