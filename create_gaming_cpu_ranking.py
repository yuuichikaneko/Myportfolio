#!/usr/bin/env python
"""
ゲーミングPC用CPU ランキング生成スクリプト
既存の txt ファイルから性能3000以上のランキングを再作成
"""
from pathlib import Path
import re

GAMING_EXCLUDED_CREATOR_CPU_MODELS = {
    'ryzen 5 7500f',
    'ryzen 5 9500f',
    'ryzen 7 8700g',
    'ryzen 9 9900x',
    'ryzen 9 9900x3d',
    'ryzen 9 9950x',
    'ryzen 9 9950x3d',
}

def parse_cpu_ranking(filename):
    """txt ファイルから CPU データを抽出（AMD/Intel 両フォーマット対応）"""
    cpus = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('順位'):
                continue
            
            # フォーマット判定
            if '|' in line:
                # AMD フォーマット: 順位. CPU | perf=xxx | price=¥xxx | value=xxx
                cpus.extend(_parse_amd_format(line))
            elif '\t' in line:
                # Intel フォーマット: 順位\tCPU\t価格\t性能目安\tコスパ値
                cpus.extend(_parse_intel_format(line))
    
    return cpus


def is_allowed_intel_for_gaming_table(cpu):
    """ゲーミング統合表では Intel は Core Ultra 7 265 のみ残す。"""
    name = re.sub(r'\s+', ' ', cpu.get('name', '')).strip().upper()
    return bool(re.search(r'\bCORE ULTRA 7 265\b', name))

def _parse_amd_format(line):
    """AMD フォーマットのパース"""
    result = []
    try:
        parts = [p.strip() for p in line.split('|')]
        
        # パート1: 順位とCPU名
        first_part = parts[0]
        if '.' in first_part:
            name = first_part.split('.', 1)[1].strip()
        else:
            return result
        
        # パート2: perf
        perf_part = parts[1] if len(parts) > 1 else ''
        perf = int(perf_part.replace('perf=', '').strip())
        
        # パート3: price
        price_part = parts[2] if len(parts) > 2 else ''
        price = int(price_part.replace('price=¥', '').strip())
        
        # パート4: value
        value_part = parts[3] if len(parts) > 3 else ''
        value = float(value_part.replace('value=', '').strip())
        
        result.append({
            'name': name,
            'price': price,
            'performance': perf,
            'value': value
        })
    except (ValueError, IndexError):
        pass
    
    return result

def _parse_intel_format(line):
    """Intel フォーマットのパース"""
    result = []
    try:
        parts = line.split('\t')
        if len(parts) < 5:
            return result
        
        name = parts[1]
        price_str = parts[2].replace('円', '').replace(',', '')
        perf_str = parts[3].replace(',', '')
        value_str = parts[4]
        
        price = int(price_str)
        perf = int(perf_str)
        value = float(value_str)
        
        result.append({
            'name': name,
            'price': price,
            'performance': perf,
            'value': value
        })
    except (ValueError, IndexError):
        pass
    
    return result


def _normalize_cpu_name(text):
    normalized = ' '.join((text or '').strip().lower().split())
    normalized = normalized.replace('amd ', '')
    normalized = normalized.replace(' box', '')
    return normalized

def filter_by_performance(cpus, min_perf=3000):
    """性能 min_perf 以上でフィルタ"""
    return [
        c for c in cpus
        if c['performance'] >= min_perf
        and _normalize_cpu_name(c['name']) not in GAMING_EXCLUDED_CREATOR_CPU_MODELS
    ]

def sort_by_value(cpus):
    """コスパ値でソート"""
    return sorted(cpus, key=lambda x: x['value'], reverse=True)

def save_ranking(cpus, filename):
    """ランキングをファイルに保存"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("順位\tCPU\t価格\t性能\tコスパ値\n")
        for i, cpu in enumerate(cpus, 1):
            f.write(f"{i}\t{cpu['name']}\t¥{cpu['price']:,}\t{cpu['performance']}\t{cpu['value']:.6f}\n")
    print(f"✓ {filename} を作成しました（{len(cpus)}件）")

# メイン処理
if __name__ == '__main__':
    base_path = Path(__file__).parent
    
    print("=" * 70)
    print("ゲーミングPC用 CPU ランキング生成（性能スコア 3000以上）")
    print("=" * 70)
    
    # AMD と Intel の統合ランキング作成
    amd_file = base_path / 'AMDコスパ順.txt'
    intel_file = base_path / 'Intelコスパ順.txt'
    
    all_cpus = []
    
    # AMD データ読込
    if amd_file.exists():
        amd_cpus = parse_cpu_ranking(amd_file)
        amd_filtered = filter_by_performance(amd_cpus, 3000)
        print(f"\n✓ {amd_file.name} から {len(amd_filtered)}/{len(amd_cpus)} 件を抽出")
        all_cpus.extend(amd_filtered)
    
    # Intel データ読込
    if intel_file.exists():
        intel_cpus = parse_cpu_ranking(intel_file)
        intel_filtered = [
            cpu for cpu in filter_by_performance(intel_cpus, 3000)
            if is_allowed_intel_for_gaming_table(cpu)
        ]
        print(f"✓ {intel_file.name} から {len(intel_filtered)}/{len(intel_cpus)} 件を抽出")
        all_cpus.extend(intel_filtered)
    
    # 統合データをコスパでソート
    all_sorted = sort_by_value(all_cpus)
    
    print(f"\n合計: {len(all_sorted)} 件")
    
    # ファイル出力
    save_ranking(all_sorted, str(base_path / 'ゲーミングCPUランキング（性能3000以上）.txt'))

    # AMD のみ
    if amd_file.exists():
        amd_sorted = sort_by_value(amd_filtered)
        save_ranking(amd_sorted, str(base_path / 'AMD ゲーミング用コスパ順（性能3000以上）.txt'))
    
    # Intel のみ
    if intel_file.exists():
        intel_sorted = sort_by_value(intel_filtered)
        save_ranking(intel_sorted, str(base_path / 'Intel ゲーミング用コスパ順（性能3000以上）.txt'))
    
    print("\n✅ 完了！")
