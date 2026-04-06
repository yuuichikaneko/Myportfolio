import csv
from pathlib import Path

base = Path(__file__).parent
cpu_csv = base / "全パーツ_cpu.csv"

# ユーザー提示 + 既存運用で使っている性能目安
perf_map = {
    "Ryzen 7 9850X3D": 4373,
    "Ryzen 7 9800X3D": 4208,
    "Ryzen 7 9700X": 3904,
    "Ryzen 7 8700G": 3329,
    "Ryzen 7 7700": 3622,
    "Ryzen 7 7800X3D": 4208,
    "Ryzen 5 9600X": 3163,
    "Ryzen 5 9600": 3090,
}

keys_by_length = sorted(perf_map.keys(), key=len, reverse=True)

rows = []
with cpu_csv.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        name = r["名称"]
        if "Ryzen" not in name:
            continue
        price = int(r["価格"].replace("¥", "").replace(",", ""))
        url = r["URL"].strip()
        match_key = None
        for k in keys_by_length:
            if k in name:
                match_key = k
                break
        if not match_key:
            continue
        perf = perf_map[match_key]
        if perf < 3000:
            continue
        if not url:
            continue
        value = perf / price
        rows.append((name, price, perf, value, url, match_key))

rows.sort(key=lambda x: x[3], reverse=True)

out_csv = base / "AMDゲーミング候補_性能3000以上_URLあり.csv"
with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["順位", "CPU", "価格", "性能目安", "コスパ値", "URL"])
    for i, (name, price, perf, value, url, _) in enumerate(rows, 1):
        w.writerow([i, name, price, perf, f"{value:.6f}", url])

print("AMD gaming candidates (perf>=3000, URLあり):", len(rows))
for i, (name, price, perf, value, url, _) in enumerate(rows, 1):
    print(f"{i:>2}. {name} | price={price} | perf={perf} | value={value:.6f}")

expected = {"Ryzen 7 9850X3D", "Ryzen 7 9800X3D", "Ryzen 7 9700X", "Ryzen 7 8700G", "Ryzen 7 7700", "Ryzen 7 7800X3D", "Ryzen 5 9600X", "Ryzen 5 9600"}
present = set()
for _, _, _, _, _, matched_key in rows:
    present.add(matched_key)

missing = sorted(expected - present)
print("\nmissing_from_catalog:")
for m in missing:
    print("-", m)

print("\noutput_csv:")
print(out_csv)
