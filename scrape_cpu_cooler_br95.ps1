Set-Location "$PSScriptRoot/django"

$pythonExe = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "py"
}

@'
import scraper.dospara_scraper as ds
from scraper.models import PCPart

url = "https://www.dospara.co.jp/BR95?srule=04&includeNotInventory=false"
ds.PART_CATEGORY_URLS = {"cpu_cooler": [url]}
parts = ds.scrape_dospara_category_parts(timeout=20, max_items_per_category=120)

created = 0
updated = 0
for p in parts:
    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "currency": p.get("currency"),
            "availability": p.get("availability"),
            "shop": p.get("shop"),
            "part_type": "cpu_cooler",
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

qs = PCPart.objects.filter(part_type="cpu_cooler")
print({
    "status": "success",
    "source": "BR95",
    "fetched": len(parts),
    "created": created,
    "updated": updated,
    "total_cpu_cooler": qs.count(),
    "min_price": qs.order_by("price").values_list("price", flat=True).first(),
    "max_price": qs.order_by("-price").values_list("price", flat=True).first(),
})
'@ | & $pythonExe manage.py shell
