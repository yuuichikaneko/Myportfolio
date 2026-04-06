#!/usr/bin/env python
"""
在庫有りの全パーツデータを取得・表示
"""
import os
import sys
import django
from pathlib import Path
from django.db.models import Q

# Django 設定
django_path = Path(__file__).parent / 'django'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, str(django_path))

django.setup()

from scraper.models import PCPart

def get_all_parts():
    """すべてのアクティブなパーツを取得"""
    parts = PCPart.objects.filter(
        is_active=True
    ).order_by('part_type', 'price').values('id', 'part_type', 'name', 'price', 'specs', 'stock_status', 'url', 'scraped_at')
    
    return list(parts)

def display_parts_by_type(parts):
    """パーツタイプ別に表示"""
    from collections import defaultdict
    
    by_type = defaultdict(list)
    for part in parts:
        by_type[part['part_type']].append(part)
    
    for part_type in sorted(by_type.keys()):
        items = by_type[part_type]
        print(f"\n[{part_type}] - {len(items)}件")
        count = 0
        for item in sorted(items, key=lambda x: x['price'])[:5]:  # 最初の5件だけ表示
            count += 1
            name = item['name'][:35]
            price = item['price']
            print(f"  {count}. {name} - {price}円")

def save_to_csv(parts):
    """CSV ファイルに保存"""
    import csv
    from collections import defaultdict
    
    by_type = defaultdict(list)
    for part in parts:
        by_type[part['part_type']].append(part)
    
    base_path = Path(__file__).parent
    
    for part_type, items in sorted(by_type.items()):
        filename = base_path / f'全パーツ_{part_type}.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'パーツタイプ', '名称', '価格', '在庫状態', 'URL'])
            for item in sorted(items, key=lambda x: x['price']):
                writer.writerow([
                    item['id'],
                    item['part_type'],
                    item['name'],
                    f"¥{item['price']:,}",
                    item['stock_status'],
                    item['url']
                ])
        print(f"> {filename.name} - {len(items)}件")

# メイン処理
if __name__ == '__main__':
    print("=" * 100)
    print("全パーツデータ取得")
    print("=" * 100)
    
    parts = get_all_parts()
    print(f"\n[結果] 全パーツ合計: {len(parts)}件")
    
    # タイプ別に表示
    display_parts_by_type(parts)
    
    # CSV に保存
    print(f"\n{'='*100}")
    print("CSV ファイルに保存中...")
    print(f"{'='*100}")
    save_to_csv(parts)
    
    print("\n[完了]")
