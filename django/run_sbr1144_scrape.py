import requests
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/SBR1144?srule=01&includeNotInventory=false"

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
    max_codes=3000,
)

products_map = ds._fetch_products_by_codes(
    codes=codes,
    api_url=config["products_api_url"],
    headers=config["headers"],
    timeout=20,
    batch_size=config["batch_size"],
    session=session,
)

parts = ds._build_parts_from_products_map(products_map, URL, max_items=3000)

created = 0
updated = 0
for p in parts:
    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": p.get("part_type"),
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

part_types = sorted({p.get("part_type") for p in parts if p.get("part_type")})

print(
    {
        "status": "success",
        "source_url": URL,
        "codes_found": len(codes),
        "fetched_parts": len(parts),
        "saved_created": created,
        "saved_updated": updated,
        "part_types": part_types,
    }
)
