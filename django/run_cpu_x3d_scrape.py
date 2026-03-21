import requests
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/cpu?q=x3d&lang=ja_JP&srule=01"

config = ds.get_dospara_scraper_config()
session = requests.Session()

resp = session.get(URL, headers=config["headers"], timeout=30)
resp.raise_for_status()

codes = ds._collect_ic_codes_from_category_pages(
    html=resp.text,
    category_url=URL,
    headers=config["headers"],
    timeout=20,
    session=session,
    max_codes=2000,
)

products_map = ds._fetch_products_by_codes(
    codes=codes,
    api_url=config["products_api_url"],
    headers=config["headers"],
    timeout=20,
    batch_size=config["batch_size"],
    session=session,
)

parts = ds._build_parts_from_products_map(products_map, URL, max_items=2000)

created = 0
updated = 0
skipped = 0

for p in parts:
    if p.get("part_type") != "cpu":
        skipped += 1
        continue

    _, is_created = PCPart.objects.update_or_create(
        part_type="cpu",
        name=p.get("name"),
        defaults={
            "url": p.get("url"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

cpu_qs = PCPart.objects.filter(part_type="cpu")
x3d_qs = cpu_qs.filter(name__icontains="x3d") | cpu_qs.filter(url__icontains="x3d")
x3d_qs = x3d_qs.distinct().order_by("price")

print(
    {
        "status": "success",
        "source_url": URL,
        "codes_found": len(codes),
        "fetched_parts": len(parts),
        "saved_cpu_created": created,
        "saved_cpu_updated": updated,
        "skipped_non_cpu": skipped,
        "cpu_total_in_db": cpu_qs.count(),
        "x3d_total_in_db": x3d_qs.count(),
        "x3d_samples": list(x3d_qs.values_list("name", flat=True)[:10]),
    }
)
