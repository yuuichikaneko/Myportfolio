import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from scraper.models import PCPart
from scraper.views import _is_cpu_x3d, _get_spec, _prefer_creator_cpu_by_core_threads

# Creator 用途での予算内 CPU を確認
creator_budget_cpu = int(334980 * 0.20)  # 20% allocation
print(f"=== Creator CPU Budget: ¥{creator_budget_cpu} ===\n")

# 予算内の全 CPU
all_cpus = PCPart.objects.filter(
    part_type='cpu',
    price__lte=creator_budget_cpu * 1.15
).order_by('price')

print(f"全 CPU 候補 ({all_cpus.count()}件):")
for cpu in all_cpus:
    cores = _get_spec(cpu, 'core_count', 0) or 0
    x3d = _is_cpu_x3d(cpu)
    print(f"  {cpu.name}: ¥{cpu.price}, {cores}cores, X3D={x3d}")

print("\n=== Filtering for creator ===")
# X3D 除外
non_x3d = [p for p in all_cpus if not _is_cpu_x3d(p)]
print(f"非 X3D CPU: {len(non_x3d)}件")

# 8コア以上
qualified = [p for p in non_x3d if (_get_spec(p, 'core_count', 0) or 0) >= 8]
print(f"8コア以上: {len(qualified)}件")
if qualified:
    for cpu in qualified:
        print(f"  {cpu.name}: ¥{cpu.price}")

# _prefer_creator_cpu_by_core_threads の結果
print("\n=== _prefer_creator_cpu_by_core_threads result ===")
selected = _prefer_creator_cpu_by_core_threads(list(all_cpus))
if selected:
    print(f"Selected: {selected.name} - ¥{selected.price}")
    print(f"  X3D: {_is_cpu_x3d(selected)}")
    print(f"  Cores: {_get_spec(selected, 'core_count', 0)}")
else:
    print("No CPU selected")
