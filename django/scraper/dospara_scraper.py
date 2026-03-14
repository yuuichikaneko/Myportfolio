import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from django.conf import settings


logger = logging.getLogger(__name__)

DOSPARA_PARTS_URL = "https://www.dospara.co.jp/parts"
DOSPARA_PRODUCTS_API_URL = "https://www.dospara.co.jp/s/dospara/api/getProducts"
DOSPARA_UPDATE_GRID_URL = (
    "https://www.dospara.co.jp/on/demandware.store/"
    "Sites-dospara-Site/ja_JP/Search-UpdateGrid"
)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

# DOM差分に追随しやすいよう、抽出セレクタを設定化する。
SCRAPER_SELECTORS = {
    "item_roots": [
        "article",
        "li",
        "div[class*='item']",
        "div[class*='product']",
        "div[class*='card']",
    ],
    "name": [
        "a[title]",
        "h1",
        "h2",
        "h3",
        "a[href]",
    ],
    "price": [
        "[data-price]",
        "span[class*='price']",
        "div[class*='price']",
        "p[class*='price']",
    ],
    "link": [
        "a[href]",
    ],
}

SCRAPER_DEFAULT_CONFIG = {
    "url": DOSPARA_PARTS_URL,
    "products_api_url": DOSPARA_PRODUCTS_API_URL,
    "timeout": 20,
    "max_items": 500,
    "batch_size": 100,
    "headers": DEFAULT_HEADERS,
    "selectors": SCRAPER_SELECTORS,
}

PRICE_PATTERNS = [
    re.compile(r"([0-9][0-9,]{2,})\s*円"),
    re.compile(r"¥\s*([0-9][0-9,]{2,})"),
]

PRODUCT_LINK_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>[^"]*(?:IC\d+\.html|/SBR\d+/IC\d+\.html)[^"]*)"[^>]*>(?P<name>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
IC_CODE_PATTERN = re.compile(r"IC\d{6,}")

# ドスパラの一覧に混在する汎用カテゴリ名を、アプリの part_type へ寄せる。
CATEGORY_RULES = {
    "cpu_cooler": {
        "include": [
            "cpuクーラー",
            "cpu cooler",
            "air cooler",
            "water cooler",
            "aio",
            "簡易水冷",
            "水冷",
            "空冷",
            "radiator",
            "lga1700対応",
            "am5対応",
            "noctua",
            "deepcool",
            "corsair icue link h",
        ],
        "exclude": ["グリス", "thermal paste", "マザーボード", "motherboard", "pcケース"],
    },
    "cpu": {
        "include": ["ryzen", "core i", "pentium", "celeron", "core ultra", "xeon", "cpu box"],
        "exclude": ["グリス", "cooler", "クーラー", "ファン", "cpuクーラー", "water block"],
    },
    "gpu": {
        "include": ["geforce", "rtx", "radeon", "graphics", "arc ", "rx "],
        "exclude": ["monitor", "モニター", "gt 710", "gt710", "gt 1030", "gt1030"],
    },
    "motherboard": {
        "include": [
            "motherboard",
            "マザーボード",
            "chipset",
            "lga1700",
            "lga1851",
            "am4",
            "am5",
            "microatx",
            "mini-itx",
            "h610",
            "h670",
            "b550",
            "b650",
            "b760",
            "z690",
            "z790",
            "x670",
        ],
        "exclude": ["noctua", "nh-", "クーラー", "cooler", "ガラス"],
    },
    "memory": {
        "include": ["ddr4", "ddr5", "sodimm", "メモリ", "memory", "pc5-", "pc4-"],
        "exclude": ["ssd", "hdd", "nvme"],
    },
    "storage": {
        "include": ["ssd", "hdd", "nvme", "m.2", "storage", "ストレージ", "wd black", "wds"],
        "exclude": ["microatx", "mini-itx", "am5", "am4", "lga1700", "lga1851", "b650", "b760", "z790", "h610"],
    },
    "psu": {
        "include": ["power", "psu", "電源", "80 plus", "80plus", "pcie5", "atx3.0", "atx 3.0"],
        "exclude": ["ケーブル", "fan", "ファン"],
    },
    "case": {
        "include": ["pcケース", "case", "chassis", "ミドルタワー", "フルタワー", "ピラーレス", "ガラス"],
        "exclude": ["ケースファン", "ファン"],
    },
}

URL_CATEGORY_HINTS = {
    "cpu_cooler": ["/sbr95/", "/br95", "/cpu-cooler"],
    "cpu": ["/sbr2/", "/sbr8/", "/TC2/"],
    "gpu": ["/sbr4/", "/sbr1853/", "/TC8/"],
    "memory": ["/sbr5/", "/sbr1716/"],
    "storage": ["/sbr7/", "/sbr12/", "/sbr13/", "/sbr6/"],
    "psu": ["/sbr83/"],
    "case": ["/sbr79/", "/sbr447/", "/sbr143/", "/sbr1959/", "/sbr448/"],
    "motherboard": ["/sbr1739/", "/sbr1798/", "/sbr1297/", "/sbr21/"],
}

# パーツ種別ごとの価格帯取得用カテゴリページ URL
# ドスパラはURLパスの大文字小文字が厳密なため、小文字に統一する。
PART_CATEGORY_URLS: Dict[str, List[str]] = {
    "cpu":         ["https://www.dospara.co.jp/cpu", "https://www.dospara.co.jp/BR11", "https://www.dospara.co.jp/BR10"],
    "cpu_cooler":  ["https://www.dospara.co.jp/BR95"],
    "gpu":         ["https://www.dospara.co.jp/BR31"],
    "motherboard": ["https://www.dospara.co.jp/BR21", "https://www.dospara.co.jp/mb-intel", "https://www.dospara.co.jp/mb-amd"],
    "memory":      ["https://www.dospara.co.jp/BR12", "https://www.dospara.co.jp/mem-note"],
    "storage":     ["https://www.dospara.co.jp/BR115", "https://www.dospara.co.jp/BR13", "https://www.dospara.co.jp/m2ssd"],
    "psu":         ["https://www.dospara.co.jp/BR83", "https://www.dospara.co.jp/SBR755"],
    "case":        ["https://www.dospara.co.jp/BR72", "https://www.dospara.co.jp/case-tower", "https://www.dospara.co.jp/case-compact"],
}

MARKET_BRAND_URLS = {
    "galleria_gaming": "https://www.dospara.co.jp/gamepc",
    "galleria_creator": "https://www.dospara.co.jp/create",
    "thirdwave_gpu": "https://www.dospara.co.jp/TC973",
    "thirdwave_note": "https://www.dospara.co.jp/general_note",
    "thirdwave_desktop": "https://www.dospara.co.jp/general_desk",
    "thirdwave_business": "https://www.dospara.co.jp/business",
}

PRICE_IN_HTML_PATTERN = re.compile(r"([1-9][0-9]{1,2},[0-9]{3})")


def _normalize_price(price_text: str) -> Optional[int]:
    digits = re.sub(r"[^0-9]", "", price_text or "")
    if not digits:
        return None
    return int(digits)


def _extract_market_prices(html: str) -> List[int]:
    prices: List[int] = []
    for match in PRICE_IN_HTML_PATTERN.finditer(html or ""):
        normalized = _normalize_price(match.group(1))
        if normalized is None:
            continue
        # 現実的なBTO PC価格帯のみに絞る
        if 70000 <= normalized <= 1200000:
            prices.append(normalized)
    return prices


def fetch_dospara_market_price_range(timeout: int = 15, session: Optional[requests.Session] = None) -> Dict:
    client = session or requests.Session()
    headers = DEFAULT_HEADERS

    per_brand: Dict[str, Dict] = {}
    all_prices: List[int] = []

    for brand, url in MARKET_BRAND_URLS.items():
        try:
            response = client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            prices = _extract_market_prices(response.text)
            if not prices:
                per_brand[brand] = {"url": url, "min": None, "max": None, "count": 0}
                continue

            per_brand[brand] = {
                "url": url,
                "min": min(prices),
                "max": max(prices),
                "count": len(prices),
            }
            all_prices.extend(prices)
        except Exception:
            per_brand[brand] = {"url": url, "min": None, "max": None, "count": 0}

    if all_prices:
        market_min = min(all_prices)
        market_max = max(all_prices)
        # 中央値 - 15,000円をデフォルトにする
        median_price = (market_min + market_max) / 2
        suggested_default = max(market_min, int(median_price) - 15000)
    else:
        # 取得失敗時の安全なフォールバック
        market_min = 100000
        market_max = 400000
        suggested_default = 250000

    return {
        "min": market_min,
        "max": market_max,
        "default": suggested_default,
        "currency": "JPY",
        "sources": per_brand,
    }


def _infer_part_type(name: str, url: str) -> Optional[str]:
    blob = f"{name} {url}".lower()

    # GT 710/1030 などの GeForce GT シリーズは対象外にする。
    # GTX/RTX は対象に残すため、"gt" + 数字のみを判定する。
    is_gt_series_gpu = re.search(r"\bgt[\s\-_/]*\d{3,4}\b", blob) is not None

    for hinted_type, hinted_paths in URL_CATEGORY_HINTS.items():
        if any(path in url.lower() for path in hinted_paths):
            if hinted_type == "gpu" and is_gt_series_gpu:
                return None
            return hinted_type

    scores: Dict[str, int] = {}
    for part_type, rule in CATEGORY_RULES.items():
        score = 0
        for kw in rule.get("include", []):
            if kw in blob:
                score += 2
        for kw in rule.get("exclude", []):
            if kw in blob:
                score -= 3
        scores[part_type] = score

    best_type = max(scores, key=scores.get)
    if best_type == "gpu" and is_gt_series_gpu:
        return None
    return best_type if scores.get(best_type, 0) > 0 else None


def _merge_selector_config(base: Dict[str, List[str]], override: Optional[Dict[str, List[str]]]) -> Dict[str, List[str]]:
    merged = {key: list(value) for key, value in base.items()}
    if not override:
        return merged

    for key, value in override.items():
        if isinstance(value, list) and value:
            merged[key] = value
    return merged


def _merge_scraper_config(base: Dict, override: Optional[Dict]) -> Dict:
    if not override:
        return dict(base)

    merged = dict(base)
    for key, value in override.items():
        if key == "selectors":
            merged["selectors"] = _merge_selector_config(base.get("selectors", {}), value)
        elif key == "headers":
            merged_headers = dict(base.get("headers", {}))
            if isinstance(value, dict):
                merged_headers.update(value)
            merged["headers"] = merged_headers
        else:
            merged[key] = value
    return merged


def get_dospara_scraper_config() -> Dict:
    configured = getattr(settings, "DOSPARA_SCRAPER", {}) or {}
    env_name = getattr(settings, "DOSPARA_SCRAPER_ENV", "development")
    env_map = getattr(settings, "DOSPARA_SCRAPER_BY_ENV", {}) or {}
    env_override = env_map.get(env_name, {}) if isinstance(env_map, dict) else {}

    base_config = _merge_scraper_config(SCRAPER_DEFAULT_CONFIG, configured)
    merged = _merge_scraper_config(base_config, env_override)

    return {
        "url": merged.get("url", SCRAPER_DEFAULT_CONFIG["url"]),
        "products_api_url": merged.get("products_api_url", SCRAPER_DEFAULT_CONFIG["products_api_url"]),
        "timeout": merged.get("timeout", SCRAPER_DEFAULT_CONFIG["timeout"]),
        "max_items": merged.get("max_items", SCRAPER_DEFAULT_CONFIG["max_items"]),
        "batch_size": merged.get("batch_size", SCRAPER_DEFAULT_CONFIG["batch_size"]),
        "headers": merged.get("headers", SCRAPER_DEFAULT_CONFIG["headers"]),
        "selectors": merged.get("selectors", SCRAPER_SELECTORS),
        "env": env_name,
    }


def _extract_ic_codes(html: str, max_codes: int) -> List[str]:
    codes = []
    seen = set()
    for code in IC_CODE_PATTERN.findall(html or ""):
        if code in seen:
            continue
        seen.add(code)
        codes.append(code)
        if len(codes) >= max_codes:
            break
    return codes


def _extract_category_id(category_url: str) -> Optional[str]:
    match = re.search(r"dospara\.co\.jp/([A-Za-z]+\d+)", category_url or "", re.IGNORECASE)
    return match.group(1) if match else None


def _collect_ic_codes_from_category_pages(
    html: str,
    category_url: str,
    headers: Dict[str, str],
    timeout: int,
    session: Optional[requests.Session],
    max_codes: int,
    page_size: int = 20,
    max_pages: int = 30,
) -> List[str]:
    # 初回HTML + UpdateGridのページングからICコードを収集する。
    codes = _extract_ic_codes(html, max_codes=max_codes)
    if len(codes) >= max_codes:
        return codes

    cgid = _extract_category_id(category_url)
    if not cgid:
        return codes

    client = session or requests.Session()
    seen = set(codes)

    for page_idx in range(1, max_pages + 1):
        start = page_idx * page_size
        response = client.get(
            DOSPARA_UPDATE_GRID_URL,
            params={"cgid": cgid, "start": start, "sz": page_size},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()

        found_any = False
        for code in _extract_ic_codes(response.text, max_codes=page_size * 2):
            if code in seen:
                continue
            seen.add(code)
            codes.append(code)
            found_any = True
            if len(codes) >= max_codes:
                return codes

        # 新規コードがなければ末尾到達とみなして終了。
        if not found_any:
            break

    return codes


def _build_product_info_key(code: str, pname: str = "", kflg: str = "") -> str:
    return quote(f"pid:{code},q:{pname},kflg:{kflg}")


def _fetch_products_by_codes(
    codes: List[str],
    api_url: str,
    headers: Dict[str, str],
    timeout: int,
    batch_size: int,
    session: Optional[requests.Session],
) -> Dict[str, Dict]:
    client = session or requests.Session()
    product_info: Dict[str, Dict] = {}
    if not codes:
        return product_info

    step = max(1, int(batch_size or 1))
    for idx in range(0, len(codes), step):
        chunk = codes[idx: idx + step]
        payload = {
            "paramList": [{"pid": code, "q": "", "kflg": ""} for code in chunk],
        }
        response = client.post(api_url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        api_map = data.get("productInfoList", {}) if isinstance(data, dict) else {}

        for code in chunk:
            value = api_map.get(_build_product_info_key(code))
            if isinstance(value, dict) and value:
                product_info[code] = value

    return product_info


def _extract_specs_from_simplespec(part_type: str, simplespec: str) -> Dict:
    """simplespec テキストからパーツ種別ごとのスペック情報を抽出する。"""
    specs: Dict = {}
    if not simplespec:
        return specs
    text = simplespec

    # ソケット: CPU と マザーボード
    if part_type in ("cpu", "motherboard"):
        m = re.search(r"ソケット形状[：:\s]\s*([^●<\n]+?)(?:●|<|$)", text)
        if m:
            socket = re.sub(r"\s+", "", m.group(1).strip())
            socket = re.sub(r"^Socket", "", socket, flags=re.IGNORECASE)
            specs["socket"] = socket

    # CPU: コア数・スレッド数・ブーストクロック・TDP
    if part_type == "cpu":
        m = re.search(r"TDP[：:]\s*(\d+)W", text)
        if m:
            specs["tdp_w"] = int(m.group(1))
        m = re.search(r"コア数[：:]\s*(\d+)", text)
        if m:
            specs["core_count"] = int(m.group(1))
        m = re.search(r"スレッド数[：:]\s*(\d+)", text)
        if m:
            specs["thread_count"] = int(m.group(1))
        m = re.search(r"(?:最大クロック|ブーストクロック|Turbo\s*Boost)[：:]\s*([\d.]+)\s*GHz", text, re.IGNORECASE)
        if m:
            specs["boost_clock_ghz"] = float(m.group(1))

    # GPU: VRAM容量・VRAM規格
    if part_type == "gpu":
        m = re.search(r"(?:グラフィックス)?メモリ容量[：:]\s*(\d+)\s*GB", text, re.IGNORECASE)
        if not m:
            m = re.search(r"\b(\d+)\s*GB\s+(?:GDDR|HBM)", text, re.IGNORECASE)
        if m:
            specs["vram_gb"] = int(m.group(1))
        m = re.search(r"(GDDR\d+X?|HBM\d*)", text, re.IGNORECASE)
        if m:
            specs["vram_type"] = m.group(1).upper()

    # メモリ: 規格・容量・動作周波数
    if part_type == "memory":
        m = re.search(r"規格[：:]\s*(DDR\d)", text, re.IGNORECASE)
        if m:
            specs["memory_type"] = m.group(1).upper()
        m = re.search(r"メモリ容量[：:]\s*(\d+)\s*GB", text, re.IGNORECASE)
        if not m:
            m = re.search(r"\b(\d+)\s*GB\b", text)
        if m:
            specs["capacity_gb"] = int(m.group(1))
        m = re.search(r"DDR\d-(\d{4,5})", text, re.IGNORECASE)
        if m:
            specs["speed_mhz"] = int(m.group(1))
        else:
            m = re.search(r"(?:クロック|動作周波数)[：:]\s*(\d{4,5})\s*MHz", text, re.IGNORECASE)
            if m:
                specs["speed_mhz"] = int(m.group(1))

    # 対応メモリ規格・チップセット: マザーボード
    if part_type == "motherboard":
        m = re.search(r"対応メモリ[：:]\s*(DDR\d)", text, re.IGNORECASE)
        if m:
            specs["memory_type"] = m.group(1).upper()
        # チップセット (例: "チップセット：B650" / "Intel B760" など)
        m = re.search(
            r"チップセット[：:\s]\s*([A-Z]\d{2,4}[A-Z0-9]*)",
            text,
            re.IGNORECASE,
        )
        if not m:
            m = re.search(
                r"\b(H610|H670|B550|B650|B650E|B760|X570|X670|X670E|Z690|Z790|Z890|W790|TRX50|WRX90)\b",
                text,
                re.IGNORECASE,
            )
        if m:
            specs["chipset"] = m.group(1).upper()

    # ストレージ: 容量・インターフェース・フォームファクタ
    if part_type == "storage":
        m = re.search(r"容量[：:]\s*(\d+(?:\.\d+)?)\s*(TB|GB)", text, re.IGNORECASE)
        if not m:
            m = re.search(r"\b(\d+(?:\.\d+)?)\s*(TB|GB)\b", text)
        if m:
            val, unit = float(m.group(1)), m.group(2).upper()
            specs["capacity_gb"] = int(val * 1024) if unit == "TB" else int(val)
        if re.search(r"NVMe", text, re.IGNORECASE):
            specs["interface"] = "NVMe"
        elif re.search(r"SATA", text, re.IGNORECASE):
            specs["interface"] = "SATA"
        if re.search(r"M\.2", text, re.IGNORECASE):
            specs["form_factor"] = "M.2"
        elif re.search(r"2\.5\s*(?:インチ|inch)", text, re.IGNORECASE):
            specs["form_factor"] = "2.5inch"
        elif re.search(r"3\.5\s*(?:インチ|inch)", text, re.IGNORECASE):
            specs["form_factor"] = "3.5inch"

    # PSU: 出力ワット数・80PLUS認証ランク
    if part_type == "psu":
        m = re.search(r"統合出力[：:]\s*(\d+)W", text)
        if m:
            specs["wattage"] = int(m.group(1))
        m = re.search(r"80\s*PLUS\s*(Bronze|Silver|Gold|Platinum|Titanium)", text, re.IGNORECASE)
        if m:
            specs["efficiency_grade"] = m.group(1).capitalize()

    # フォームファクタ: マザーボード・ケース
    if part_type in ("motherboard", "case"):
        m = re.search(r"フォームファクタ[：:]\s*([^●<\n]+?)(?:●|<|$)", text)
        if m:
            specs["form_factor"] = m.group(1).strip()

    # ケース: ラジエーター対応サイズ
    if part_type == "case":
        size_tokens = {
            int(token)
            for token in re.findall(r"(?:^|[^\d])(120|140|240|280|360|420)\s*mm", text, re.IGNORECASE)
        }

        # 「最大ラジエーター 360mm」「ラジエーターサイズ: 120/240/360mm」などを拾う
        max_hits = re.findall(
            r"(?:最大[^\n]{0,12}ラジエーター|ラジエーター最大|ラジエーター[^\n]{0,10}最大)[^\d]{0,8}(120|140|240|280|360|420)\s*mm",
            text,
            re.IGNORECASE,
        )
        if max_hits:
            specs["max_radiator_mm"] = max(int(v) for v in max_hits)

        if size_tokens:
            sorted_sizes = sorted(size_tokens)
            specs["radiator_sizes"] = sorted_sizes
            specs["supported_radiators"] = sorted_sizes
            if "max_radiator_mm" not in specs:
                specs["max_radiator_mm"] = max(sorted_sizes)

    return specs


def _build_parts_from_products_map(products_map: Dict[str, Dict], base_url: str, max_items: int) -> List[Dict]:
    collected: List[Dict] = []
    for code, info in products_map.items():
        name = (info.get("pname") or "").strip()
        price = _normalize_price(str(info.get("amttax") or ""))
        relative_url = (info.get("url") or "").strip()
        full_url = urljoin(base_url, relative_url) if relative_url else base_url

        if not name or price is None:
            continue

        part_type = _infer_part_type(name, full_url)
        if not part_type:
            continue

        simplespec = (info.get("simplespec") or "").strip()
        extracted = _extract_specs_from_simplespec(part_type, simplespec)

        part_specs = {
            "source": "dospara",
            "parser": "products_api",
            "code": code,
        }
        part_specs.update(extracted)

        collected.append(
            {
                "part_type": part_type,
                "name": name,
                "price": price,
                "url": full_url,
                "specs": part_specs,
            }
        )

        if len(collected) >= max_items:
            break

    return collected


def _extract_first_text(root, selectors: List[str]) -> str:
    for selector in selectors:
        node = root.select_one(selector)
        if node:
            text = node.get("title") if node.has_attr("title") else node.get_text(" ", strip=True)
            if text:
                return text.strip()
    return ""


def _extract_first_url(root, selectors: List[str], base_url: str) -> str:
    for selector in selectors:
        node = root.select_one(selector)
        if node and node.get("href"):
            return urljoin(base_url, node.get("href").strip())
    return ""


def _extract_price(root, selectors: List[str]) -> Optional[int]:
    for selector in selectors:
        node = root.select_one(selector)
        if not node:
            continue

        data_price = node.get("data-price")
        if data_price:
            normalized = _normalize_price(data_price)
            if normalized is not None:
                return normalized

        text = node.get_text(" ", strip=True)
        for pattern in PRICE_PATTERNS:
            match = pattern.search(text)
            if match:
                normalized = _normalize_price(match.group(1))
                if normalized is not None:
                    return normalized

    blob_text = " ".join(root.stripped_strings)
    for pattern in PRICE_PATTERNS:
        match = pattern.search(blob_text)
        if match:
            normalized = _normalize_price(match.group(1))
            if normalized is not None:
                return normalized

    return None


def _iter_item_roots(soup: BeautifulSoup, selectors: Dict[str, List[str]]):
    seen_nodes = set()
    for selector in selectors.get("item_roots", []):
        for node in soup.select(selector):
            identity = id(node)
            if identity in seen_nodes:
                continue
            seen_nodes.add(identity)
            yield node

    # 設定セレクタで要素が取れないDOMにも対応するフォールバック。
    if not seen_nodes:
        for anchor in soup.select("a[href]"):
            identity = id(anchor)
            if identity in seen_nodes:
                continue
            seen_nodes.add(identity)
            yield anchor


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _extract_with_regex_fallback(html: str, base_url: str, max_items: int, seen: set) -> List[Dict]:
    collected: List[Dict] = []

    for match in PRODUCT_LINK_PATTERN.finditer(html):
        href = (match.group("href") or "").strip()
        name = _strip_tags(match.group("name") or "")
        full_url = urljoin(base_url, href)

        if "dospara.co.jp" not in full_url:
            continue
        if not name or len(name) < 3:
            continue

        window = html[match.end(): match.end() + 400]
        price = None
        for pattern in PRICE_PATTERNS:
            price_match = pattern.search(window)
            if price_match:
                price = _normalize_price(price_match.group(1))
                break
        if price is None:
            continue

        part_type = _infer_part_type(name, full_url)
        if not part_type:
            continue

        key = (part_type, name)
        if key in seen:
            continue
        seen.add(key)

        collected.append(
            {
                "part_type": part_type,
                "name": name,
                "price": price,
                "url": full_url,
                "specs": {"source": "dospara", "parser": "regex_fallback"},
            }
        )

        if len(collected) >= max_items:
            break

    return collected


def parse_dospara_parts_html(
    html: str,
    base_url: str = DOSPARA_PARTS_URL,
    max_items: int = 200,
    selectors: Optional[Dict[str, List[str]]] = None,
) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    selectors = selectors or SCRAPER_SELECTORS

    collected: List[Dict] = []
    seen = set()

    for root in _iter_item_roots(soup, selectors):
        full_url = _extract_first_url(root, selectors.get("link", ["a[href]"]), base_url)
        if "dospara.co.jp" not in full_url:
            continue

        name = _extract_first_text(root, selectors.get("name", ["a[href]"]))
        if not name or len(name) < 3:
            continue

        price = _extract_price(root, selectors.get("price", []))
        if price is None:
            continue

        part_type = _infer_part_type(name, full_url)
        if not part_type:
            continue

        key = (part_type, name)
        if key in seen:
            continue
        seen.add(key)

        collected.append(
            {
                "part_type": part_type,
                "name": name,
                "price": price,
                "url": full_url,
                "specs": {"source": "dospara"},
            }
        )

        if len(collected) >= max_items:
            break

    if not collected:
        collected.extend(_extract_with_regex_fallback(html, base_url, max_items, seen))

    return collected


def scrape_dospara_category_parts(
    timeout: int = 20,
    max_items_per_category: int = 80,
    session: Optional[requests.Session] = None,
) -> List[Dict]:
    """各パーツカテゴリページをスクレイピングしてパーツ一覧を返す。"""
    client = session or requests.Session()
    config = get_dospara_scraper_config()
    all_parts: List[Dict] = []
    seen: set = set()

    for part_type, urls in PART_CATEGORY_URLS.items():
        category_count = 0
        for url in urls:
            if category_count >= max_items_per_category:
                break
            try:
                resp = client.get(url, headers=config["headers"], timeout=timeout)
                resp.raise_for_status()
                codes = _collect_ic_codes_from_category_pages(
                    html=resp.text,
                    category_url=url,
                    headers=config["headers"],
                    timeout=timeout,
                    session=client,
                    max_codes=max_items_per_category * 10,
                )
                products_map = _fetch_products_by_codes(
                    codes=codes,
                    api_url=config["products_api_url"],
                    headers=config["headers"],
                    timeout=timeout,
                    batch_size=config["batch_size"],
                    session=client,
                )
                parts = _build_parts_from_products_map(products_map, url, max_items_per_category)
                for part in parts:
                    if part["part_type"] != part_type:
                        continue
                    key = (part["part_type"], part["name"])
                    if key in seen:
                        continue
                    seen.add(key)
                    all_parts.append(part)
                    category_count += 1
                    if category_count >= max_items_per_category:
                        break
            except Exception as e:
                logger.warning("category_scrape_failed part_type=%s url=%s error=%s", part_type, url, e)

    return all_parts


def scrape_dospara_parts(timeout: int = 20, max_items: int = 200, session: Optional[requests.Session] = None) -> List[Dict]:
    client = session or requests.Session()
    config = get_dospara_scraper_config()
    effective_timeout = timeout if timeout != SCRAPER_DEFAULT_CONFIG["timeout"] else config["timeout"]
    effective_max_items = max_items if max_items != SCRAPER_DEFAULT_CONFIG["max_items"] else config["max_items"]

    response = client.get(config["url"], headers=config["headers"], timeout=effective_timeout)
    response.raise_for_status()
    html = response.text

    codes = _extract_ic_codes(html, max_codes=effective_max_items * 10)
    products_map = _fetch_products_by_codes(
        codes=codes,
        api_url=config["products_api_url"],
        headers=config["headers"],
        timeout=effective_timeout,
        batch_size=config.get("batch_size", SCRAPER_DEFAULT_CONFIG["batch_size"]),
        session=client,
    )
    api_parts = _build_parts_from_products_map(products_map, config["url"], effective_max_items)
    if api_parts:
        return api_parts

    return parse_dospara_parts_html(
        html,
        base_url=config["url"],
        max_items=effective_max_items,
        selectors=config["selectors"],
    )
