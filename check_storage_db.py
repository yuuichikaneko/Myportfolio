#!/usr/bin/env python
import sys
sys.path.insert(0, 'f:\\Python\\Myportfolio\\django')
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from scraper.models import PCPart

# Check all storage items
storages = PCPart.objects.filter(part_type='storage')

print("=== Total Storage Count ===")
print(f"Total: {storages.count()}")

print("\n=== SSD Count ===")
ssds = storages.filter(media_type='ssd')
print(f"SSD (media_type='ssd'): {ssds.count()}")

print("\n=== HDD Count ===")
hdds = storages.filter(media_type='hdd')
print(f"HDD (media_type='hdd'): {hdds.count()}")

print("\n=== First 5 SSD by capacity ===")
for ssd in ssds.order_by('capacity_gb')[:5]:
    print(f"  {ssd.name[:60]:<60} | {ssd.capacity_gb}GB | {ssd.interface or 'N/A'}")

print("\n=== First 5 HDD by capacity ===")
for hdd in hdds.order_by('capacity_gb')[:5]:
    print(f"  {hdd.name[:60]:<60} | {hdd.capacity_gb}GB | {hdd.interface or 'N/A'}")

print("\n=== 2TB Storage Options ===")
storages_2tb = storages.filter(capacity_gb=2048)
print(f"2TB storage count: {storages_2tb.count()}")
for s in storages_2tb:
    print(f"  {s.name[:60]:<60} | Media: {s.media_type or 'unknown'} | Interface: {s.interface or 'unknown'}")
