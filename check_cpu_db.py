#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DB CPU データ確認
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'django'))
django.setup()

from scraper.models import PCPart
from scraper.views import _should_exclude_cpu_for_gaming_cost, _is_gaming_cpu_x3d_preferred

# All gaming AMD CPUs
cpus = PCPart.objects.filter(part_type='cpu', name__icontains='Ryzen').order_by('price')
print(f"=== Total AMD Ryzen CPUs: {cpus.count()} ===")
for cpu in cpus[:20]:
    is_flagship = _should_exclude_cpu_for_gaming_cost(cpu)
    is_x3d = _is_gaming_cpu_x3d_preferred(cpu)
    price_str = f"{cpu.price:,}"
    print(f"{cpu.name[:50]:50} Price={price_str:>8} X3D={is_x3d} Flagship={is_flagship}")

print("\n=== X3D CPUs ===")
x3d_cpus = cpus.filter(name__icontains='X3D')
for cpu in x3d_cpus:
    is_flagship = _should_exclude_cpu_for_gaming_cost(cpu)
    price_str = f"{cpu.price:,}"
    print(f"{cpu.name[:50]:50} Price={price_str:>8} Flagship={is_flagship}")
