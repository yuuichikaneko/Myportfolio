import os
import sys
import django
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

logging.basicConfig(level=logging.INFO)

from scraper.dospara_scraper import scrape_dospara_parts, scrape_dospara_category_parts
from scraper.models import PCPart, ScraperStatus

print("=" * 60)
print("スクレイピング開始...")
print("=" * 60)

try:
    # メインスクレイピング実行
    scraped_parts = scrape_dospara_parts(
        timeout=10,
        max_items=50  # 少数の項目のみ
    )

    # カテゴリページも併用して、ローエンドGPUなどの取りこぼしを減らす
    category_parts = scrape_dospara_category_parts(
        timeout=10,
        max_items_per_category=80,
    )
    main_keys = {(p['part_type'], p['name']) for p in scraped_parts}
    for part in category_parts:
        key = (part['part_type'], part['name'])
        if key in main_keys:
            continue
        scraped_parts.append(part)
        main_keys.add(key)
    
    print(f"\n[OK] {len(scraped_parts)} 個のパーツを取得しました。")
    
    # データベースに保存
    saved_count = 0
    updated_count = 0
    
    for part in scraped_parts:
        obj, created = PCPart.objects.update_or_create(
            part_type=part['part_type'],
            name=part['name'],
            defaults={
                'price': part['price'],
                'url': part['url'],
                'specs': part.get('specs', {}),
                'stock_status': part.get('stock_status', 'unknown'),
                'is_active': part.get('is_active', True),
            }
        )
        if created:
            saved_count += 1
        else:
            updated_count += 1
    
    # ScraperStatus 更新
    status, _ = ScraperStatus.objects.get_or_create(id=1)
    status.last_run = django.utils.timezone.now()
    status.total_scraped = len(scraped_parts)
    status.success_count = (status.success_count or 0) + 1
    status.save()
    
    print(f"[OK] 新規保存: {saved_count} 個")
    print(f"[OK] 更新: {updated_count} 個")
    print(f"\n現在のDB: 全 {PCPart.objects.count()} 個のパーツ")
    
    # パーツタイプ別集計
    for part_type in sorted(PCPart.objects.values_list('part_type', flat=True).distinct()):
        count = PCPart.objects.filter(part_type=part_type).count()
        print(f"  {part_type}: {count}個")
    
    print("\n=" * 60)
    print("スクレイピング完了！")
    print("=" * 60)
    
except Exception as e:
    print(f"[ERROR] エラーが発生しました: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
