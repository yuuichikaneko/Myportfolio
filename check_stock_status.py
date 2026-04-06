#!/usr/bin/env python
"""
パーツの在庫状態を確認
"""
import os
import sys
import django
from pathlib import Path

# Django 設定
django_path = Path(__file__).parent / 'django'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myportfolio_django.settings')
sys.path.insert(0, str(django_path))

django.setup()

from scraper.models import PCPart
from django.db.models import Q

# メイン処理
if __name__ == '__main__':
    print("=" * 100)
    print("パーツの在庫状態確認")
    print("=" * 100)
    
    # 全パーツ数
    total = PCPart.objects.filter(is_active=True).count()
    print(f"\n✓ 全パーツ数: {total}件")
    
    # 在庫状態の種類を確認
    stock_statuses = PCPart.objects.filter(is_active=True).values_list('stock_status', flat=True).distinct()
    print(f"\n✓ 存在する在庫状態:")
    for status in sorted(stock_statuses):
        count = PCPart.objects.filter(is_active=True, stock_status=status).count()
        print(f"  - {status}: {count}件")
    
    # 各パーツタイプの在庫状態を確認
    print(f"\n✓ パーツタイプ別在庫状態:")
    part_types = PCPart.objects.filter(is_active=True).values_list('part_type', flat=True).distinct()
    for part_type in sorted(part_types):
        print(f"\n  【{part_type}】")
        statuses = PCPart.objects.filter(is_active=True, part_type=part_type).values_list('stock_status', flat=True).distinct()
        for status in sorted(statuses):
            count = PCPart.objects.filter(is_active=True, part_type=part_type, stock_status=status).count()
            print(f"    - {status}: {count}件")
    
    print("\n✅ 確認完了！")
