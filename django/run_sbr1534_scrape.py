import requests
from collections import Counter
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/SBR1534?srule=01&includeNotInventory=false"

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
saved_type_counter = Counter()
found_type_counter = Counter()

for p in parts:
    part_type = p.get("part_type")
    found_type_counter[part_type or "unknown"] += 1
    if not part_type:
        skipped += 1
        continue

    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": part_type,
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1
    saved_type_counter[part_type] += 1

print(
    {
        "status": "success",
        "source_url": URL,
        "codes_found": len(codes),
        "fetched_parts": len(parts),
        "saved_created": created,
        "saved_updated": updated,
        "skipped": skipped,
        "found_type_counts": dict(found_type_counter),
        "saved_type_counts": dict(saved_type_counter),
        "db_total_parts": PCPart.objects.count(),
    }
)
