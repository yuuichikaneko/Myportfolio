import requests
import scraper.dospara_scraper as ds
from scraper.models import PCPart

URL = "https://www.dospara.co.jp/cpu?prefn1=txSpec001&prefv1=16%ef%bd%9e24%e3%82%b3%e3%82%a2&srule=01&includeNotInventory=false"

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
print(f"IC codes collected: {len(codes)}")

products_map = ds._fetch_products_by_codes(
    codes=codes,
    api_url=config["products_api_url"],
    headers=config["headers"],
    timeout=20,
    batch_size=config["batch_size"],
    session=session,
)
print(f"Products fetched: {len(products_map)}")

parts = ds._build_parts_from_products_map(products_map, URL, max_items=2000)
print(f"Parts built: {len(parts)}")

created = 0
updated = 0
skipped = 0

for p in parts:
    # 念のためCPUのみ保存
    if p.get("part_type") != "cpu":
        skipped += 1
        continue

    obj, is_created = PCPart.objects.update_or_create(
        url=p.get("url"),
        defaults={
            "name": p.get("name"),
            "price": p.get("price"),
            "specs": p.get("specs", {}),
            "part_type": "cpu",
        },
    )
    if is_created:
        created += 1
    else:
        updated += 1

cpu_qs = PCPart.objects.filter(part_type="cpu")

print({
    "status": "success",
    "source_url": URL,
    "codes_found": len(codes),
    "fetched_parts": len(parts),
    "saved_cpu_created": created,
    "saved_cpu_updated": updated,
    "skipped_non_cpu": skipped,
    "cpu_total_in_db": cpu_qs.count(),
    "cpu_min_price": cpu_qs.order_by("price").values_list("price", flat=True).first(),
    "cpu_max_price": cpu_qs.order_by("-price").values_list("price", flat=True).first(),
})
