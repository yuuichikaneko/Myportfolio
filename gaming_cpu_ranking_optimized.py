#!/usr/bin/env python
"""
ゲーミングPC用CPU ランキング
Intel 13/14世代と性能3000以下を除外
"""
from pathlib import Path

def is_excluded_intel_gen(name):
    """Intel 13/14世代かどうか判定"""
    excluded_patterns = [
        'Core i3-13',
        'Core i5-13',
        'Core i7-13',
        'Core i9-13',
        'Core i3-14',
        'Core i5-14',
        'Core i7-14',
        'Core i9-14',
    ]
    for pattern in excluded_patterns:
        if pattern in name:
            return True
    return False

def parse_amd_ranking(filename):
    """AMD ランキング CSV を読み込む"""
    cpus = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('順位'):
                continue
            
            # フォーマット: 順位. CPU | perf=xxx | price=¥xxx | value=xxx
            if '|' not in line:
                continue
            
            try:
                parts = [p.strip() for p in line.split('|')]
                
                first_part = parts[0]
                if '.' in first_part:
                    name = first_part.split('.', 1)[1].strip()
                else:
                    continue
                
                perf_part = parts[1] if len(parts) > 1 else ''
                perf = int(perf_part.replace('perf=', '').strip())
                
                price_part = parts[2] if len(parts) > 2 else ''
                price = int(price_part.replace('price=¥', '').strip())
                
                value_part = parts[3] if len(parts) > 3 else ''
                value = float(value_part.replace('value=', '').strip())
                
                cpus.append({
                    'name': name,
                    'price': price,
                    'performance': perf,
                    'value': value
                })
            except (ValueError, IndexError):
                continue
    
    return cpus

def parse_intel_ranking(filename):
    """Intel ランキング CSV を読み込む"""
    cpus = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('順位'):
                continue
            
            # フォーマット: 順位\tCPU\t価格\t性能目安\tコスパ値
            parts = line.split('\t')
            if len(parts) < 5:
                continue
            
            try:
                name = parts[1]
                price_str = parts[2].replace('円', '').replace(',', '')
                perf_str = parts[3].replace(',', '')
                value_str = parts[4]
                
                price = int(price_str)
                perf = int(perf_str)
                value = float(value_str)
                
                cpus.append({
                    'name': name,
                    'price': price,
                    'performance': perf,
                    'value': value
                })
            except (ValueError, IndexError):
                continue
    
    return cpus

def get_gaming_cpus():
    """ゲーミングPC用CPU取得（性能3000以上、13/14世代除外）"""
    base_path = Path(__file__).parent
    
    amd_file = base_path / 'AMDコスパ順.txt'
    intel_file = base_path / 'Intelコスパ順.txt'
    
    all_cpus = []
    
    # AMD データ読込
    if amd_file.exists():
        amd_cpus = parse_amd_ranking(amd_file)
        for cpu in amd_cpus:
            if cpu['performance'] >= 3000:
                all_cpus.append(cpu)
    
    # Intel データ読込
    if intel_file.exists():
        intel_cpus = parse_intel_ranking(intel_file)
        for cpu in intel_cpus:
            # 13/14世代を除外
            if is_excluded_intel_gen(cpu['name']):
                continue
            # 性能3000以上
            if cpu['performance'] >= 3000:
                all_cpus.append(cpu)
    
    # コスパ値でソート
    all_cpus.sort(key=lambda x: x['value'], reverse=True)
    return all_cpus

def display_ranking(cpus):
    """ランキングを表示"""
    print(f"\n[ゲーミングPC用CPU] 性能3000以上、Intel 13/14世代除外")
    print(f"{'='*100}")
    print(f"{'順位':<4} {'CPU':<45} {'価格':<10} {'性能':<6} {'コスパ':<8}")
    print(f"{'-'*100}")
    
    for i, cpu in enumerate(cpus, 1):
        name = cpu['name'][:42] + '...' if len(cpu['name']) > 45 else cpu['name']
        price = cpu['price']
        perf = cpu['performance']
        value = cpu['value']
        print(f"{i:<4} {name:<45} {price:>8}円 {perf:>6} {value:>8.5f}")

def save_to_csv(cpus):
    """CSV に保存"""
    import csv
    base_path = Path(__file__).parent
    
    # AMD vs Intel に分割
    amd = [c for c in cpus if 'Ryzen' in c['name']]
    intel = [c for c in cpus if 'Intel' in c['name']]
    
    # 統合ランキング
    filename = base_path / 'ゲーミングPC_CPU_ランキング.csv'
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['順位', 'CPU', '価格', '性能', 'コスパ'])
        for i, cpu in enumerate(cpus, 1):
            writer.writerow([i, cpu['name'], cpu['price'], cpu['performance'], f"{cpu['value']:.5f}"])
    print(f"\n> {filename.name} - {len(cpus)}件")
    
    # AMD
    if amd:
        filename = base_path / 'ゲーミングPC_AMD_CPU.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['順位', 'CPU', '価格', '性能', 'コスパ'])
            for i, cpu in enumerate(amd, 1):
                writer.writerow([i, cpu['name'], cpu['price'], cpu['performance'], f"{cpu['value']:.5f}"])
        print(f"> {filename.name} - {len(amd)}件")
    
    # Intel
    if intel:
        filename = base_path / 'ゲーミングPC_Intel_CPU.csv'
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['順位', 'CPU', '価格', '性能', 'コスパ'])
            for i, cpu in enumerate(intel, 1):
                writer.writerow([i, cpu['name'], cpu['price'], cpu['performance'], f"{cpu['value']:.5f}"])
        print(f"> {filename.name} - {len(intel)}件")

# メイン
if __name__ == '__main__':
    cpus = get_gaming_cpus()
    
    print(f"\n[取得結果] ゲーミングPC用CPU: {len(cpus)}件")
    print(f"(Intel 13/14世代と性能3000以下を除外)")
    
    if cpus:
        display_ranking(cpus)
        
        print(f"\n[CSV保存]")
        save_to_csv(cpus)
    
    print("\n[完了]")
