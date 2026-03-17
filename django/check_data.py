import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
django.setup()

from scraper.models import PCPart, ScraperStatus

print("PCParts数:", PCPart.objects.count())
parts = list(PCPart.objects.values_list('part_type', flat=True).distinct())
print("パーツ種別:", parts)

# 各パーツ種別のカウント
for part_type in sorted(parts):
    count = PCPart.objects.filter(part_type=part_type).count()
    print(f"  {part_type}: {count}個")

# ScraperStatus 確認
status = ScraperStatus.objects.first()
if status:
    print(f"最後の実行: {status.last_run}")
    print(f"合計スクレイプ: {status.total_scraped}")
    print(f"成功回数: {status.success_count}")
else:
    print("ScraperStatus: なし")
