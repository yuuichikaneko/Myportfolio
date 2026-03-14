import os
import re
import sys
import django

sys.path.insert(0, r"F:\Python\Myportfolio\django")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myportfolio_django.settings")
django.setup()

from scraper.views import build_configuration_response

budget = 169980
n = 10
bad = []
totals = []

for i in range(n):
    res, err = build_configuration_response(
        budget,
        "gaming",
        cooler_type="air",
        radiator_size="240",
        cooling_profile="performance",
        case_size="mid",
        cpu_vendor="any",
        build_priority="spec",
    )
    if err:
        bad.append((i, "error", str(getattr(err, "data", None))))
        continue

    parts = {p["category"]: p for p in res["parts"]}
    gpu = parts.get("gpu", {}).get("price", 0)
    mem = parts.get("memory", {}).get("price", 0)
    sto_name = (parts.get("storage", {}).get("name") or "")
    sto_specs = (parts.get("storage", {}).get("specs", {}) or {})
    sto_cap = sto_specs.get("capacity_gb")

    cap = sto_cap if isinstance(sto_cap, int) else 0
    if cap <= 0:
        m_tb = re.search(r"(\d+)\s*TB", sto_name, re.I)
        m_gb = re.search(r"(\d+)\s*GB", sto_name, re.I)
        if m_tb:
            cap = int(m_tb.group(1)) * 1000
        elif m_gb:
            cap = int(m_gb.group(1))

    ok_gpu = gpu >= mem
    ok_sto = cap >= 1000
    ok_budget = res.get("total_price", 10**9) <= budget
    totals.append(res.get("total_price", 0))

    if not (ok_gpu and ok_sto and ok_budget):
        bad.append((i, ok_gpu, ok_sto, ok_budget, gpu, mem, cap, res.get("total_price")))

print("RUNS", n)
print("BAD_COUNT", len(bad))
if bad:
    print("BAD_FIRST5", bad[:5])
if totals:
    print("TOTAL_MIN_MAX", min(totals), max(totals))
