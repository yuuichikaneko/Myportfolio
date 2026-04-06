#!/usr/bin/env python
import os, sys, django
from pathlib import Path
django_path = Path(__file__).parent / 'django'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, str(django_path))
django.setup()
from scraper.models import PCPart

total = PCPart.objects.filter(is_active=True).count()
print(f"全パーツ数: {total}件\n")

statuses = PCPart.objects.filter(is_active=True).values_list('stock_status', flat=True).distinct()
print("存在する在庫状態:")
for s in sorted(statuses):
    c = PCPart.objects.filter(is_active=True, stock_status=s).count()
    print(f"  {s}: {c}件")
