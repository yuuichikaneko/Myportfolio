from config.models import Configuration
from scraper.models import PCPart

c = Configuration.objects.get(id=273)
print(f"ID 273 の構成情報:")
print(f"  用途: {c.usage}")
print(f"  選定方針: {c.selection_policy}")
print(f"  CPU: {c.cpu.name if c.cpu else 'None'}")
print(f"  CPU価格: {c.cpu.price if c.cpu else 'N/A'}")

# 同じ用途で生成されたときにどのCPUが候補だったか確認
print(f"\n同じ条件での CPU 候補:")
print(f"  用途: {c.usage}")
print(f"  予算: {c.total_budget}")
# 推定される CPU 選定条件
usage = c.usage
budget_weights = {
    'creator': {'cpu': 0.27, 'gpu': 0.15, 'memory': 0.16, 'storage': 0.11, 'others': 0.31},
    'gaming': {'cpu': 0.15, 'gpu': 0.35, 'memory': 0.10, 'storage': 0.10, 'others': 0.30},
    'business': {'cpu': 0.20, 'gpu': 0.05, 'memory': 0.20, 'storage': 0.15, 'others': 0.40},
}

if usage in budget_weights:
    cpu_allocation = int(c.total_budget * budget_weights[usage]['cpu'])
    print(f"  推定 CPU 予算枠: ¥{cpu_allocation}")
    
    # 予算内の CPU 確認
    try:
        cpus = PCPart.objects.filter(
            part_type='cpu',
            price__lte=cpu_allocation*1.15  # 少し余裕を持たせる
        ).order_by('-core_count')
        print(f"\n予算内の CPU:")
        for cpu in cpus[:5]:
            print(f"    {cpu.name}: ¥{cpu.price}")
    except:
        pass
