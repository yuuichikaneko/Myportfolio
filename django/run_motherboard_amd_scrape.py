import requests
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/mb-amd?srule=01&includeNotInventory=false"

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
    if p.get("part_type") != "motherboard":
        skipped += 1
        continue

    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": "motherboard",
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

mb_qs = PCPart.objects.filter(part_type="motherboard")

print(
    {
        "status": "success",
        "source_url": URL,
        "codes_found": len(codes),
        "fetched_parts": len(parts),
        "saved_mb_created": created,
        "saved_mb_updated": updated,
        "skipped_non_motherboard": skipped,
        "motherboard_total_in_db": mb_qs.count(),
        "sample_names": list(mb_qs.order_by("price").values_list("name", flat=True)[:10]),
    }
)
