Set-Location "$PSScriptRoot/django"

$pythonExe = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "py"
}

@'
import requests
from collections import Counter
import scraper.dospara_scraper as ds
from scraper.models import PCPart

url = "https://www.dospara.co.jp/BR116?srule=04&includeNotInventory=false"
config = ds.get_dospara_scraper_config()
session = requests.Session()

# 1. カテゴリページから IC コードを収集
resp = session.get(url, headers=config["headers"], timeout=30)
resp.raise_for_status()
codes = ds._collect_ic_codes_from_category_pages(
    html=resp.text,
    category_url=url,
    headers=config["headers"],
    timeout=20,
    session=session,
    max_codes=2000,
)
print(f"  IC codes collected: {len(codes)}")

# 2. 製品 API から詳細取得
products_map = ds._fetch_products_by_codes(
    codes=codes,
    api_url=config["products_api_url"],
    headers=config["headers"],
    timeout=20,
    batch_size=config["batch_size"],
    session=session,
)
print(f"  Products fetched: {len(products_map)}")

# 3. パーツ一覧を組み立て（part_type フィルタなし）
parts = ds._build_parts_from_products_map(products_map, url, max_items=1000)
print(f"  Parts built: {len(parts)}")

# 4. 検出された type を集計してから DB 保存
created = 0
updated = 0
skipped = 0
type_counter = Counter()
ALLOWED_TYPES = {"cpu", "cpu_cooler", "gpu", "motherboard", "memory", "storage", "os", "psu", "case"}

for p in parts:
    detected_type = p.get("part_type")
    if not detected_type or detected_type not in ALLOWED_TYPES:
        skipped += 1
        continue
    type_counter[detected_type] += 1
    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": detected_type,
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

dominant_type = type_counter.most_common(1)[0][0] if type_counter else "unknown"
qs = PCPart.objects.filter(part_type=dominant_type) if dominant_type != "unknown" else PCPart.objects.none()

print({
    "status": "success",
    "source": "BR116",
    "codes_found": len(codes),
    "fetched": len(parts),
    "created": created,
    "updated": updated,
    "skipped": skipped,
    "by_type": dict(type_counter),
    "dominant_type": dominant_type,
    "total_in_db": qs.count(),
    "min_price": qs.order_by("price").values_list("price", flat=True).first(),
    "max_price": qs.order_by("-price").values_list("price", flat=True).first(),
})
'@ | & $pythonExe manage.py shell
