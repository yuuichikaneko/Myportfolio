Set-Location "$PSScriptRoot/django"

$pythonExe = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "py"
}

@'
import scraper.dospara_scraper as ds
from scraper.models import PCPart

url = "https://www.dospara.co.jp/BR12?srule=04&includeNotInventory=false"
ds.PART_CATEGORY_URLS = {"memory": [url]}
parts = ds.scrape_dospara_category_parts(timeout=20, max_items_per_category=200)

created = 0
updated = 0
for p in parts:
    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": "memory",
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

qs = PCPart.objects.filter(part_type="memory")
print({
    "status": "success",
    "source": "BR12",
    "fetched": len(parts),
    "created": created,
    "updated": updated,
    "total_memory": qs.count(),
    "min_price": qs.order_by("price").values_list("price", flat=True).first(),
    "max_price": qs.order_by("-price").values_list("price", flat=True).first(),
})
'@ | & $pythonExe manage.py shell
