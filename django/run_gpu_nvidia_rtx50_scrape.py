import requests
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/nvidia-geforce?prefn1=txChipFilter&prefv1=GeForce%20RTX%205090%7cGeForce%20RTX%205080%7cGeForce%20RTX%205070%20Ti%7cGeForce%20RTX%205070%7cGeForce%20RTX%205060%20Ti%7cGeForce%20RTX%205060%7cGeForce%20RTX%205050%7cGeForce%20RTX%203050&srule=01&includeNotInventory=false"

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
    if p.get("part_type") != "gpu":
        skipped += 1
        continue

    _, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": "gpu",
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

gpu_qs = PCPart.objects.filter(part_type="gpu")

print(
    {
        "status": "success",
        "source_url": URL,
        "codes_found": len(codes),
        "fetched_parts": len(parts),
        "saved_gpu_created": created,
        "saved_gpu_updated": updated,
        "skipped_non_gpu": skipped,
        "gpu_total_in_db": gpu_qs.count(),
        "sample_names": list(gpu_qs.order_by("price").values_list("name", flat=True)[:12]),
    }
)
