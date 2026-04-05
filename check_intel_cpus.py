import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from scraper.models import PCPart

# 全CPU確認
cpus = PCPart.objects.filter(part_type='cpu').order_by('price')
print(f'=== Total CPUs in DB: {cpus.count()} ===\n')

# Intel CPUを特定
intel_cpus = [c for c in cpus if 'core i' in c.name.lower() or 'core ultra' in c.name.lower()]
amd_cpus = [c for c in cpus if 'ryzen' in c.name.lower()]
print(f'Intel CPUs: {len(intel_cpus)}')
print(f'AMD Ryzen CPUs: {len(amd_cpus)}\n')

# 高価格順の上位20 Intel CPU
print('=== Top 20 Intel CPUs (by price, highest first) ===')
for cpu in sorted(intel_cpus, key=lambda x: x.price, reverse=True)[:20]:
    print(f'{cpu.name:<40} ¥{cpu.price:>8}')

print('\n=== Top 10 AMD Ryzen CPUs (by price, highest first) ===')
for cpu in sorted(amd_cpus, key=lambda x: x.price, reverse=True)[:10]:
    print(f'{cpu.name:<40} ¥{cpu.price:>8}')
