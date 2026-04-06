import os
import sys
from pathlib import Path

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myportfolio_django.settings")
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

import scraper.dospara_scraper as ds
from scraper.models import PCPart
from generate_cpu_ranking_db import generate_and_save_rankings


TARGETS = [
    "Ryzen 9 9900X3D",
    "Ryzen 9 9950X",
]


def _contains_target(name: str) -> bool:
    text = (name or "").lower()
    return any(t.lower() in text for t in TARGETS)


def main() -> None:
    config = ds.get_dospara_scraper_config()
    session = requests.Session()

    created = 0
    updated = 0
    skipped_non_cpu = 0
    skipped_non_target = 0
    total_codes = 0
    total_parts = 0

    for target in TARGETS:
        url = f"https://www.dospara.co.jp/cpu?q={requests.utils.quote(target)}&lang=ja_JP&srule=01&includeNotInventory=false"

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
        total_codes += len(codes)

        products_map = ds._fetch_products_by_codes(
            codes=codes,
            api_url=config["products_api_url"],
            headers=config["headers"],
            timeout=20,
            batch_size=config["batch_size"],
            session=session,
        )

        parts = ds._build_parts_from_products_map(products_map, url, max_items=2000)
        total_parts += len(parts)

        for p in parts:
            if p.get("part_type") != "cpu":
                skipped_non_cpu += 1
                continue

            if not _contains_target(p.get("name", "")):
                skipped_non_target += 1
                continue

            _, is_created = PCPart.objects.update_or_create(
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
    target_qs = cpu_qs.filter(name__icontains="9900x3d") | cpu_qs.filter(name__icontains="9950x")
    target_qs = target_qs.distinct().order_by("price")

    print(
        {
            "status": "success",
            "targets": TARGETS,
            "codes_found_total": total_codes,
            "fetched_parts_total": total_parts,
            "saved_cpu_created": created,
            "saved_cpu_updated": updated,
            "skipped_non_cpu": skipped_non_cpu,
            "skipped_non_target": skipped_non_target,
            "cpu_total_in_db": cpu_qs.count(),
            "target_total_in_db": target_qs.count(),
            "target_names": list(target_qs.values_list("name", flat=True)),
        }
    )

    # 取り込み後に同条件の総合ランキングCSVを自動再生成
    generate_and_save_rankings()


if __name__ == "__main__":
    main()
