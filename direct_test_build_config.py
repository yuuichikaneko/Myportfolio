#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接テスト: build_configuration_response（API path を追跡）
"""

import os
import sys
import django
import importlib

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'django'))
django.setup()

# Force reload views to get latest code
import scraper.views as views_module
importlib.reload(views_module)

# Direct test
result, error = views_module.build_configuration_response(
    budget=574980,
    usage='gaming',
    cooler_type='any',
    radiator_size='any',
    cooling_profile='balanced',
    case_size='any',
    case_fan_policy='auto',
    cpu_vendor='any',
    build_priority='cost',
    storage_preference='ssd',
    storage2_part_id=None,
    storage3_part_id=None,
    os_edition='home',
    custom_budget_weights=None,
    min_storage_capacity_gb=None,
    max_motherboard_chipset=None,
    enforce_gaming_x3d=False,
    persist=False,
)

if error:
    print(f"ERROR: {error}")
else:
    print("=== build_configuration_response Result ===")
    parts_dict = {}
    for part in result.get('parts', []):
        parts_dict[part.get('category')] = part
    
    cpu = parts_dict.get('cpu', {})
    print(f"CPU: {cpu.get('name')}")
    print(f"  Price: {cpu.get('price'):,}")
    print(f"  Is 9850X3D: {'9850x3d' in cpu.get('name', '').lower()}")
