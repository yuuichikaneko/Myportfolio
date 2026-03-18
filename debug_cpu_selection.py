import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from scraper.models import PCPart
from scraper.views import _is_cpu_x3d, _extract_cpu_core_threads, _get_spec

parts = PCPart.objects.filter(name__icontains='9950')
print("=== X3D フィルタ動作確認 ===")
for p in parts:
    print(f"Name: {p.name}")
    print(f"  Price: {p.price}")
    print(f"  Is X3D: {_is_cpu_x3d(p)}")
    print(f"  Core/Thread: {_extract_cpu_core_threads(p)}")
    print()

# ソート動作確認
print("=== ソート結果 ===")
candidates = list(parts)
sorted_candidates = sorted(
    candidates,
    key=lambda p: (
        -_extract_cpu_core_threads(p),
        -(_get_spec(p, 'core_count', 0) or 0),
        _is_cpu_x3d(p),
        p.price,
    ),
)
for i, p in enumerate(sorted_candidates):
    print(f"{i+1}. {p.name} - ¥{p.price}")
