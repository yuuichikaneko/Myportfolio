import re
from collections import defaultdict

from rest_framework import viewsets, status
from django.db.models import Min, Max, Avg, Count as DbCount
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from .dospara_scraper import fetch_dospara_market_price_range
from .models import PCPart, Configuration, ScraperStatus
from .serializers import PCPartSerializer, ConfigurationSerializer, ScraperStatusSerializer


PART_ORDER = ['cpu', 'cpu_cooler', 'gpu', 'motherboard', 'memory', 'storage', 'os', 'psu', 'case']
USAGE_POWER_MAP = {
    'gaming': 550,    # ゲーミング: GPU高負荷
    'creator': 500,   # クリエイター: CPU+GPU高負荷
    'business': 350,  # ビジネス: 省電力
    'standard': 400,  # スタンダード: 標準
}

USAGE_BUDGET_WEIGHTS = {
    # ゲーミング: GPU最重視
    'gaming': {
        'cpu': 0.18,
        'cpu_cooler': 0.06,
        'gpu': 0.48,
        'motherboard': 0.09,
        'memory': 0.08,
        'storage': 0.05,
        'os': 0.04,
        'psu': 0.05,
        'case': 0.00,
    },
    # クリエイター: マザボ > メモリ > GPU をより明確化
    'creator': {
        'cpu': 0.17,
        'cpu_cooler': 0.08,
        'gpu': 0.08,
        'motherboard': 0.24,
        'memory': 0.20,
        'storage': 0.10,
        'os': 0.05,
        'psu': 0.06,
        'case': 0.02,
    },
    # ビジネス: CPU中程度、GPU控えめ、信頼性重視
    'business': {
        'cpu': 0.24,
        'cpu_cooler': 0.03,
        'gpu': 0.08,
        'motherboard': 0.15,
        'memory': 0.18,
        'storage': 0.17,
        'os': 0.06,
        'psu': 0.08,
        'case': 0.04,
    },
    # スタンダード: バランス型
    'standard': {
        'cpu': 0.20,
        'cpu_cooler': 0.04,
        'gpu': 0.16,
        'motherboard': 0.14,
        'memory': 0.13,
        'storage': 0.11,
        'os': 0.04,
        'psu': 0.10,
        'case': 0.08,
    },
}

# 高予算帯のクリエイター用途では、GPUを上位帯から選定して
# "フラッグシップ予算なのに中位GPU" になりにくくする。
CREATOR_FLAGSHIP_BUDGET_THRESHOLD = 900000
CREATOR_FLAGSHIP_GPU_BUDGET_CAP = 0.75
CREATOR_GPU_BUDGET_CAP_BY_PRIORITY = {
    'cost': 0.12,
    'spec': 0.16,
    'balanced': 0.14,
}
CREATOR_MOTHERBOARD_FLOOR_BY_PRIORITY = {
    'cost': 0.12,
    'spec': 0.15,
    'balanced': 0.13,
}

CATEGORY_DROP_PRIORITY = ['case', 'storage', 'memory', 'cpu_cooler', 'motherboard', 'psu', 'gpu', 'cpu']

UPGRADE_PRIORITY_BY_USAGE = {
    'gaming':   ['gpu', 'cpu', 'cpu_cooler', 'memory', 'storage', 'motherboard', 'psu', 'case'],
    'creator':  ['cpu', 'motherboard', 'memory', 'gpu', 'storage', 'cpu_cooler', 'psu', 'case'],
    'business': ['cpu', 'memory', 'storage', 'motherboard', 'cpu_cooler', 'psu', 'case'],
    'standard': ['cpu', 'memory', 'storage', 'motherboard', 'cpu_cooler', 'psu', 'case'],
}

# 内蔵GPU(iGPU)使用: ビジネス・スタンダードはdGPU不要
IGPU_USAGES = frozenset({'business', 'standard'})

# GPUウェイト分を他パーツへ再分配した予算配分
IGPU_BUDGET_WEIGHTS = {
    'business': {
        'cpu': 0.25,
        'cpu_cooler': 0.05,
        'motherboard': 0.17,
        'memory': 0.20,
        'storage': 0.17,
        'os': 0.08,
        'psu': 0.08,
        'case': 0.04,
    },
    'standard': {
        'cpu': 0.24,
        'cpu_cooler': 0.06,
        'motherboard': 0.18,
        'memory': 0.18,
        'storage': 0.12,
        'os': 0.06,
        'psu': 0.10,
        'case': 0.08,
    },
}

IGPU_POWER_MAP = {
    'business': 250,
    'standard': 300,
}

UNSUITABLE_KEYWORDS = {
    'cpu': ['グリス', 'cooler', 'クーラー', 'fan', 'ファン'],
    'memory': ['sodimm', 'ノート'],
    'storage': ['microatx', 'mini-itx', 'am5', 'am4', 'lga1700', 'lga1851', 'motherboard', 'マザーボード'],
}

UNSUITABLE_URL_HINTS = {
    'cpu': ['/sbr131/', '/sbr95/'],
    'motherboard': ['/sbr1969/'],
}

COOLER_TYPE_KEYWORDS = {
    'liquid': ['水冷', 'aio', 'liquid', 'radiator', 'ラジエーター', '簡易水冷'],
    'air': ['空冷', 'air', 'tower', 'top flow', 'サイドフロー', 'トップフロー', 'nh-d', 'ak', 'assassin'],
}

COOLING_PROFILE_KEYWORDS = {
    'silent': ['静音', 'silent', 'low noise', 'noctua', 'be quiet'],
    'performance': ['high performance', 'extreme', 'oc', 'overclock', 'ハイパフォーマンス'],
}

CASE_FAN_POLICY_KEYWORDS = {
    'silent': ['静音', 'silent', 'low noise', 'be quiet', 'define', 'p12 pwm pst', 'f12 silent'],
    'airflow': ['airflow', 'mesh', 'high airflow', 'high static pressure', 'p14', '140mm', '200mm', 'front mesh'],
}

CASE_SIZE_KEYWORDS = {
    'mini': ['mini-itx', 'mini itx', 'itx', 'sff', '小型', 'コンパクト', 'mini tower'],
    'mid': ['mid tower', 'ミドルタワー', 'micro-atx', 'micro atx', 'matx', 'atx'],
    'full': ['full tower', 'フルタワー', 'e-atx', 'eatx', 'super tower'],
}

CPU_VENDOR_KEYWORDS = {
    'intel': ['intel', 'core i', 'core ultra', 'pentium', 'celeron', 'xeon'],
    'amd': ['amd', 'ryzen', 'athlon', 'epyc', 'threadripper'],
}

GAMING_SPEC_GPU_KEYWORDS = (
    'rtx',
    'radeon rx',
)

GAMING_CPU_X3D_PATTERN = re.compile(r'\b(?:ryzen\s*[3579]\s*)?\d{4,5}x3d\b', re.IGNORECASE)
UNSTABLE_INTEL_CORE_I_PATTERN = re.compile(r'\bcore\s*i[3579]?[-\s]?(?:13|14)\d{3,4}[a-z]{0,3}\b', re.IGNORECASE)

RADIATOR_SIZE_VALUES = (120, 140, 240, 280, 360, 420)

# 一部ケースはAPIスペックにラジエーター情報がないため、
# 確認済みモデルのみ保守的に補助判定する。
CASE_RADIATOR_HINTS = {
    'the tower 250': {120, 140, 240, 280, 360},
    'tr100': {120, 140, 240, 280, 360},
    # BR72で流通が多いmini系モデル（段階追加）
    'the tower 100': {120, 140},
    'meshroom d': {120, 140, 240, 280},
    'h2 flow': {120, 140, 240},
    'ridge': {120, 140, 240},
    'mood': {120, 140, 240},
    'terra': {120},
    'core v1': {120, 140},
    'node 202': {120},
}


def _is_part_suitable(part_type, part):
    text = f"{part.name} {part.url}".lower()
    for keyword in UNSUITABLE_KEYWORDS.get(part_type, []):
        if keyword in text:
            return False

    # Intel Core i 13/14世代は安定性ポリシー上、常に除外する。
    if part_type == 'cpu' and UNSTABLE_INTEL_CORE_I_PATTERN.search(part.name or ''):
        return False

    url = (part.url or '').lower()
    for hint in UNSUITABLE_URL_HINTS.get(part_type, []):
        if hint in url:
            return False

    return True


def _normalize_cooler_type(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            '空冷': 'air',
            '水冷': 'liquid',
            '指定なし': 'any',
            'なし': 'any',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'air', 'liquid'}:
            return normalized
    return 'any'


def _normalize_radiator_size(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        normalized = normalized.replace('mm', '').replace('ｍｍ', '').strip()
        if normalized in {'120', '240', '360'}:
            return normalized
    return 'any'


def _normalize_cooling_profile(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            '冷却重視': 'performance',
            '静音重視': 'silent',
            'バランス': 'balanced',
            '標準': 'balanced',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'silent', 'performance'}:
            return normalized
    return 'balanced'


def _normalize_case_size(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            'mini': 'mini',
            'mid': 'mid',
            'full': 'full',
            '小型': 'mini',
            'ミニ': 'mini',
            '中型': 'mid',
            'ミドル': 'mid',
            '大型': 'full',
            'フル': 'full',
            '指定なし': 'any',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'mini', 'mid', 'full'}:
            return normalized
    return 'any'


def _normalize_case_fan_policy(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            '自動': 'auto',
            '冷却重視': 'airflow',
            '静音重視': 'silent',
            'バランス': 'auto',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'silent', 'airflow'}:
            return normalized
    return 'auto'


def _normalize_cpu_vendor(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            '指定なし': 'any',
            'なし': 'any',
            'インテル': 'intel',
            'intel': 'intel',
            'amd': 'amd',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'intel', 'amd'}:
            return normalized
    return 'any'


def _normalize_build_priority(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        alias = {
            'コスト重視': 'cost',
            '費用重視': 'cost',
            '性能重視': 'spec',
            'スペック重視': 'spec',
            'バランス': 'balanced',
            '標準': 'balanced',
        }
        normalized = alias.get(normalized, normalized)
        if normalized in {'cost', 'spec'}:
            return normalized
    return 'balanced'


def _normalize_storage_preference(value):
    # メインストレージはSSD固定。'hdd' は受け付けない。
    return 'ssd'


def _normalize_os_edition(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'auto', 'home', 'pro'}:
            return normalized
    return 'auto'


def _resolve_os_edition_by_usage(usage, os_edition):
    if os_edition != 'auto':
        return os_edition

    auto_map = {
        'gaming': 'home',
        'standard': 'home',
        'general': 'home',
        'creator': 'pro',
        'business': 'pro',
        'video_editing': 'pro',
    }
    return auto_map.get(usage, 'home')


def _normalize_custom_budget_weights(value):
    if not isinstance(value, dict):
        return None

    normalized = {}
    total = 0.0
    for part_type in PART_ORDER:
        raw = value.get(part_type)
        if raw in (None, ''):
            normalized[part_type] = 0.0
            continue
        try:
            numeric = float(raw)
        except (TypeError, ValueError):
            return None
        if numeric < 0:
            return None
        normalized[part_type] = numeric
        total += numeric

    if total <= 0:
        return None

    return {part_type: weight / total for part_type, weight in normalized.items()}


def _normalize_optional_storage_part_id(value):
    if value in (None, ''):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _normalize_min_storage_capacity_gb(value):
    if value in (None, ''):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized not in {512, 1024, 2048, 4096}:
        return None
    return normalized


def _normalize_max_motherboard_chipset(value):
    """マザーボードチップセット上限を正規化: 'x870e' / 'x870' / 'x670e' / 'x670' / 'any'"""
    if value in (None, ''):
        return 'any'
    normalized = str(value).lower().strip()
    if normalized in ('x870e', 'x870', 'x670e', 'x670'):
        return normalized
    return 'any'


def _resolve_storage_part_by_id(part_id):
    normalized = _normalize_optional_storage_part_id(part_id)
    if normalized is None:
        return None
    try:
        return PCPart.objects.get(id=normalized, part_type='storage')
    except PCPart.DoesNotExist:
        return None


def _normalize_selection_options(cooler_type, radiator_size, cooling_profile, case_size, case_fan_policy, cpu_vendor, build_priority, os_edition, storage_preference, min_storage_capacity_gb=None, max_motherboard_chipset='any'):
    return {
        'cooler_type': _normalize_cooler_type(cooler_type),
        'radiator_size': _normalize_radiator_size(radiator_size),
        'cooling_profile': _normalize_cooling_profile(cooling_profile),
        'case_size': _normalize_case_size(case_size),
        'case_fan_policy': _normalize_case_fan_policy(case_fan_policy),
        'cpu_vendor': _normalize_cpu_vendor(cpu_vendor),
        'build_priority': _normalize_build_priority(build_priority),
        'os_edition': _normalize_os_edition(os_edition),
        'storage_preference': _normalize_storage_preference(storage_preference),
        'min_storage_capacity_gb': _normalize_min_storage_capacity_gb(min_storage_capacity_gb),
        'max_motherboard_chipset': _normalize_max_motherboard_chipset(max_motherboard_chipset),
    }


def _is_os_edition_match(part, os_edition):
    if os_edition == 'auto':
        return True

    text = f"{part.name} {part.url}".lower()
    if os_edition == 'home':
        return 'home' in text
    if os_edition == 'pro':
        return ' pro ' in f' {text} ' or 'windows 11 pro' in text
    return True


def _is_cpu_cooler_type_match(part, cooler_type):
    if cooler_type == 'any':
        return True

    text = f"{part.name} {part.url}".lower()

    def _has_keyword(keyword):
        if keyword in {'air', 'aio', 'liquid'}:
            return re.search(rf'\b{re.escape(keyword)}\b', text) is not None
        return keyword in text

    for keyword in COOLER_TYPE_KEYWORDS.get(cooler_type, []):
        if _has_keyword(keyword):
            return True
    return False


def _is_cpu_cooler_product(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    specs = getattr(part, 'specs', {}) or {}

    # ケースファン単品/セットをCPUクーラー候補から除外
    if (
        'case fan' in text
        or 'ケースファン' in text
        or 'single fan' in text
        or 'fan kit' in text
        or '2pack' in text
        or '3pack' in text
        or '4pack' in text
        or '2個パック' in text
        or re.search(r'\bcl-f\d', text)
    ):
        return False

    # CPUクーラーらしい明示キーワード
    cooler_hints = (
        'cpu cooler',
        'cpuクーラー',
        'air cooler',
        'aio',
        'liquid cooler',
        '水冷',
        '空冷',
        'heatsink',
        'ヒートシンク',
        'nh-',
        'ak',
        'assassin',
    )
    if any(hint in text for hint in cooler_hints):
        return True

    # 仕様にCPUソケット互換情報があればCPUクーラーとみなす
    socket_keys = ('socket', 'supported_socket', 'supported_sockets', 'socket_support')
    if any(specs.get(key) for key in socket_keys):
        return True

    return False


def _extract_radiator_size_token(text):
    for token in ('120', '240', '360'):
        if f'{token}mm' in text or f'{token} mm' in text or token in text:
            return token
    return None


def _is_radiator_size_match(part, radiator_size):
    if radiator_size == 'any':
        return True
    text = f"{part.name} {part.url}".lower()
    token = _extract_radiator_size_token(text)
    return token == radiator_size


def _cpu_cooler_profile_score(part, cooling_profile, cooler_type):
    text = f"{part.name} {part.url}".lower()
    score = 0

    if cooling_profile == 'silent':
        for keyword in COOLING_PROFILE_KEYWORDS['silent']:
            if keyword in text:
                score += 2
        if cooler_type == 'air':
            score += 1
    elif cooling_profile == 'performance':
        for keyword in COOLING_PROFILE_KEYWORDS['performance']:
            if keyword in text:
                score += 2
        if cooler_type == 'liquid':
            score += 1
        for token in ('240', '280', '360'):
            if token in text:
                score += 1

    return score


def _is_allowed_cpu_cooler_brand(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    return 'noctua' not in text


def _case_fan_policy_score(part, case_fan_policy):
    if case_fan_policy == 'auto':
        return 0

    text = f"{part.name} {part.url}".lower()
    score = 0
    for keyword in CASE_FAN_POLICY_KEYWORDS.get(case_fan_policy, []):
        if keyword in text:
            score += 2

    # 仕様情報がある場合は追加加点
    specs = getattr(part, 'specs', {}) or {}
    max_radiator_mm = _extract_numeric_radiator_size(specs.get('max_radiator_mm'))
    included_fan_count = _extract_numeric_fan_count(specs.get('included_fan_count'))
    supported_fan_count = _extract_numeric_fan_count(specs.get('supported_fan_count'))
    front_fan_slots = _extract_numeric_fan_count(specs.get('front_fan_slots'))
    top_fan_slots = _extract_numeric_fan_count(specs.get('top_fan_slots'))
    rear_fan_slots = _extract_numeric_fan_count(specs.get('rear_fan_slots'))

    # 付属ファンなしケースは方針不一致として強く減点
    if included_fan_count == 0:
        score -= 6
    elif included_fan_count is None:
        if any(keyword in text for keyword in ('ファン非搭載', 'ファンなし', 'ファン別売', 'fanless', 'without fan')):
            score -= 6

    # 同梱ファン数を優先評価
    if included_fan_count is not None:
        if included_fan_count >= 4:
            score += 5
        elif included_fan_count == 3:
            score += 4
        elif included_fan_count == 2:
            score += 2
        elif included_fan_count == 1:
            score += 1

    # 搭載可能ファン数は冷却重視でより強く評価
    if supported_fan_count is not None:
        if case_fan_policy == 'airflow':
            if supported_fan_count >= 10:
                score += 5
            elif supported_fan_count >= 8:
                score += 4
            elif supported_fan_count >= 6:
                score += 3
            elif supported_fan_count >= 4:
                score += 1
        elif case_fan_policy == 'silent':
            if supported_fan_count >= 7:
                score += 2
            elif supported_fan_count >= 5:
                score += 1

    # 前面/上面/背面スロットがある場合は airflow を段階的に強化
    if case_fan_policy == 'airflow':
        weighted_slots = (
            (front_fan_slots or 0) * 1.8
            + (top_fan_slots or 0) * 1.3
            + (rear_fan_slots or 0) * 1.0
        )
        if weighted_slots >= 10:
            score += 6
        elif weighted_slots >= 7:
            score += 4
        elif weighted_slots >= 5:
            score += 2

        if (front_fan_slots or 0) >= 3:
            score += 3
        elif (front_fan_slots or 0) >= 2:
            score += 1

        if (top_fan_slots or 0) >= 3:
            score += 2
        elif (top_fan_slots or 0) >= 2:
            score += 1

        if (rear_fan_slots or 0) >= 1:
            score += 1
    elif case_fan_policy == 'silent':
        # 静音重視は最低限の吸排気を評価し、過多なトップ排気は軽く抑制
        if (front_fan_slots or 0) >= 2:
            score += 1
        if (rear_fan_slots or 0) >= 1:
            score += 1
        if (top_fan_slots or 0) >= 4:
            score -= 1

    if case_fan_policy == 'airflow' and max_radiator_mm:
        if max_radiator_mm >= 360:
            score += 2
        elif max_radiator_mm >= 240:
            score += 1

    return score


def _is_case_size_match(part, case_size):
    if case_size == 'any':
        return True

    text = f"{part.name} {part.url}".lower()
    is_mini = any(keyword in text for keyword in CASE_SIZE_KEYWORDS['mini'])
    is_full = any(keyword in text for keyword in CASE_SIZE_KEYWORDS['full'])

    if case_size == 'mini':
        return is_mini
    if case_size == 'full':
        return is_full

    # midはATX系を含めるが、mini/fullと明示されるものは除外する。
    if case_size == 'mid':
        is_mid_keyword = any(keyword in text for keyword in CASE_SIZE_KEYWORDS['mid'])
        return is_mid_keyword and not is_mini and not is_full

    return False


def _is_cpu_vendor_match(part, cpu_vendor):
    if cpu_vendor == 'any':
        return True
    text = f"{part.name} {part.url}".lower()
    return any(keyword in text for keyword in CPU_VENDOR_KEYWORDS.get(cpu_vendor, []))


def _is_gt_series_gpu(part):
    text = f"{part.name} {part.url}".lower()
    return re.search(r'\bgt[\s\-_/]*\d{3,4}\b', text) is not None


def _is_nvidia_gpu(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    return any(keyword in text for keyword in ('nvidia', 'geforce', 'rtx', 'quadro'))


def _prefer_creator_gpu_with_vram_flex(candidates):
    """creator用途: NVIDIA優先。ただし同等以上VRAMのAMDは候補として許容する。"""
    if not candidates:
        return candidates

    nvidia_candidates = [p for p in candidates if _is_nvidia_gpu(p)]
    if not nvidia_candidates:
        return candidates

    nvidia_max_vram = max((_infer_gpu_memory_gb(p) for p in nvidia_candidates), default=0)
    if nvidia_max_vram <= 0:
        return nvidia_candidates

    amd_same_vram_candidates = [
        p for p in candidates
        if not _is_nvidia_gpu(p) and _infer_gpu_memory_gb(p) >= nvidia_max_vram
    ]
    if not amd_same_vram_candidates:
        return nvidia_candidates

    allowed_ids = {p.id for p in (nvidia_candidates + amd_same_vram_candidates)}
    # 呼び出し側の並び順（安い順/高い順）を維持する。
    return [p for p in candidates if p.id in allowed_ids]


def _creator_motherboard_expandability_score(part):
    specs = getattr(part, 'specs', {}) or {}
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()

    score = 0

    form_factor = _infer_motherboard_form_factor(part)
    form_factor_score = {
        'eatx': 45,
        'atx': 35,
        'micro-atx': 20,
        'mini-itx': 8,
    }
    score += form_factor_score.get(form_factor, 10)

    chipset = _infer_motherboard_chipset(part)
    chipset_score = {
        'x870e': 20,
        'x870': 16,
        'x670e': 14,
        'x670': 10,
    }
    score += chipset_score.get(chipset, 0)

    # specs が疎なデータセットでも動くよう、URL/名称ヒントを併用する。
    if any(kw in text for kw in ('creator', 'proart', 'aorus master', 'taichi', 'steel legend', 'tomahawk', 'rog strix')):
        score += 8
    if any(kw in text for kw in ('gaming x', 'aorus', 'tuf')):
        score += 4

    usb_like_keys = ('usb_total', 'usb_ports', 'rear_usb_ports', 'usb3_ports', 'usb2_ports', 'type_c_ports')
    pcie_like_keys = ('pcie_slots', 'pcie_x16_slots', 'm2_slots', 'm_2_slots')
    for key in usb_like_keys + pcie_like_keys:
        value = specs.get(key)
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = 0
        score += min(max(numeric, 0), 12)

    return score


def _pick_creator_preferred_motherboard(candidates):
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda p: (
            _creator_motherboard_expandability_score(p),
            -p.price,
        ),
        reverse=True,
    )[0]


def _infer_gpu_memory_gb(part):
    try:
        memory_gb = int(_get_spec(part, 'memory_gb', 0) or 0)
    except (TypeError, ValueError):
        memory_gb = 0
    if memory_gb > 0:
        return memory_gb

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    match = re.search(r'(\d+)\s*gb', text)
    if match:
        return int(match.group(1))
    return 0


def _gaming_spec_gpu_tier(part):
    text = f"{part.name} {part.url}".lower()
    memory_gb = _infer_gpu_memory_gb(part)

    # 最低限のゲーム向け: RTX 3050 6GBクラス
    if 'rtx 3050' in text and memory_gb >= 6:
        return 1

    # もう一段上の下限: RTX 5050 / RX 7600 クラス以上
    upper_mid_keywords = (
        'rtx 5050',
        'rtx 5060',
        'rtx 5060 ti',
        'rtx 5070',
        'rtx 5070 ti',
        'rtx 5080',
        'rtx 5090',
        'rx 7600',
        'rx7600',
        'rx 9060',
        'rx9060',
        'rx 9070',
        'rx9070',
    )
    if any(keyword in text for keyword in upper_mid_keywords):
        return 2 if memory_gb >= 8 else 1

    if any(keyword in text for keyword in GAMING_SPEC_GPU_KEYWORDS) or re.search(r'\brx\s*\d{3,4}\b', text):
        if memory_gb >= 8:
            return 2
        if memory_gb >= 6:
            return 1
        return 0

    return 0


def _minimum_gaming_spec_gpu_tier(budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return 0
    if budget >= 200000:
        return 2
    return 1


def _creator_gpu_tier(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    memory_gb = _infer_gpu_memory_gb(part)

    if any(keyword in text for keyword in ('rtx 5090', 'rtx 5080', 'rtx 5070 ti', 'rtx 4090', 'rtx 4080')):
        return 3
    if any(keyword in text for keyword in ('rtx 5070', 'rtx 5060 ti', 'rtx 4070', 'rtx 4060 ti')):
        return 2
    if any(keyword in text for keyword in ('rtx 5060', 'rtx 4060', 'rtx 3060')):
        return 1
    if 'rtx 3050' in text and memory_gb >= 6:
        return 1
    return 0


def _minimum_creator_gpu_tier(budget, options=None):
    options = options or {}
    build_priority = options.get('build_priority', 'balanced')

    if build_priority == 'spec':
        if budget >= 350000:
            return 2
        return 1

    # cost でも、クリエイター用途は最低限の CUDA クラスを維持する。
    if budget >= 180000:
        return 1
    return 0


def _creator_gpu_cap_price(budget, options=None):
    options = options or {}
    build_priority = options.get('build_priority', 'balanced')
    cap_ratio = CREATOR_GPU_BUDGET_CAP_BY_PRIORITY.get(build_priority, CREATOR_GPU_BUDGET_CAP_BY_PRIORITY['balanced'])
    return int(budget * cap_ratio)


def _creator_motherboard_floor_price(budget, options=None):
    options = options or {}
    build_priority = options.get('build_priority', 'balanced')
    floor_ratio = CREATOR_MOTHERBOARD_FLOOR_BY_PRIORITY.get(build_priority, CREATOR_MOTHERBOARD_FLOOR_BY_PRIORITY['balanced'])
    return int(budget * floor_ratio)


def _infer_rx_model_and_variant(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    model_match = re.search(r'\brx\s*(\d{4})', text)
    if not model_match:
        return None, ''

    model = model_match.group(1)
    variant = 'xt' if re.search(r'\brx\s*\d{4}\s*xt\b|\brx\d{4}xt\b', text) else 'base'
    return model, variant


def _prefer_rx_xt_value_candidates(candidates):
    if not candidates:
        return candidates

    cheapest_xt_by_model = {}
    for part in candidates:
        model, variant = _infer_rx_model_and_variant(part)
        if not model or variant != 'xt':
            continue
        cheapest = cheapest_xt_by_model.get(model)
        if cheapest is None or part.price < cheapest.price:
            cheapest_xt_by_model[model] = part

    filtered = []
    for part in candidates:
        model, variant = _infer_rx_model_and_variant(part)
        if not model or variant != 'base':
            filtered.append(part)
            continue

        xt = cheapest_xt_by_model.get(model)
        if xt and xt.price <= part.price:
            # 同型番でXTが同価格以下なら、価値の低い非XTは候補から外す。
            continue
        filtered.append(part)

    return filtered or candidates


def _is_gaming_spec_gpu_preferred(part, minimum_tier=1):
    if _gaming_spec_gpu_tier(part) >= minimum_tier:
        return True

    return False


def _infer_gaming_gpu_perf_score(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    score_rules = (
        (r'rtx\s*5090', 1200),
        (r'rtx\s*5080', 1050),
        (r'rtx\s*5070\s*ti', 900),
        (r'rx\s*9070\s*xt|rx9070xt', 860),
        (r'rtx\s*5070', 820),
        (r'rx\s*9070(?!\s*xt)|rx9070(?!xt)', 780),
        (r'rtx\s*5060\s*ti', 730),
        (r'rx\s*9060\s*xt|rx9060xt', 720),
        (r'rtx\s*5060', 660),
        (r'rtx\s*5050', 620),
        (r'rx\s*7600|rx7600', 610),
        (r'rtx\s*3050', 420),
        (r'rx\s*6400|rx6400', 360),
    )
    for pattern, score in score_rules:
        if re.search(pattern, text):
            return score
    return 500


def _pick_gaming_spec_gpu(candidates):
    if not candidates:
        return None

    # ゲーミング・スペック重視: 価格最大ではなく性能優先で選ぶ。
    # 同程度の性能なら安価な方を優先し、価格逆転に強くする。
    ranked = _prefer_rx_xt_value_candidates(candidates)
    return sorted(
        ranked,
        key=lambda p: (
            _infer_gaming_gpu_perf_score(p),
            -p.price,
        ),
        reverse=True,
    )[0]


def _is_gaming_cpu_x3d_preferred(part):
    text = f"{part.name} {part.url}".lower()
    if 'ryzen' not in text and 'amd' not in text:
        return False
    return GAMING_CPU_X3D_PATTERN.search(text) is not None


def _is_cpu_x3d(part):
    """CPU が X3D モデルかどうかを判定する"""
    if not part:
        return False
    text = f"{part.name} {part.url}".lower()
    return GAMING_CPU_X3D_PATTERN.search(text) is not None


def _extract_cpu_core_threads(part):
    """CPU の総スレッド数(コア数 × 2 相当)を抽出する。未入力の場合は 0"""
    if not part:
        return 0
    try:
        core_count = int(_get_spec(part, 'core_count', 0) or 0)
        thread_count = int(_get_spec(part, 'thread_count', 0) or 0)
    except (TypeError, ValueError):
        core_count = 0
        thread_count = 0
    # スレッド数が優先、なければコア数×2の推定を使う
    if thread_count > 0:
        return thread_count
    if core_count > 0:
        return core_count * 2
    return 0


def _extract_cpu_core_count(part):
    """CPU のコア数を抽出する。未入力・変換不可は 0"""
    if not part:
        return 0
    try:
        return int(_get_spec(part, 'core_count', 0) or 0)
    except (TypeError, ValueError):
        return 0


def _is_high_heat_cpu(part):
    """高発熱CPU を判定する（TDP >= 140W またはスペック情報から推定）"""
    if not part:
        return False
    try:
        tdp_w = int(_get_spec(part, 'tdp_w', 0) or 0)
    except (TypeError, ValueError):
        tdp_w = 0
    # TDP >= 140W の場合、または X3D CPU（通常発熱が高い）
    return tdp_w >= 140 or _is_cpu_x3d(part)


def _is_liquid_cooler(part):
    """液冷クーラーかどうかを判定する"""
    if not part:
        return False
    text = f"{part.name} {part.url}".lower()
    return any(kw in text for kw in ['liquid', 'aio', '水冷', 'cooler master ml', 'asus rog strix'])


def _is_dual_tower_cooler(part):
    """ツインタワー空冷クーラーかどうかを判定する"""
    if not part:
        return False
    text = f"{part.name} {part.url}".lower()
    # ツインタワーの一般的なキーワード: dual tower, twin tower, 2タワー
    return any(kw in text for kw in ['dual tower', 'twin tower', '2tower', 'tower cooler', 'noctua nh-d15'])


def _prefer_creator_cpu_by_core_threads(candidates):
    """クリエイター用途: 最小要件コア数を満たす最安値CPUを選ぶ（X3D は完全に除外）"""
    if not candidates:
        return None
    # X3D を除外
    non_x3d_candidates = [p for p in candidates if not _is_cpu_x3d(p)]
    if not non_x3d_candidates:
        # X3D のみの場合は警告の上、非X3D を優先（ログには出力しない）
        non_x3d_candidates = candidates
    
    # 最小要件: 8コア以上（Ryzen 7相当）
    min_cores = 8
    qualified_cpus = [p for p in non_x3d_candidates 
                      if (_get_spec(p, 'core_count', 0) or 0) >= min_cores]
    
    # 条件を満たすCPUがあれば、その中から最安値を選ぶ
    if qualified_cpus:
        return sorted(qualified_cpus, key=lambda p: p.price)[0]
    
    # 条件を満たすCPUがない場合は、コアスレッド数優先で選定
    return sorted(
        non_x3d_candidates,
        key=lambda p: (
            -_extract_cpu_core_threads(p),    # スレッド数が多い方かな優先
            -(_get_spec(p, 'core_count', 0) or 0),  # コア数が多い方が優先
            p.price,  # 同じスレッド数ならより安い方を選ぶ
        ),
    )[0]


def _prefer_creator_cost_cpu_8_to_24_cores(candidates):
    """creator + cost 用: 8～24コアかつ16スレッド以上を優先し、最安値を選ぶ（X3D除外）"""
    if not candidates:
        return None

    non_x3d_candidates = [p for p in candidates if not _is_cpu_x3d(p)]
    if not non_x3d_candidates:
        non_x3d_candidates = candidates

    min_threads = 16
    in_band = [
        p for p in non_x3d_candidates
        if 8 <= _extract_cpu_core_count(p) <= 24
        and _extract_cpu_core_threads(p) >= min_threads
    ]
    if in_band:
        return sorted(in_band, key=lambda p: p.price)[0]

    # スレッド条件を満たすCPUがない場合のみ、コア帯のみで選ぶ
    in_band_core_only = [
        p for p in non_x3d_candidates
        if 8 <= _extract_cpu_core_count(p) <= 24
    ]
    if in_band_core_only:
        return sorted(
            in_band_core_only,
            key=lambda p: (-_extract_cpu_core_threads(p), p.price),
        )[0]

    # 8～24コアが無い場合のみ既存のcreatorロジックへフォールバック
    return _prefer_creator_cpu_by_core_threads(non_x3d_candidates)


def _extract_numeric_radiator_size(value):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _extract_numeric_fan_count(value):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _extract_case_supported_radiators(part):
    specs = getattr(part, 'specs', {}) or {}
    supported = set()

    for key in ('max_radiator_mm', 'radiator_mm'):
        numeric = _extract_numeric_radiator_size(specs.get(key))
        if numeric:
            supported.add(numeric)

    list_values = specs.get('radiator_sizes') or specs.get('supported_radiators') or []
    if isinstance(list_values, (list, tuple, set)):
        for item in list_values:
            numeric = _extract_numeric_radiator_size(item)
            if numeric:
                supported.add(numeric)

    text = f"{part.name} {part.url}".lower()
    for size in RADIATOR_SIZE_VALUES:
        if f'{size}mm' in text or f'{size} mm' in text:
            supported.add(size)

    for keyword, hint_sizes in CASE_RADIATOR_HINTS.items():
        if keyword in text:
            supported.update(hint_sizes)

    if supported:
        return supported

    # スペック抽出がないケース名向けの保守的フォールバック
    if any(keyword in text for keyword in CASE_SIZE_KEYWORDS['mini']):
        return {120, 140, 240}
    if any(keyword in text for keyword in CASE_SIZE_KEYWORDS['mid']):
        return {120, 140, 240, 280, 360}
    if any(keyword in text for keyword in CASE_SIZE_KEYWORDS['full']):
        return {120, 140, 240, 280, 360, 420}

    return set()


def _is_case_radiator_compatible(part, radiator_size):
    requested = _extract_numeric_radiator_size(radiator_size)
    if not requested:
        return True

    supported = _extract_case_supported_radiators(part)
    if not supported:
        return False
    return any(size >= requested for size in supported)


def _infer_motherboard_form_factor(part):
    """マザーボードのフォームファクターを推定する: 'eatx' / 'atx' / 'micro-atx' / 'mini-itx' / 'unknown'"""
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    form_factor = str(_get_spec(part, 'form_factor', '') or '').lower()
    combined = f"{text} {form_factor}"
    if any(kw in combined for kw in ('e-atx', 'eatx', 'extended atx')):
        return 'eatx'
    if any(kw in combined for kw in ('mini-itx', 'mini itx', 'mitx')):
        return 'mini-itx'
    if any(kw in combined for kw in ('micro-atx', 'micro atx', 'microatx', 'matx', 'm-atx')):
        return 'micro-atx'
    if 'atx' in combined:
        return 'atx'
    return 'unknown'


def _preferred_motherboard_form_factors(case_size):
    if case_size == 'full':
        return ('eatx', 'atx')
    if case_size == 'mid':
        return ('atx', 'eatx')
    if case_size == 'mini':
        return ('mini-itx',)
    return tuple()


def _infer_motherboard_chipset(part):
    """マザーボードのチップセットを推定する: 'x870e' / 'x870' / 'x670e' / 'x670' / 'unknown'"""
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    chipset = str(_get_spec(part, 'chipset', '') or '').lower()
    combined = f"{text} {chipset}"
    
    if any(kw in combined for kw in ('x870e', 'x870-e')):
        return 'x870e'
    if 'x870' in combined:
        return 'x870'
    if any(kw in combined for kw in ('x670e', 'x670-e')):
        return 'x670e'
    if 'x670' in combined:
        return 'x670'
    return 'unknown'


def _prefer_motherboard_candidates(candidates, case_size):
    preferred_form_factors = _preferred_motherboard_form_factors(case_size)
    if not preferred_form_factors:
        return candidates

    preferred_candidates = [
        part for part in candidates
        if _infer_motherboard_form_factor(part) in preferred_form_factors
    ]
    return preferred_candidates or candidates


def _infer_cpu_power_w(part):
    if not part:
        return 0

    try:
        tdp_w = int(_get_spec(part, 'tdp_w', 0) or 0)
    except (TypeError, ValueError):
        tdp_w = 0
    if tdp_w > 0:
        return tdp_w

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    for watts in (170, 125, 105, 95, 65, 35):
        if f'{watts}w' in text:
            return watts
    return 95


GPU_POWER_RULES = (
    (r'rtx\s*5090', 575),
    (r'rtx\s*5080', 360),
    (r'rtx\s*5070\s*ti', 300),
    (r'rtx\s*5070', 250),
    (r'rtx\s*5060\s*ti', 180),
    (r'rtx\s*5060', 150),
    (r'rtx\s*5050', 130),
    (r'rtx\s*3050', 70),
    (r'rx\s*9070\s*xt', 320),
    (r'rx\s*9070', 260),
    (r'rx\s*9060\s*xt', 190),
    (r'rx\s*6400', 55),
    (r'arc\s*b580', 190),
    (r'arc\s*b570', 150),
    (r'arc\s*a310', 50),
)


def _infer_gpu_power_w(part):
    if not part:
        return 0

    try:
        tdp_w = int(_get_spec(part, 'tdp_w', 0) or 0)
    except (TypeError, ValueError):
        tdp_w = 0
    if tdp_w > 0:
        return tdp_w

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    for pattern, watts in GPU_POWER_RULES:
        if re.search(pattern, text):
            return watts

    return 180


def _estimate_system_power_w(selected_parts, usage):
    cpu = selected_parts.get('cpu')
    gpu = selected_parts.get('gpu')
    cpu_cooler = selected_parts.get('cpu_cooler')
    motherboard = selected_parts.get('motherboard')
    memory = selected_parts.get('memory')
    storage_parts = [selected_parts.get('storage')]
    for key in ('storage2', 'storage3'):
        if selected_parts.get(key):
            storage_parts.append(selected_parts.get(key))

    cpu_power = _infer_cpu_power_w(cpu)
    gpu_power = _infer_gpu_power_w(gpu)
    motherboard_power = 45 if motherboard else 0
    memory_power = 10 if memory else 0

    storage_power = 0
    for storage_part in storage_parts:
        if not storage_part:
            continue
        media_type = _infer_storage_media_type(storage_part)
        storage_power += 12 if media_type == 'hdd' else 6

    cooler_text = f"{getattr(cpu_cooler, 'name', '')} {getattr(cpu_cooler, 'url', '')}".lower()
    if cpu_cooler:
        cooler_power = 20 if any(token in cooler_text for token in ('水冷', 'aio', '360', '280', '240')) else 8
    else:
        cooler_power = 0

    case_power = 10 if selected_parts.get('case') else 0

    estimated = cpu_power + gpu_power + motherboard_power + memory_power + storage_power + cooler_power + case_power
    if estimated <= 0:
        return IGPU_POWER_MAP.get(usage, USAGE_POWER_MAP.get(usage, 300)) if usage in IGPU_USAGES else USAGE_POWER_MAP.get(usage, 400)
    return estimated


def _recommended_psu_floor_w(selected_parts, usage):
    gpu_power = _infer_gpu_power_w(selected_parts.get('gpu'))
    cpu_power = _infer_cpu_power_w(selected_parts.get('cpu'))

    if gpu_power >= 550:
        return 1200
    if gpu_power >= 350:
        return 1000
    if gpu_power >= 300:
        return 850
    if gpu_power >= 250:
        return 850
    if gpu_power >= 180:
        return 750
    if cpu_power >= 170:
        return 750
    if gpu_power > 0 or cpu_power > 0:
        return 650
    return 0


def _required_psu_wattage(selected_parts, usage):
    estimated = _estimate_system_power_w(selected_parts, usage)
    cpu_gpu_total = _infer_cpu_power_w(selected_parts.get('cpu')) + _infer_gpu_power_w(selected_parts.get('gpu'))
    required = max(
        int(estimated * 1.25),
        estimated + 100,
        cpu_gpu_total + 100,
        _recommended_psu_floor_w(selected_parts, usage),
    )
    return int(((required + 49) // 50) * 50)


def _infer_psu_wattage_w(part):
    if not part:
        return 0
    try:
        return int(_get_spec(part, 'wattage', 0) or 0)
    except (TypeError, ValueError):
        return 0


def _psu_selection_sort_key(part, required_wattage):
    wattage = _infer_psu_wattage_w(part)
    if required_wattage is None:
        return (part.price, 0 if wattage > 0 else 1)

    headroom = max(0, wattage - int(required_wattage)) if wattage > 0 else 10_000
    # まず価格最小を優先し、同価格帯では必要Wに近いものを選ぶ。
    return (part.price, headroom)


def _psu_headroom_cap_w(required_wattage, usage=None, build_priority=None):
    if required_wattage is None:
        return None

    try:
        required = int(required_wattage)
    except (TypeError, ValueError):
        return None

    # ゲーミング・スペック重視は過剰容量を抑え、その他は少し広めに許容する。
    margin = 200 if usage == 'gaming' and build_priority == 'spec' else 300
    return required + margin


def _filter_psu_candidates_by_headroom(candidates, required_wattage, usage=None, build_priority=None):
    if required_wattage is None:
        return candidates

    max_allowed = _psu_headroom_cap_w(required_wattage, usage=usage, build_priority=build_priority)
    if max_allowed is None:
        return candidates

    bounded = [p for p in candidates if _infer_psu_wattage_w(p) <= max_allowed]
    return bounded or candidates


def _rightsize_psu_after_selection(selected_parts, usage, options=None):
    options = options or {}
    current_psu = selected_parts.get('psu')
    if not current_psu:
        return selected_parts

    required_w = _required_psu_wattage(selected_parts, usage)
    psu_options = dict(options)
    psu_options['required_psu_wattage'] = required_w

    candidates = [
        p
        for p in PCPart.objects.filter(part_type='psu').order_by('price')
        if _is_part_suitable('psu', p) and _matches_selection_options('psu', p, options=psu_options)
    ]
    candidates = _filter_psu_candidates_by_headroom(
        candidates,
        required_w,
        usage=options.get('usage', usage),
        build_priority=options.get('build_priority'),
    )
    if not candidates:
        return selected_parts

    best_fit = sorted(candidates, key=lambda p: _psu_selection_sort_key(p, required_w))[0]
    if best_fit.id == current_psu.id:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['psu'] = best_fit
    return adjusted


def _pick_part_by_target(part_type, budget, usage, weights_override=None, options=None):
    options = options or {}
    cooler_type = options.get('cooler_type', 'any')
    radiator_size = options.get('radiator_size', 'any')
    cooling_profile = options.get('cooling_profile', 'balanced')
    case_size = options.get('case_size', 'any')
    case_fan_policy = options.get('case_fan_policy', 'auto')
    cpu_vendor = options.get('cpu_vendor', 'any')
    build_priority = options.get('build_priority', 'balanced')
    storage_preference = options.get('storage_preference', 'ssd')
    required_psu_wattage = options.get('required_psu_wattage')
    minimum_gaming_gpu_tier = options.get('minimum_gaming_gpu_tier', 1)
    motherboard_memory_type = str(options.get('motherboard_memory_type', '') or '').upper()
    min_storage_capacity_gb = options.get('min_storage_capacity_gb')

    candidates = [p for p in PCPart.objects.filter(part_type=part_type).order_by('price') if _is_part_suitable(part_type, p)]
    if part_type == 'gpu':
        candidates = [p for p in candidates if not _is_gt_series_gpu(p)]
    if part_type == 'cpu_cooler':
        candidates = [
            p for p in candidates
            if _is_cpu_cooler_product(p)
            and _is_cpu_cooler_type_match(p, cooler_type)
            and _is_allowed_cpu_cooler_brand(p)
        ]
        if cooler_type == 'liquid' and radiator_size != 'any':
            radiator_filtered = [p for p in candidates if _is_radiator_size_match(p, radiator_size)]
            if radiator_filtered:
                candidates = radiator_filtered
    elif part_type == 'case':
        size_filtered = [p for p in candidates if _is_case_size_match(p, case_size)]
        if size_filtered:
            candidates = size_filtered
        if cooler_type == 'liquid' and radiator_size != 'any':
            radiator_filtered = [p for p in candidates if _is_case_radiator_compatible(p, radiator_size)]
            if radiator_filtered:
                candidates = radiator_filtered
    elif part_type == 'cpu':
        vendor_filtered = [p for p in candidates if _is_cpu_vendor_match(p, cpu_vendor)]
        if vendor_filtered:
            candidates = vendor_filtered
    elif part_type == 'motherboard':
        cpu_socket = options.get('cpu_socket')
        if cpu_socket:
            socket_filtered = [p for p in candidates if _get_spec(p, 'socket') == cpu_socket]
            if socket_filtered:
                candidates = socket_filtered
        max_chipset = options.get('max_motherboard_chipset', 'any')
        if max_chipset != 'any':
            if max_chipset == 'x870':
                chipset_filtered = [p for p in candidates if _infer_motherboard_chipset(p) != 'x870e']
            elif max_chipset == 'x670':
                chipset_filtered = [p for p in candidates if _infer_motherboard_chipset(p) not in ('x870e', 'x870', 'x670e')]
            else:
                chipset_filtered = candidates
            if chipset_filtered:
                candidates = chipset_filtered

        if usage == 'creator':
            motherboard_floor = _creator_motherboard_floor_price(budget, options=options)
            floor_filtered = [p for p in candidates if p.price >= motherboard_floor]
            if floor_filtered:
                candidates = floor_filtered

        candidates = _prefer_motherboard_candidates(candidates, case_size)
    elif part_type == 'memory':
        if motherboard_memory_type:
            mem_type_filtered = [
                p for p in candidates
                if _infer_memory_type(p) == motherboard_memory_type
            ]
            if mem_type_filtered:
                candidates = mem_type_filtered
    elif part_type == 'storage':
        if min_storage_capacity_gb:
            capacity_filtered = [
                p for p in candidates
                if _infer_storage_capacity_gb(p) >= int(min_storage_capacity_gb)
            ]
            if capacity_filtered:
                candidates = capacity_filtered
    elif part_type == 'psu':
        if required_psu_wattage is not None:
            psu_filtered = [
                p for p in candidates
                if _infer_psu_wattage_w(p) >= int(required_psu_wattage)
            ]
            if psu_filtered:
                candidates = psu_filtered
            candidates = _filter_psu_candidates_by_headroom(
                candidates,
                required_psu_wattage,
                usage=usage,
                build_priority=build_priority,
            )

    if part_type == 'gpu' and usage == 'gaming' and build_priority == 'spec':
        preferred_gpu = [p for p in candidates if _is_gaming_spec_gpu_preferred(p, minimum_gaming_gpu_tier)]
        if preferred_gpu:
            candidates = preferred_gpu
        candidates = _prefer_rx_xt_value_candidates(candidates)

    if part_type == 'gpu' and usage == 'creator':
        # クリエイター用途は NVIDIA 優先。ただし同等以上VRAMのAMDは許容。
        candidates = _prefer_creator_gpu_with_vram_flex(candidates)

        creator_gpu_cap = _creator_gpu_cap_price(budget, options=options)
        capped_candidates = [p for p in candidates if p.price <= creator_gpu_cap]
        if capped_candidates:
            candidates = capped_candidates

        minimum_creator_tier = _minimum_creator_gpu_tier(budget, options=options)
        if minimum_creator_tier > 0:
            tier_filtered = [p for p in candidates if _creator_gpu_tier(p) >= minimum_creator_tier]
            if tier_filtered:
                candidates = tier_filtered

    if not candidates:
        return None

    if (
        usage == 'creator'
        and part_type == 'gpu'
        and budget >= CREATOR_FLAGSHIP_BUDGET_THRESHOLD
    ):
        # 予算上限75%以内で買えるGPUのうち、最上位価格を選ぶ。
        # これにより、クリエイターの高予算ではGPUを積極的に上位化する。
        upper_cap = int(budget * CREATOR_FLAGSHIP_GPU_BUDGET_CAP)
        premium_candidates = [p for p in candidates if p.price <= upper_cap]
        if premium_candidates:
            return premium_candidates[-1]

    weights = weights_override if weights_override is not None else USAGE_BUDGET_WEIGHTS[usage]
    target_price = int(budget * weights.get(part_type, 0.1))
    if part_type == 'cpu_cooler':
        if cooling_profile == 'performance':
            target_price = int(target_price * 1.3)
        elif cooling_profile == 'silent':
            target_price = int(target_price * 0.85)

    within_target = [p for p in candidates if p.price <= target_price]
    if within_target:
        if part_type == 'gpu' and usage == 'gaming' and build_priority == 'spec':
            picked_gpu = _pick_gaming_spec_gpu(within_target)
            if picked_gpu:
                return picked_gpu
        if part_type == 'psu':
            # PSU は過剰容量・過剰価格より、必要W数に近い候補を優先する。
            return sorted(
                within_target,
                key=lambda p: _psu_selection_sort_key(p, required_psu_wattage),
            )[0]
        if part_type == 'cpu' and usage == 'gaming' and cpu_vendor != 'intel':
            preferred_x3d = [p for p in within_target if _is_gaming_cpu_x3d_preferred(p)]
            if preferred_x3d:
                within_target = preferred_x3d
        if part_type == 'cpu' and usage == 'creator':
            # クリエイター用途: コアスレッド数が多いCPUを優先選定
            # within_target が空の場合は candidates 全体から選定
            target_cpus = within_target if within_target else candidates
            if build_priority == 'cost':
                picked_creator_cpu = _prefer_creator_cost_cpu_8_to_24_cores(target_cpus)
            else:
                picked_creator_cpu = _prefer_creator_cpu_by_core_threads(target_cpus)
            if picked_creator_cpu:
                return picked_creator_cpu
        if part_type == 'memory':
            # gaming + spec はGPU優先のため、メモリは目標価格内から選ぶ。
            # それ以外の spec では、候補全体から上位メモリを選んでもよい。
            if build_priority == 'spec' and usage != 'gaming':
                memory_pool = candidates
            else:
                memory_pool = within_target
            profiled = _memory_profile_pick(memory_pool, build_priority, budget=budget, usage=usage, options=options)
            if usage == 'creator':
                min_capacity_candidates = [p for p in candidates if _infer_memory_capacity_gb(p) >= 16]
                if min_capacity_candidates:
                    candidates = min_capacity_candidates
            if profiled:
                return profiled
        if part_type == 'motherboard' and usage == 'creator':
            picked_mb = _pick_creator_preferred_motherboard(within_target)
            if picked_mb:
                return picked_mb
        if part_type == 'storage':
            # スペック重視では目標価格内の安価HDDに固定されやすいため、
            # 候補全体からSSD/NVMe優先で選ぶ。
            storage_pool = candidates if build_priority == 'spec' else within_target
            profiled = _storage_profile_pick(storage_pool, build_priority, storage_preference)
            if profiled:
                return profiled
        if build_priority == 'spec' and part_type == 'motherboard':
            return candidates[-1]
        if part_type == 'case' and case_fan_policy != 'auto':
            if build_priority == 'cost':
                return sorted(
                    within_target,
                    key=lambda p: (-_case_fan_policy_score(p, case_fan_policy), p.price),
                )[0]
            return sorted(
                within_target,
                key=lambda p: (_case_fan_policy_score(p, case_fan_policy), p.price),
                reverse=True,
            )[0]
        if part_type == 'case' and case_fan_policy == 'auto':
            # 自動時はケース価格を抑え、GPU/CPUへ予算を回す。
            return within_target[0]
        if build_priority == 'cost':
            return within_target[0]
        if part_type == 'cpu_cooler':
            # creator 用途: 水冷またはツインタワー空冷を優先
            if usage == 'creator':
                # 水冷クーラーを最優先
                liquid_coolers = [p for p in within_target if _is_liquid_cooler(p)]
                if liquid_coolers:
                    return sorted(
                        liquid_coolers,
                        key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), p.price),
                        reverse=True,
                    )[0]
                # 水冷がなければツインタワー空冷を優先
                dual_tower_coolers = [p for p in within_target if _is_dual_tower_cooler(p)]
                if dual_tower_coolers:
                    return sorted(
                        dual_tower_coolers,
                        key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), p.price),
                        reverse=True,
                    )[0]
            return sorted(
                within_target,
                key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), p.price),
                reverse=True,
            )[0]
        return sorted(within_target, key=lambda p: p.price, reverse=True)[0]

    if build_priority == 'cost':
        if part_type == 'cpu' and usage == 'gaming' and cpu_vendor != 'intel':
            preferred_x3d = [p for p in candidates if _is_gaming_cpu_x3d_preferred(p)]
            if preferred_x3d:
                return preferred_x3d[0]
        if part_type == 'cpu' and usage == 'creator':
            # クリエイター用途 + コスト重視: 8～24コア帯を優先
            picked_creator_cpu = _prefer_creator_cost_cpu_8_to_24_cores(candidates)
            if picked_creator_cpu:
                return picked_creator_cpu
        if part_type == 'memory':
            profiled = _memory_profile_pick(candidates, build_priority, budget=budget, usage=usage, options=options)
            if profiled:
                return profiled
        if part_type == 'motherboard' and usage == 'creator':
            picked_mb = _pick_creator_preferred_motherboard(candidates)
            if picked_mb:
                return picked_mb
        if part_type == 'storage':
            profiled = _storage_profile_pick(candidates, build_priority, storage_preference)
            if profiled:
                return profiled
        if part_type == 'case' and case_fan_policy != 'auto':
            return sorted(
                candidates,
                key=lambda p: (-_case_fan_policy_score(p, case_fan_policy), p.price),
            )[0]
        return candidates[0]

    if part_type == 'cpu_cooler':
        if build_priority == 'spec':
            return sorted(
                candidates,
                key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), p.price),
                reverse=True,
            )[0]
        return sorted(
            candidates,
            key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), -p.price),
            reverse=True,
        )[0]

    if part_type == 'case':
        if case_fan_policy != 'auto':
            if build_priority == 'cost':
                return sorted(
                    candidates,
                    key=lambda p: (-_case_fan_policy_score(p, case_fan_policy), p.price),
                )[0]
            return sorted(
                candidates,
                key=lambda p: (_case_fan_policy_score(p, case_fan_policy), p.price),
                reverse=True,
            )[0]
        return candidates[0]

    if part_type == 'psu':
        return sorted(
            candidates,
            key=lambda p: _psu_selection_sort_key(p, required_psu_wattage),
        )[0]

    if part_type == 'memory' and build_priority == 'spec':
        profiled = _memory_profile_pick(candidates, build_priority, budget=budget, usage=usage, options=options)
        if profiled:
            return profiled

    if part_type == 'storage':
        profiled = _storage_profile_pick(candidates, build_priority, storage_preference)
        if profiled:
            return profiled

    if part_type == 'cpu' and usage == 'gaming' and cpu_vendor != 'intel':
        preferred_x3d = [p for p in candidates if _is_gaming_cpu_x3d_preferred(p)]
        if preferred_x3d:
            return preferred_x3d[-1] if build_priority == 'spec' else preferred_x3d[0]

    if part_type == 'cpu' and usage == 'creator':
        # クリエイター用途: 目標価格を超えた候補からもコアスレッド数で優先
        # 注: クーラー条件によって候補が制限されている場合でも、creator CPU ロジックを適用
        if build_priority == 'cost':
            picked_creator_cpu = _prefer_creator_cost_cpu_8_to_24_cores(candidates)
        else:
            picked_creator_cpu = _prefer_creator_cpu_by_core_threads(candidates)
        if picked_creator_cpu:
            return picked_creator_cpu
        # それでも candidates が空の場合は、制限を緩和して再試行
        # (例: 空冷・水冷のどちらでも互換性のある CPU から選定)
        if not candidates and part_type == 'cpu':
            # cooler_type と radiator_size を無視して全 CPU 候補から選定
            all_creator_cpus = PCPart.objects.filter(part_type='cpu').order_by('price')
            if all_creator_cpus:
                if build_priority == 'cost':
                    return _prefer_creator_cost_cpu_8_to_24_cores(list(all_creator_cpus))
                return _prefer_creator_cpu_by_core_threads(list(all_creator_cpus))

    if part_type == 'gpu' and usage == 'gaming' and build_priority == 'spec':
        picked_gpu = _pick_gaming_spec_gpu(candidates)
        if picked_gpu:
            return picked_gpu

    if build_priority == 'spec':
        return candidates[-1]

    return candidates[0]


def _get_spec(part, key, default=None):
    if not part:
        return default
    specs = getattr(part, 'specs', {}) or {}
    return specs.get(key, default)


def _infer_memory_type(part):
    memory_type = str(_get_spec(part, 'memory_type', '') or '').upper()
    if memory_type in {'DDR4', 'DDR5'}:
        return memory_type

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".upper()
    if 'DDR5' in text:
        return 'DDR5'
    if 'DDR4' in text:
        return 'DDR4'
    return ''


def _infer_memory_capacity_gb(part):
    try:
        capacity = int(_get_spec(part, 'capacity_gb', 0) or 0)
    except (TypeError, ValueError):
        capacity = 0
    if capacity > 0:
        return capacity

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".upper()

    kit_match = re.search(r'(\d+)\s*GB\s*[X×*]\s*(\d+)', text)
    if kit_match:
        return int(kit_match.group(1)) * int(kit_match.group(2))

    pair_match = re.search(r'(\d+)\s*GB[^\d]{0,12}(\d+)\s*枚組', text)
    if pair_match:
        return int(pair_match.group(1)) * int(pair_match.group(2))

    single_match = re.search(r'(\d+)\s*GB', text)
    if single_match:
        return int(single_match.group(1))

    return 0


def _infer_memory_speed_mhz(part):
    try:
        speed = int(_get_spec(part, 'speed_mhz', 0) or 0)
    except (TypeError, ValueError):
        speed = 0
    if speed > 0:
        return speed

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".upper()

    pc5_match = re.search(r'PC5-(\d{5})', text)
    if pc5_match:
        return int(int(pc5_match.group(1)) / 8)

    pc4_match = re.search(r'PC4-(\d{5})', text)
    if pc4_match:
        return int(int(pc4_match.group(1)) / 8)

    mhz_match = re.search(r'(\d{4,5})\s*MHZ', text)
    if mhz_match:
        return int(mhz_match.group(1))

    return 0


def _infer_memory_module_count(part):
    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".upper()

    kit_match = re.search(r'(\d+)\s*GB\s*[X×*]\s*(\d+)', text)
    if kit_match:
        return int(kit_match.group(2))

    pair_match = re.search(r'(\d+)\s*GB[^\d]{0,12}(\d+)\s*枚組', text)
    if pair_match:
        return int(pair_match.group(2))

    return 1


def _infer_motherboard_memory_type(part):
    memory_type = str(_get_spec(part, 'memory_type', '') or '').upper()
    if memory_type in {'DDR4', 'DDR5'}:
        return memory_type

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".upper()
    if 'DDR5' in text:
        return 'DDR5'
    if 'DDR4' in text:
        return 'DDR4'

    # 規格が欠損している場合の保守的推定
    socket = str(_get_spec(part, 'socket', '') or '').upper()
    if socket == 'AM5':
        return 'DDR5'
    if socket == 'AM4':
        return 'DDR4'

    chipset = str(_get_spec(part, 'chipset', '') or '').upper()
    ddr4_chipsets = {'A320', 'A520', 'B450', 'B550', 'X470', 'X570'}
    ddr5_chipsets = {'A620', 'B650', 'B650E', 'X670', 'X670E', 'B850', 'X870', 'X870E'}
    if chipset in ddr4_chipsets:
        return 'DDR4'
    if chipset in ddr5_chipsets:
        return 'DDR5'

    # 名前/URLからのフォールバック推定
    if 'AM5' in text:
        return 'DDR5'
    if 'AM4' in text:
        return 'DDR4'

    if any(token in text for token in ddr5_chipsets):
        return 'DDR5'
    if any(token in text for token in ddr4_chipsets):
        return 'DDR4'

    return ''


def _minimum_memory_speed_for_selected_cpu(cpu_part, usage, options=None):
    options = options or {}
    if not cpu_part or usage != 'gaming':
        return None

    text = f"{getattr(cpu_part, 'name', '')} {getattr(cpu_part, 'url', '')}".lower()
    if '9850x3d' in text:
        return 5600

    return None


def _target_memory_profile(budget, usage, options=None):
    options = options or {}
    build_priority = options.get('build_priority')

    if usage == 'creator':
        if budget >= 500000:
            return {'capacity_gb': 64, 'preferred_modules': 2}
        if budget >= 250000:
            return {'capacity_gb': 32, 'preferred_modules': 2}
        return {'capacity_gb': 16, 'preferred_modules': 2}

    if usage == 'gaming':
        if build_priority == 'spec':
            if budget >= 500000:
                return {'capacity_gb': 64, 'preferred_modules': 2}
            if budget >= 280000:
                return {'capacity_gb': 32, 'preferred_modules': 2}
            return {'capacity_gb': 16, 'preferred_modules': 1}
        if budget >= 400000:
            return {'capacity_gb': 32, 'preferred_modules': 2}
        return {'capacity_gb': 16, 'preferred_modules': 2}

    if usage in {'business', 'standard'}:
        if budget >= 300000 or build_priority == 'spec':
            return {'capacity_gb': 32, 'preferred_modules': 2}
        return {'capacity_gb': 16, 'preferred_modules': 1}

    return {'capacity_gb': 16, 'preferred_modules': 1}


def _memory_profile_pick(candidates, build_priority, budget=None, usage=None, options=None):
    if not candidates:
        return None

    options = options or {}
    target_profile = _target_memory_profile(budget or 0, usage or options.get('usage', 'standard'), options=options)
    target_capacity = target_profile['capacity_gb']
    preferred_modules = target_profile['preferred_modules']

    def _normalized_memory_type(part):
        return _infer_memory_type(part)

    def _capacity_gb(part):
        return _infer_memory_capacity_gb(part)

    def _module_count(part):
        return _infer_memory_module_count(part)

    min_memory_speed_mhz = options.get('min_memory_speed_mhz')
    if min_memory_speed_mhz:
        speed_filtered = [p for p in candidates if _infer_memory_speed_mhz(p) >= int(min_memory_speed_mhz)]
        if speed_filtered:
            candidates = speed_filtered

    if build_priority == 'cost':
        creator_min_capacity_gb = 16 if (usage or options.get('usage')) == 'creator' else 0
        # コスト重視: DDR4優先 + 小容量優先 + 同条件なら安価なもの
        return sorted(
            candidates,
            key=lambda p: (
                _capacity_gb(p) < creator_min_capacity_gb,
                _normalized_memory_type(p) != 'DDR4',
                _capacity_gb(p) > 16,
                _infer_memory_speed_mhz(p) < int(min_memory_speed_mhz or 0),
                _capacity_gb(p),
                p.price,
            ),
        )[0]

    if build_priority == 'spec':
        # スペック重視: DDR5優先 + 予算帯ごとの容量/枚数ルール優先
        return sorted(
            candidates,
            key=lambda p: (
                _normalized_memory_type(p) == 'DDR5',
                _capacity_gb(p) >= target_capacity,
                _infer_memory_speed_mhz(p) >= int(min_memory_speed_mhz or 0),
                -abs(_capacity_gb(p) - target_capacity),
                _module_count(p) == preferred_modules,
                _capacity_gb(p),
                -p.price,
            ),
            reverse=True,
        )[0]

    return None


def _target_memory_capacity_gb(budget, usage, options=None):
    return _target_memory_profile(budget, usage, options=options)['capacity_gb']


def _upgrade_memory_to_capacity_target(selected_parts, total_price, budget, usage, options=None):
    options = options or {}
    memory = selected_parts.get('memory')
    if not memory:
        return selected_parts, total_price

    current_capacity = _infer_memory_capacity_gb(memory)
    target_capacity = _target_memory_capacity_gb(budget, usage, options=options)
    if current_capacity >= target_capacity:
        return selected_parts, total_price

    affordable_max_price = memory.price + max(0, budget - total_price)
    if affordable_max_price <= memory.price:
        return selected_parts, total_price

    candidates = [
        p
        for p in PCPart.objects.filter(part_type='memory').order_by('price')
        if _is_part_suitable('memory', p)
        and _matches_selection_options('memory', p, options=options)
        and memory.price < p.price <= affordable_max_price
        and _infer_memory_capacity_gb(p) >= target_capacity
    ]
    if not candidates:
        return selected_parts, total_price

    upgraded_memory = sorted(
        candidates,
        key=lambda p: (
            _infer_memory_capacity_gb(p) == target_capacity,
            _infer_memory_module_count(p) == _target_memory_profile(budget, usage, options=options)['preferred_modules'],
            _infer_memory_type(p) == 'DDR5',
            -_infer_memory_capacity_gb(p),
            -p.price,
        ),
        reverse=True,
    )[0]

    adjusted = dict(selected_parts)
    adjusted['memory'] = upgraded_memory
    return adjusted, _sum_selected_price(adjusted)


def _infer_storage_capacity_gb(part):
    capacity = int(_get_spec(part, 'capacity_gb', 0) or 0)
    if capacity > 0:
        return capacity

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}"
    # TB単位を優先して検索し、モデル番号埋め込み (例: "F20GB") を除外するため負の後読みを使用
    tb_match = re.search(r'(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*TB', text, re.IGNORECASE)
    if tb_match:
        return int(float(tb_match.group(1)) * 1024)
    gb_match = re.search(r'(?<![A-Za-z0-9])(\d+(?:\.\d+)?)\s*GB', text, re.IGNORECASE)
    if gb_match:
        return int(float(gb_match.group(1)))
    return 0


def _infer_storage_media_type(part):
    media_type = str(_get_spec(part, 'media_type', '') or '').strip().lower()
    if media_type in {'ssd', 'hdd'}:
        return media_type

    name_text = str(getattr(part, 'name', '') or '').lower()
    form_factor = str(_get_spec(part, 'form_factor', '') or '').strip().lower()
    interface = _infer_storage_interface(part)

    if interface == 'nvme':
        return 'ssd'
    # SSD キーワード・フォームファクター・名前中の M.2
    if 'ssd' in name_text or form_factor in {'m.2', '2.5inch'}:
        return 'ssd'
    if 'm.2' in name_text:
        return 'ssd'
    # WD SSD モデル番号 (SA500=SATA, SN500/580/700/750/850=NVMe)
    if re.search(r'\b(sa500|sn500|sn580|sn700|sn750|sn850)\b', name_text):
        return 'ssd'
    if re.search(r'(5400|7200|10000|15000)\s*rpm', name_text, re.IGNORECASE):
        return 'hdd'

    # HDD キーワードは "wd red" 単体を除外し "wd red wd" 等の HDDのみに絞る
    hdd_keywords = (
        'barracuda',
        'ironwolf',
        'wd blue wd',
        'wd green wd',
        'wd red wd',
        'wd purple wd',
        'mq04',
        'dt02',
        'n300',
        'mg10',
        'mg11',
        'hat3300',
        'hdd',
    )
    if any(keyword in name_text for keyword in hdd_keywords):
        return 'hdd'
    if interface == 'sata' and form_factor == '3.5inch':
        return 'hdd'
    if interface == 'sata' and form_factor in {'2.5inch', 'm.2'}:
        return 'ssd'
    return 'other'


def _storage_profile_pick(candidates, build_priority, storage_preference='ssd'):
    if not candidates:
        return None

    # メインストレージはHDD不可。SSD候補が存在する場合は必ずSSDを選ぶ。
    ssd_candidates = [p for p in candidates if _infer_storage_media_type(p) != 'hdd']
    if ssd_candidates:
        candidates = ssd_candidates

    prefer_hdd = False  # storage_preference == 'hdd' は廃止

    def _media_rank(part):
        media_type = _infer_storage_media_type(part)
        if media_type == ('hdd' if prefer_hdd else 'ssd'):
            return 0
        if media_type == ('ssd' if prefer_hdd else 'hdd'):
            return 1
        if media_type == 'other':
            return 2
        return 3

    def _interface_rank(part):
        interface = _infer_storage_interface(part)
        if interface == 'nvme':
            return 0
        if interface == 'sata':
            return 1
        return 2

    def _capacity(part):
        return _infer_storage_capacity_gb(part)

    if build_priority == 'cost':
        return sorted(
            candidates,
            key=lambda p: (
                _media_rank(p),
                p.price,
                _interface_rank(p),
                -_capacity(p),
            ),
        )[0]

    if build_priority == 'spec':
        # スペック重視: SSD > HDD、NVMe > SATA を最優先。
        # 同一メディア・インターフェース階層内では 1TB+ を優先し、最安値を選ぶ。
        # 最高価格を選ぶと予算を大幅超過してダウングレードループが起きHDDが残るため。
        return sorted(
            candidates,
            key=lambda p: (
                _media_rank(p),
                _interface_rank(p),
                0 if _capacity(p) >= 1000 else 1,
                p.price,
            ),
        )[0]

    return sorted(
        candidates,
        key=lambda p: (
            _media_rank(p),
            _interface_rank(p),
            0 if _capacity(p) >= 1000 else 1,
            -_capacity(p),
            p.price,
        ),
    )[0]


def _required_power_w(usage):
    if usage in IGPU_USAGES:
        return int(IGPU_POWER_MAP.get(usage, 300) * 1.2)
    return int(USAGE_POWER_MAP.get(usage, 400) * 1.2)


def _compatibility_issues(selected_parts, usage, options=None):
    options = options or {}
    issues = []

    cpu = selected_parts.get('cpu')
    motherboard = selected_parts.get('motherboard')
    memory = selected_parts.get('memory')
    psu = selected_parts.get('psu')
    case = selected_parts.get('case')
    gpu = selected_parts.get('gpu')
    cpu_cooler = selected_parts.get('cpu_cooler')

    cooler_type = options.get('cooler_type', 'any')
    radiator_size = options.get('radiator_size', 'any')

    cpu_socket = _get_spec(cpu, 'socket')
    mb_socket = _get_spec(motherboard, 'socket')
    if cpu and motherboard and cpu_socket and mb_socket and cpu_socket != mb_socket:
        issues.append('socket_mismatch')

    mb_mem_type = _infer_motherboard_memory_type(motherboard)
    mem_type = _infer_memory_type(memory)
    if motherboard and memory and mb_mem_type and mem_type and mb_mem_type != mem_type:
        issues.append('memory_type_mismatch')

    psu_watt = _get_spec(psu, 'wattage')
    required_psu_wattage = options.get('required_psu_wattage') or _required_psu_wattage(selected_parts, usage)
    if psu and psu_watt:
        if int(psu_watt) < int(required_psu_wattage):
            issues.append('psu_too_weak')

    mb_form = _get_spec(motherboard, 'form_factor')
    case_forms = _get_spec(case, 'supported_form_factors', [])
    if motherboard and case and mb_form and case_forms and mb_form not in case_forms:
        issues.append('form_factor_mismatch')

    gpu_len = _get_spec(gpu, 'gpu_length_mm')
    max_gpu_len = _get_spec(case, 'max_gpu_length_mm')
    if gpu and case and gpu_len and max_gpu_len and int(gpu_len) > int(max_gpu_len):
        issues.append('gpu_too_long')

    if cpu_cooler and case and cooler_type == 'liquid' and radiator_size != 'any':
        if not _is_case_radiator_compatible(case, radiator_size):
            issues.append('radiator_not_supported')

    return issues


def _pick_candidate(part_type, predicate):
    for candidate in PCPart.objects.filter(part_type=part_type).order_by('price'):
        if _is_part_suitable(part_type, candidate) and predicate(candidate):
            return candidate
    return None


def _matches_selection_options(part_type, part, options=None):
    options = options or {}
    cooler_type = options.get('cooler_type', 'any')
    radiator_size = options.get('radiator_size', 'any')
    case_size = options.get('case_size', 'any')
    cpu_vendor = options.get('cpu_vendor', 'any')
    os_edition = options.get('os_edition', 'auto')
    motherboard_memory_type = str(options.get('motherboard_memory_type', '') or '').upper()
    min_memory_speed_mhz = options.get('min_memory_speed_mhz')
    min_storage_capacity_gb = options.get('min_storage_capacity_gb')
    require_preferred_gaming_gpu = options.get('require_preferred_gaming_gpu', False)
    minimum_gaming_gpu_tier = options.get('minimum_gaming_gpu_tier', 1)
    required_psu_wattage = options.get('required_psu_wattage')

    if part_type == 'cpu_cooler':
        if not _is_cpu_cooler_product(part):
            return False
        if not _is_cpu_cooler_type_match(part, cooler_type):
            return False
        if not _is_allowed_cpu_cooler_brand(part):
            return False
        if cooler_type == 'liquid' and radiator_size != 'any' and not _is_radiator_size_match(part, radiator_size):
            return False
        return True

    if part_type == 'case':
        if not _is_case_size_match(part, case_size):
            return False
        if cooler_type == 'liquid' and radiator_size != 'any' and not _is_case_radiator_compatible(part, radiator_size):
            return False
        return True

    if part_type == 'cpu':
        return _is_cpu_vendor_match(part, cpu_vendor)

    if part_type == 'gpu':
        if require_preferred_gaming_gpu and not _is_gaming_spec_gpu_preferred(part, minimum_gaming_gpu_tier):
            return False
        return not _is_gt_series_gpu(part)

    if part_type == 'motherboard':
        cpu_socket = options.get('cpu_socket')
        if cpu_socket:
            mb_socket = _get_spec(part, 'socket')
            if mb_socket and mb_socket != cpu_socket:
                return False
        max_chipset = options.get('max_motherboard_chipset', 'any')
        if max_chipset != 'any':
            chipset = _infer_motherboard_chipset(part)
            if max_chipset == 'x870' and chipset == 'x870e':
                return False
            if max_chipset == 'x670' and chipset in ('x870e', 'x870', 'x670e'):
                return False
        current_case_size = options.get('case_size', 'any')
        preferred_form_factors = _preferred_motherboard_form_factors(current_case_size)
        if preferred_form_factors:
            available_candidates = [
                candidate for candidate in PCPart.objects.filter(part_type='motherboard')
                if _is_part_suitable('motherboard', candidate)
                and (not cpu_socket or _get_spec(candidate, 'socket') == cpu_socket)
                and _infer_motherboard_form_factor(candidate) in preferred_form_factors
            ]
            if available_candidates and _infer_motherboard_form_factor(part) not in preferred_form_factors:
                return False
        return True

    if part_type == 'memory':
        if motherboard_memory_type:
            mem_type = _infer_memory_type(part)
            if mem_type and mem_type != motherboard_memory_type:
                return False
        if min_memory_speed_mhz and _infer_memory_speed_mhz(part) < int(min_memory_speed_mhz):
            return False
        return True

    if part_type == 'storage':
        if min_storage_capacity_gb:
            capacity_gb = _infer_storage_capacity_gb(part)
            if capacity_gb < int(min_storage_capacity_gb):
                return False
        return True

    if part_type == 'psu':
        if required_psu_wattage is None:
            return True
        try:
            wattage = int(_get_spec(part, 'wattage', 0) or 0)
        except (TypeError, ValueError):
            wattage = 0
        return wattage >= int(required_psu_wattage)

    if part_type == 'os':
        return _is_os_edition_match(part, os_edition)

    return True


def _resolve_compatibility(selected_parts, usage, options=None):
    options = options or {}
    case_size = options.get('case_size', 'any')
    for _ in range(10):
        issues = _compatibility_issues(selected_parts, usage, options=options)
        if not issues:
            return selected_parts

        issue = issues[0]
        cpu = selected_parts.get('cpu')
        motherboard = selected_parts.get('motherboard')
        memory = selected_parts.get('memory')

        if issue == 'socket_mismatch':
            cpu_socket = _get_spec(cpu, 'socket')
            mb_socket = _get_spec(motherboard, 'socket')
            replaced = False
            if cpu_socket:
                motherboard_candidates = [
                    candidate for candidate in PCPart.objects.filter(part_type='motherboard').order_by('price')
                    if _is_part_suitable('motherboard', candidate) and _get_spec(candidate, 'socket') == cpu_socket
                ]
                motherboard_candidates = _prefer_motherboard_candidates(motherboard_candidates, case_size)
                new_mb = motherboard_candidates[0] if motherboard_candidates else None
                if new_mb:
                    selected_parts['motherboard'] = new_mb
                    replaced = True
            if not replaced and mb_socket:
                new_cpu = _pick_candidate('cpu', lambda p: _get_spec(p, 'socket') == mb_socket)
                if new_cpu:
                    selected_parts['cpu'] = new_cpu
                    replaced = True
            if not replaced:
                break

        elif issue == 'memory_type_mismatch':
            mb_mem_type = _infer_motherboard_memory_type(motherboard)
            mem_type = _infer_memory_type(memory)
            # まずメモリをマザーボードの規格に合わせて変更
            if mb_mem_type:
                new_mem = _pick_candidate('memory', lambda p: _infer_memory_type(p) == mb_mem_type)
                if new_mem:
                    selected_parts['memory'] = new_mem
                    continue
            # マザーボードに対応するメモリが存在しなければ、マザーボードをメモリ規格に合わせて変更
            if mem_type:
                cpu_socket = _get_spec(cpu, 'socket') if cpu else None
                def _mb_fits_mem(p, _mem_type=mem_type, _cpu_socket=cpu_socket):
                    if _infer_motherboard_memory_type(p) != _mem_type:
                        return False
                    p_socket = _get_spec(p, 'socket')
                    if _cpu_socket and p_socket and p_socket != _cpu_socket:
                        return False
                    return True
                motherboard_candidates = [
                    candidate for candidate in PCPart.objects.filter(part_type='motherboard').order_by('price')
                    if _is_part_suitable('motherboard', candidate) and _mb_fits_mem(candidate)
                ]
                motherboard_candidates = _prefer_motherboard_candidates(motherboard_candidates, case_size)
                new_mb = motherboard_candidates[0] if motherboard_candidates else None
                if new_mb:
                    selected_parts['motherboard'] = new_mb
                else:
                    break
            else:
                break

        elif issue == 'psu_too_weak':
            required_w = options.get('required_psu_wattage') or _required_psu_wattage(selected_parts, usage)
            psu_candidates = [
                p
                for p in PCPart.objects.filter(part_type='psu').order_by('price')
                if _is_part_suitable('psu', p)
                and int(_get_spec(p, 'wattage', 0) or 0) >= int(required_w)
            ]
            psu_candidates = _filter_psu_candidates_by_headroom(
                psu_candidates,
                required_w,
                usage=options.get('usage', usage),
                build_priority=options.get('build_priority'),
            )
            new_psu = psu_candidates[0] if psu_candidates else None
            if new_psu:
                selected_parts['psu'] = new_psu
                options = dict(options)
                options['required_psu_wattage'] = _required_psu_wattage(selected_parts, usage)
            else:
                break

        elif issue == 'form_factor_mismatch':
            mb_form = _get_spec(motherboard, 'form_factor')
            if not mb_form:
                break
            new_case = _pick_candidate(
                'case',
                lambda p: (
                    mb_form in (_get_spec(p, 'supported_form_factors', []) or [])
                    and _is_case_size_match(p, case_size)
                ),
            )
            if new_case:
                selected_parts['case'] = new_case
            else:
                break

        elif issue == 'gpu_too_long':
            gpu = selected_parts.get('gpu')
            gpu_len = _get_spec(gpu, 'gpu_length_mm')
            if not gpu_len:
                break
            new_case = _pick_candidate(
                'case',
                lambda p: (
                    int(_get_spec(p, 'max_gpu_length_mm', 0)) >= int(gpu_len)
                    and _is_case_size_match(p, case_size)
                ),
            )
            if new_case:
                selected_parts['case'] = new_case
            else:
                break

        elif issue == 'radiator_not_supported':
            radiator_size = options.get('radiator_size', 'any')
            preferred_case = _pick_candidate(
                'case',
                lambda p: _is_case_size_match(p, case_size) and _is_case_radiator_compatible(p, radiator_size),
            )
            if preferred_case:
                selected_parts['case'] = preferred_case
                continue

            # 希望サイズに対応ケースがない場合は、ケースサイズ制約を緩和して互換性を優先
            fallback_case = _pick_candidate(
                'case',
                lambda p: _is_case_radiator_compatible(p, radiator_size),
            )
            if fallback_case:
                selected_parts['case'] = fallback_case
            else:
                break

        else:
            break

    return selected_parts


def _downgrade_selected_parts(selected_parts, total_price, budget, options=None):
    if total_price <= budget:
        return selected_parts, total_price

    options = options or {}
    protect_x3d_cpu = options.get('usage') == 'gaming' and options.get('build_priority') == 'spec'

    changed = True
    while changed and total_price > budget:
        changed = False
        for part_type, current in sorted(selected_parts.items(), key=lambda item: item[1].price if item[1] else 0, reverse=True):
            if current is None:
                continue
            if protect_x3d_cpu and part_type == 'cpu' and _is_gaming_cpu_x3d_preferred(current):
                continue

            build_priority = options.get('build_priority', 'balanced')
            cheaper_candidates = [
                c for c in PCPart.objects.filter(part_type=part_type, price__lt=current.price).order_by('-price')
                if _is_part_suitable(part_type, c) and _matches_selection_options(part_type, c, options=options)
            ]
            cheaper = None
            if cheaper_candidates:
                if part_type == 'storage' and build_priority == 'spec':
                    storage_preference = options.get('storage_preference', 'ssd')
                    cheaper = _storage_profile_pick(cheaper_candidates, build_priority, storage_preference) or cheaper_candidates[0]
                elif (
                    part_type == 'gpu'
                    and options.get('usage') == 'gaming'
                    and build_priority == 'spec'
                ):
                    minimum_tier = options.get('minimum_gaming_gpu_tier', 1)
                    preferred_gpu = [c for c in cheaper_candidates if _is_gaming_spec_gpu_preferred(c, minimum_tier)]
                    gpu_pool = preferred_gpu or cheaper_candidates
                    gpu_pool = _prefer_rx_xt_value_candidates(gpu_pool)
                    cheaper = gpu_pool[0]
                else:
                    cheaper = cheaper_candidates[0]
            if cheaper:
                total_price -= (current.price - cheaper.price)
                selected_parts[part_type] = cheaper
                changed = True
                if total_price <= budget:
                    break

    return selected_parts, total_price


def _drop_until_budget(selected_parts, total_price, budget):
    if total_price <= budget:
        return selected_parts, total_price

    for part_type in CATEGORY_DROP_PRIORITY:
        part = selected_parts.get(part_type)
        if part is None:
            continue
        selected_parts[part_type] = None
        total_price -= part.price
        if total_price <= budget:
            break

    return selected_parts, total_price


def _sum_selected_price(selected_parts):
    return sum(part.price for part in selected_parts.values() if part is not None)


def _upgrade_memory_with_surplus(selected_parts, total_price, budget, usage, options=None):
    options = options or {}
    if total_price >= budget:
        return selected_parts, total_price

    if options.get('build_priority') == 'cost':
        return selected_parts, total_price

    memory = selected_parts.get('memory')
    if not memory:
        return selected_parts, total_price

    affordable_max_price = memory.price + (budget - total_price)

    gpu = selected_parts.get('gpu')
    if usage == 'gaming' and options.get('build_priority') == 'spec' and gpu:
        # gaming + spec はGPU優先を維持し、メモリがGPU価格を超えない範囲で増強する。
        affordable_max_price = min(affordable_max_price, gpu.price)

    if affordable_max_price <= memory.price:
        return selected_parts, total_price

    candidates = [
        p
        for p in PCPart.objects.filter(part_type='memory').order_by('price')
        if _is_part_suitable('memory', p)
        and _matches_selection_options('memory', p, options=options)
        and memory.price < p.price <= affordable_max_price
    ]
    if not candidates:
        return selected_parts, total_price

    preferred = _memory_profile_pick(candidates, 'spec', budget=budget, usage=usage, options=options)
    upgraded_memory = preferred or candidates[-1]

    adjusted = dict(selected_parts)
    adjusted['memory'] = upgraded_memory
    return adjusted, _sum_selected_price(adjusted)


def _upgrade_parts_with_surplus(selected_parts, total_price, budget, usage, options=None):
    """余剰予算が大きい場合に優先度順でパーツをアップグレードし、予算を有効活用する。"""
    options = options or {}
    build_priority = options.get('build_priority', 'balanced')

    # cost は「最安」寄りを維持しつつ、予算からの極端な下振れだけ抑える。
    target_budget = budget
    if build_priority == 'cost':
        utilization_floor_by_usage = {
            'gaming': 0.70,
            'creator': 0.92,
            'business': 0.65,
            'standard': 0.65,
        }
        floor_ratio = utilization_floor_by_usage.get(usage, 0.65)
        target_budget = int(budget * floor_ratio)
        if total_price >= target_budget:
            return selected_parts, total_price

    use_igpu = usage in IGPU_USAGES
    upgrade_order = UPGRADE_PRIORITY_BY_USAGE.get(usage, list(PART_ORDER))
    if usage == 'creator':
        # 予算余りの再配分はGPUを最優先にして、体感性能を引き上げる。
        upgrade_order = ['gpu'] + [p for p in upgrade_order if p != 'gpu']

    for _ in range(len(upgrade_order) * 4):
        surplus = target_budget - total_price
        if surplus < 5000:
            break

        upgraded = False
        for part_type in upgrade_order:
            if use_igpu and part_type == 'gpu':
                continue
            if part_type == 'psu' and options.get('build_priority') == 'spec':
                # 余剰予算でPSUを肥大化させない。必要Wの見直しは互換/右サイズ処理に任せる。
                continue
            current = selected_parts.get(part_type)
            if not current:
                continue

            affordable_max = current.price + surplus
            better_candidates = [
                c for c in PCPart.objects.filter(
                    part_type=part_type,
                    price__gt=current.price,
                    price__lte=affordable_max,
                ).order_by('-price')
                if _is_part_suitable(part_type, c) and _matches_selection_options(part_type, c, options=options)
            ]
            if part_type == 'gpu' and usage == 'creator':
                better_candidates = _prefer_creator_gpu_with_vram_flex(better_candidates)
                creator_gpu_cap = _creator_gpu_cap_price(budget, options=options)
                capped_candidates = [c for c in better_candidates if c.price <= creator_gpu_cap]
                if capped_candidates:
                    better_candidates = capped_candidates
            if part_type == 'cpu' and usage == 'creator':
                better_candidates = [c for c in better_candidates if not _is_cpu_x3d(c)]
            better = None
            if better_candidates:
                if part_type == 'storage' and build_priority == 'spec':
                    storage_preference = options.get('storage_preference', 'ssd')
                    better = _storage_profile_pick(better_candidates, build_priority, storage_preference) or better_candidates[0]
                elif (
                    part_type == 'gpu'
                    and options.get('usage') == 'gaming'
                    and build_priority == 'spec'
                ):
                    minimum_tier = options.get('minimum_gaming_gpu_tier', 1)
                    preferred_gpu = [c for c in better_candidates if _is_gaming_spec_gpu_preferred(c, minimum_tier)]
                    gpu_pool = preferred_gpu or better_candidates
                    gpu_pool = _prefer_rx_xt_value_candidates(gpu_pool)
                    better = gpu_pool[0]
                else:
                    better = better_candidates[0]

            if better:
                total_price += better.price - current.price
                selected_parts[part_type] = better
                upgraded = True
                break

        if not upgraded:
            break

    return selected_parts, total_price


def _rebalance_gaming_spec_gpu_memory(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    gpu = selected_parts.get('gpu')
    memory = selected_parts.get('memory')
    if not gpu or not memory:
        return selected_parts

    if gpu.price >= memory.price:
        return selected_parts

    def _gpu_candidates(base_options):
        candidates = [
            p
            for p in PCPart.objects.filter(part_type='gpu').order_by('price')
            if _is_part_suitable('gpu', p) and _matches_selection_options('gpu', p, options=base_options)
        ]
        preferred = [p for p in candidates if _is_gaming_spec_gpu_preferred(p, base_options.get('minimum_gaming_gpu_tier', 1))]
        picked = preferred or candidates
        return _prefer_rx_xt_value_candidates(picked)

    def _memory_candidates(base_options):
        return [
            p
            for p in PCPart.objects.filter(part_type='memory').order_by('price')
            if _is_part_suitable('memory', p) and _matches_selection_options('memory', p, options=base_options)
        ]

    # 1) まずは現行マザーボード前提でGPU/メモリのみ再配分する。
    motherboard = selected_parts.get('motherboard')
    same_mb_options = dict(options)
    if motherboard:
        mb_mem_type = _infer_motherboard_memory_type(motherboard)
        if mb_mem_type:
            same_mb_options['motherboard_memory_type'] = mb_mem_type

    gpu_candidates = _gpu_candidates(same_mb_options)
    memory_candidates = _memory_candidates(same_mb_options)

    if gpu_candidates and memory_candidates:
        total_other = _sum_selected_price(selected_parts) - gpu.price - memory.price
        if total_other < 0:
            total_other = 0

        for gpu_candidate in reversed(gpu_candidates):
            max_memory_price = min(gpu_candidate.price, budget - total_other - gpu_candidate.price)
            if max_memory_price < 0:
                continue

            affordable_memories = [m for m in memory_candidates if m.price <= max_memory_price]
            if not affordable_memories:
                continue

            memory_candidate = affordable_memories[-1]
            rebalanced = dict(selected_parts)
            rebalanced['gpu'] = gpu_candidate
            rebalanced['memory'] = memory_candidate
            return rebalanced

    # 2) それでも成立しない場合、マザーボード+メモリ+GPUを同時に再選定する。
    cpu = selected_parts.get('cpu')
    total_fixed = _sum_selected_price(selected_parts) - gpu.price - memory.price
    if motherboard:
        total_fixed -= motherboard.price
    if total_fixed < 0:
        total_fixed = 0

    motherboard_candidates = [
        p
        for p in PCPart.objects.filter(part_type='motherboard').order_by('price')
        if _is_part_suitable('motherboard', p) and _matches_selection_options('motherboard', p, options=options)
    ]

    if cpu:
        cpu_socket = _get_spec(cpu, 'socket')
        if cpu_socket:
            socket_filtered = [p for p in motherboard_candidates if _get_spec(p, 'socket') == cpu_socket]
            if socket_filtered:
                motherboard_candidates = socket_filtered

    motherboard_candidates = _prefer_motherboard_candidates(motherboard_candidates, options.get('case_size', 'any'))

    for gpu_candidate in reversed(_gpu_candidates(options)):
        for motherboard_candidate in motherboard_candidates:
            mb_mem_type = _infer_motherboard_memory_type(motherboard_candidate)
            mb_options = dict(options)
            if mb_mem_type:
                mb_options['motherboard_memory_type'] = mb_mem_type

            memory_candidates_for_mb = _memory_candidates(mb_options)
            if not memory_candidates_for_mb:
                continue

            max_memory_price = min(
                gpu_candidate.price,
                budget - total_fixed - gpu_candidate.price - motherboard_candidate.price,
            )
            if max_memory_price < 0:
                continue

            affordable_memories = [m for m in memory_candidates_for_mb if m.price <= max_memory_price]
            if not affordable_memories:
                continue

            memory_candidate = affordable_memories[-1]
            rebalanced = dict(selected_parts)
            rebalanced['gpu'] = gpu_candidate
            rebalanced['motherboard'] = motherboard_candidate
            rebalanced['memory'] = memory_candidate
            return rebalanced

    return selected_parts


def _enforce_gaming_spec_gpu_not_lower_than_memory(selected_parts, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    gpu = selected_parts.get('gpu')
    memory = selected_parts.get('memory')
    if not gpu or not memory:
        return selected_parts
    if gpu.price >= memory.price:
        return selected_parts

    memory_candidates = [
        p
        for p in PCPart.objects.filter(part_type='memory').order_by('price')
        if _is_part_suitable('memory', p) and _matches_selection_options('memory', p, options=options)
    ]
    memory_candidates = [p for p in memory_candidates if p.price <= gpu.price]
    if not memory_candidates:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['memory'] = memory_candidates[-1]
    return adjusted


def _enforce_gaming_spec_prefers_rx_xt(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    gpu = selected_parts.get('gpu')
    if not gpu:
        return selected_parts

    text = f"{getattr(gpu, 'name', '')} {getattr(gpu, 'url', '')}".lower()
    model_match = re.search(r'\brx\s*(\d{4})\b', text)
    if not model_match:
        return selected_parts
    if re.search(r'\brx\s*\d{4}\s*xt\b', text):
        return selected_parts

    model = model_match.group(1)
    xt_pattern = re.compile(rf'\brx\s*{model}\s*xt\b', re.IGNORECASE)

    xt_candidates = [
        p
        for p in PCPart.objects.filter(part_type='gpu').order_by('price')
        if _is_part_suitable('gpu', p)
        and _matches_selection_options('gpu', p, options=options)
        and xt_pattern.search(f"{getattr(p, 'name', '')} {getattr(p, 'url', '')}")
    ]
    if not xt_candidates:
        return selected_parts

    total_current = _sum_selected_price(selected_parts)

    # 同価格以下のXTがあれば最優先で置換
    for candidate in xt_candidates:
        if candidate.price <= gpu.price:
            adjusted = dict(selected_parts)
            adjusted['gpu'] = candidate
            return adjusted

    # 少し高くても予算内ならXTへ置換
    for candidate in xt_candidates:
        projected_total = total_current - gpu.price + candidate.price
        if projected_total <= budget:
            adjusted = dict(selected_parts)
            adjusted['gpu'] = candidate
            return adjusted

    return selected_parts


def _enforce_gaming_spec_best_value_gpu(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    current_gpu = selected_parts.get('gpu')
    if not current_gpu:
        return selected_parts

    minimum_tier = options.get('minimum_gaming_gpu_tier', 1)
    total_without_gpu = _sum_selected_price(selected_parts) - current_gpu.price

    affordable_candidates = [
        p
        for p in PCPart.objects.filter(part_type='gpu').order_by('price')
        if _is_part_suitable('gpu', p)
        and _matches_selection_options('gpu', p, options=options)
        and _is_gaming_spec_gpu_preferred(p, minimum_tier)
        and total_without_gpu + p.price <= budget
    ]
    if not affordable_candidates:
        return selected_parts

    best = _pick_gaming_spec_gpu(affordable_candidates)
    if not best or best.id == current_gpu.id:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['gpu'] = best
    return adjusted


def _enforce_gaming_spec_prefers_x3d_cpu(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    cpu = selected_parts.get('cpu')
    if not cpu:
        return selected_parts
    if _is_gaming_cpu_x3d_preferred(cpu):
        return selected_parts

    x3d_candidates = [
        p
        for p in PCPart.objects.filter(part_type='cpu').order_by('price')
        if _is_part_suitable('cpu', p)
        and _is_gaming_cpu_x3d_preferred(p)
        and _matches_selection_options('cpu', p, options=options)
    ]
    if not x3d_candidates:
        return selected_parts

    total_without_cpu = _sum_selected_price(selected_parts) - cpu.price
    affordable = [candidate for candidate in x3d_candidates if total_without_cpu + candidate.price <= budget]
    if affordable:
        adjusted = dict(selected_parts)
        adjusted['cpu'] = affordable[-1]
        return _resolve_compatibility(adjusted, usage, options=options)

    trial = dict(selected_parts)
    trial['cpu'] = x3d_candidates[0]
    trial = _resolve_compatibility(trial, usage, options=options)
    trial_total = _sum_selected_price(trial)
    trial, trial_total = _downgrade_selected_parts(trial, trial_total, budget, options=options)
    if trial_total <= budget and _is_gaming_cpu_x3d_preferred(trial.get('cpu')):
        return trial

    return selected_parts


def _rightsize_case_after_selection(selected_parts, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    current_case = selected_parts.get('case')
    if not current_case:
        return selected_parts

    # ケースファン方針を指定した場合は、方針優先で高価格ケースが必要な可能性があるため維持。
    if options.get('case_fan_policy', 'auto') != 'auto':
        return selected_parts

    candidates = [
        p
        for p in PCPart.objects.filter(part_type='case').order_by('price')
        if _is_part_suitable('case', p) and _matches_selection_options('case', p, options=options)
    ]
    if not candidates:
        return selected_parts

    cheapest = candidates[0]
    if cheapest.price >= current_case.price:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['case'] = cheapest
    return adjusted


def _rightsize_motherboard_for_gaming_spec(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    current_mb = selected_parts.get('motherboard')
    current_gpu = selected_parts.get('gpu')
    if not current_mb or not current_gpu:
        return selected_parts

    # ゲーミングではGPUを主役にするため、MBの過剰高額化を抑える。
    # 目安: GPU価格の55% or 総予算12% を超えるMBは右サイズ化対象。
    price_cap = min(int(current_gpu.price * 0.55), int(budget * 0.12))
    price_cap = max(price_cap, 18000)
    if current_mb.price <= price_cap:
        return selected_parts

    current_mem_type = _infer_motherboard_memory_type(current_mb)
    cpu_part = selected_parts.get('cpu')
    cpu_socket = _get_spec(cpu_part, 'socket') if cpu_part else ''

    candidates = [
        p
        for p in PCPart.objects.filter(part_type='motherboard').order_by('price')
        if _is_part_suitable('motherboard', p)
        and _matches_selection_options('motherboard', p, options=options)
        and p.price < current_mb.price
        and p.price <= price_cap
    ]

    if cpu_socket:
        socket_filtered = [p for p in candidates if _get_spec(p, 'socket') == cpu_socket]
        if socket_filtered:
            candidates = socket_filtered

    if current_mem_type:
        mem_type_filtered = [p for p in candidates if _infer_motherboard_memory_type(p) == current_mem_type]
        if mem_type_filtered:
            candidates = mem_type_filtered

    candidates = _prefer_motherboard_candidates(candidates, options.get('case_size', 'any'))
    if not candidates:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['motherboard'] = candidates[-1]
    return adjusted


def _upgrade_to_liquid_cooler_with_surplus(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts
    if options.get('cooling_profile') != 'performance':
        return selected_parts

    current_cooler = selected_parts.get('cpu_cooler')
    if not current_cooler:
        return selected_parts

    current_text = f"{getattr(current_cooler, 'name', '')} {getattr(current_cooler, 'url', '')}".lower()
    if _is_cpu_cooler_type_match(current_cooler, 'liquid') or '水冷' in current_text:
        return selected_parts

    total_price = _sum_selected_price(selected_parts)
    surplus = budget - total_price
    # 十分な余剰がある場合のみ、水冷への自動アップグレードを許可する。
    if surplus < 15000:
        return selected_parts

    liquid_options = dict(options)
    liquid_options['cooler_type'] = 'liquid'

    current_case = selected_parts.get('case')

    def _infer_cooler_radiator_mm(part):
        text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
        for size in (420, 360, 280, 240, 140, 120):
            if f"{size}mm" in text or f"{size} mm" in text:
                return size
        return _extract_numeric_radiator_size(_get_spec(part, 'radiator_mm', None))

    liquid_candidates = []
    for candidate in PCPart.objects.filter(part_type='cpu_cooler').order_by('price'):
        if candidate.price <= current_cooler.price:
            continue
        if total_price - current_cooler.price + candidate.price > budget:
            continue
        if not _is_part_suitable('cpu_cooler', candidate):
            continue
        if not _matches_selection_options('cpu_cooler', candidate, options=liquid_options):
            continue
        if not _is_allowed_cpu_cooler_brand(candidate):
            continue

        radiator_mm = _infer_cooler_radiator_mm(candidate)
        if current_case and radiator_mm and not _is_case_radiator_compatible(current_case, str(radiator_mm)):
            continue

        liquid_candidates.append(candidate)

    if not liquid_candidates:
        return selected_parts

    picked = sorted(
        liquid_candidates,
        key=lambda p: (_cpu_cooler_profile_score(p, 'performance', 'liquid'), p.price),
        reverse=True,
    )[0]

    adjusted = dict(selected_parts)
    adjusted['cpu_cooler'] = picked
    return adjusted


def _upgrade_case_for_cooling_with_surplus(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    current_case = selected_parts.get('case')
    if not current_case:
        return selected_parts

    total_price = _sum_selected_price(selected_parts)
    surplus = budget - total_price
    if surplus < 8000:
        return selected_parts

    # auto は airflow と同等の冷却優先として評価する。
    requested_policy = options.get('case_fan_policy', 'auto')
    target_policy = 'airflow' if requested_policy == 'auto' else requested_policy

    current_cooler = selected_parts.get('cpu_cooler')
    cooler_text = f"{getattr(current_cooler, 'name', '')} {getattr(current_cooler, 'url', '')}".lower()

    def _infer_cooler_radiator_mm(part):
        text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
        for size in (420, 360, 280, 240, 140, 120):
            if f"{size}mm" in text or f"{size} mm" in text:
                return size
        return _extract_numeric_radiator_size(_get_spec(part, 'radiator_mm', None))

    required_radiator_mm = None
    if current_cooler and (_is_cpu_cooler_type_match(current_cooler, 'liquid') or '水冷' in cooler_text):
        required_radiator_mm = _infer_cooler_radiator_mm(current_cooler)

    current_score = _case_fan_policy_score(current_case, target_policy)
    candidates = []
    for candidate in PCPart.objects.filter(part_type='case').order_by('price'):
        if candidate.price <= current_case.price:
            continue
        if total_price - current_case.price + candidate.price > budget:
            continue
        if not _is_part_suitable('case', candidate):
            continue
        if not _matches_selection_options('case', candidate, options=options):
            continue
        if required_radiator_mm and not _is_case_radiator_compatible(candidate, str(required_radiator_mm)):
            continue
        candidates.append(candidate)

    if not candidates:
        return selected_parts

    best = sorted(
        candidates,
        key=lambda p: (_case_fan_policy_score(p, target_policy), p.price),
        reverse=True,
    )[0]
    if _case_fan_policy_score(best, target_policy) <= current_score:
        return selected_parts

    adjusted = dict(selected_parts)
    adjusted['case'] = best
    return adjusted


def _enforce_gaming_spec_prefers_nvme_storage(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'spec':
        return selected_parts

    storage = selected_parts.get('storage')
    if not storage:
        return selected_parts

    current_media = _infer_storage_media_type(storage)
    current_interface = _infer_storage_interface(storage)
    if current_media == 'ssd' and current_interface == 'nvme':
        return selected_parts

    def _preferred_storage_candidates(base_options):
        pool = [
            p
            for p in PCPart.objects.filter(part_type='storage').order_by('price')
            if _is_part_suitable('storage', p) and _matches_selection_options('storage', p, options=base_options)
        ]
        if not pool:
            return []

        nvme_ssd = [p for p in pool if _infer_storage_media_type(p) == 'ssd' and _infer_storage_interface(p) == 'nvme']
        if nvme_ssd:
            return nvme_ssd
        sata_ssd = [p for p in pool if _infer_storage_media_type(p) == 'ssd']
        return sata_ssd

    strict_preferred = _preferred_storage_candidates(options)

    # 容量条件が厳しい場合でも、最低512GBまで緩めたNVMe候補を必ず試す。
    relaxed_options = dict(options)
    relaxed_options['min_storage_capacity_gb'] = 512
    relaxed_preferred = _preferred_storage_candidates(relaxed_options)

    preferred = list(strict_preferred)
    strict_ids = {p.id for p in strict_preferred}
    preferred.extend([p for p in relaxed_preferred if p.id not in strict_ids])

    if not preferred:
        return selected_parts

    total_current = _sum_selected_price(selected_parts)
    for candidate in preferred:
        projected_total = total_current - storage.price + candidate.price
        if projected_total <= budget:
            adjusted = dict(selected_parts)
            adjusted['storage'] = candidate
            return adjusted

    # 直接置換で予算超過する場合は、他パーツを調整してでもSSD/NVMe維持を試みる。
    for candidate in preferred:
        trial = dict(selected_parts)
        trial['storage'] = candidate
        trial_total = _sum_selected_price(trial)
        trial, trial_total = _downgrade_selected_parts(trial, trial_total, budget, options=relaxed_options)

        final_storage = trial.get('storage')
        if not final_storage:
            continue
        if trial_total > budget:
            continue

        final_media = _infer_storage_media_type(final_storage)
        final_interface = _infer_storage_interface(final_storage)
        if final_media == 'ssd' and final_interface == 'nvme':
            return trial

    return selected_parts


def _apply_build_priority_weights(usage, build_priority, use_igpu, custom_budget_weights=None):
    if custom_budget_weights is not None:
        return dict(custom_budget_weights)

    base = IGPU_BUDGET_WEIGHTS.get(usage) if use_igpu else USAGE_BUDGET_WEIGHTS.get(usage)
    if not base:
        return None

    adjusted = dict(base)
    if build_priority != 'spec' or use_igpu:
        return adjusted

    gpu_boost_map = {
        'gaming': 0.20,
        'creator': 0.08,
    }
    boost = gpu_boost_map.get(usage, 0.06)
    adjusted['gpu'] = min(0.75, adjusted.get('gpu', 0) + boost)

    # GPUへ寄せた分は、優先度の低いカテゴリから順に減らす。
    remaining = boost
    reduce_order = ['memory', 'storage', 'motherboard', 'case', 'psu', 'cpu_cooler', 'cpu']
    floors = {
        'cpu': 0.17 if usage == 'gaming' else (0.14 if usage == 'creator' else 0.10),
        'motherboard': 0.08,
        'memory': 0.05,
        'storage': 0.05,
        'os': 0.04,
        'case': 0.00,
        'psu': 0.04,
        'cpu_cooler': 0.03,
    }

    for key in reduce_order:
        if remaining <= 0:
            break
        current = adjusted.get(key, 0)
        floor = floors.get(key, 0.03)
        reducible = max(0, current - floor)
        delta = min(remaining, reducible)
        adjusted[key] = current - delta
        remaining -= delta

    # 減額しきれない場合はGPU増加分を戻して配分合計の歪みを抑える。
    if remaining > 0:
        adjusted['gpu'] = max(0, adjusted.get('gpu', 0) - remaining)

    return adjusted


def _refresh_selection_options_with_selected_parts(selection_options, selected_parts):
    updated = dict(selection_options)

    cpu_part = selected_parts.get('cpu')
    if cpu_part:
        cpu_socket = _get_spec(cpu_part, 'socket')
        if cpu_socket:
            updated['cpu_socket'] = cpu_socket
        else:
            updated.pop('cpu_socket', None)

        min_memory_speed_mhz = _minimum_memory_speed_for_selected_cpu(
            cpu_part,
            updated.get('usage', 'gaming'),
            options=updated,
        )
        if min_memory_speed_mhz:
            updated['min_memory_speed_mhz'] = min_memory_speed_mhz
        else:
            updated.pop('min_memory_speed_mhz', None)

    motherboard_part = selected_parts.get('motherboard')
    if motherboard_part:
        mb_mem_type = _infer_motherboard_memory_type(motherboard_part)
        if mb_mem_type:
            updated['motherboard_memory_type'] = mb_mem_type
        else:
            updated.pop('motherboard_memory_type', None)

    updated['required_psu_wattage'] = _required_psu_wattage(selected_parts, updated.get('usage', 'gaming'))
    return updated


def _is_premium_gaming_cpu_for_cost_build(part, budget):
    if not part or not _is_gaming_cpu_x3d_preferred(part):
        return False

    text = f"{part.name} {part.url}".lower()
    if 'ryzen 9' in text:
        return True

    return part.price >= max(90000, int(budget * 0.16))


def _rebalance_gaming_cost_cpu_to_storage(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'cost':
        return selected_parts

    cpu = selected_parts.get('cpu')
    storage = selected_parts.get('storage')
    if not cpu or not storage:
        return selected_parts

    if not _is_premium_gaming_cpu_for_cost_build(cpu, budget):
        return selected_parts

    desired_capacity = int(options.get('min_storage_capacity_gb') or 0)
    current_capacity = _infer_storage_capacity_gb(storage)

    def _storage_upgrade_score(part):
        return (
            1 if _infer_storage_media_type(part) == 'ssd' else 0,
            1 if _infer_storage_interface(part) == 'nvme' else 0,
            _infer_storage_capacity_gb(part),
        )

    current_storage_score = _storage_upgrade_score(storage)
    current_cpu_text = f"{cpu.name} {cpu.url}".lower()
    current_cpu_socket = _get_spec(cpu, 'socket')

    base_total = _sum_selected_price(selected_parts) - cpu.price - storage.price
    cpu_candidates = [
        part
        for part in PCPart.objects.filter(part_type='cpu', price__lt=cpu.price).order_by('-price')
        if _is_part_suitable('cpu', part)
        and _matches_selection_options('cpu', part, options=options)
        and _is_gaming_cpu_x3d_preferred(part)
        and ('amd' in current_cpu_text or 'ryzen' in current_cpu_text)
        and (not current_cpu_socket or _get_spec(part, 'socket') == current_cpu_socket)
    ]
    if not cpu_candidates:
        return selected_parts

    storage_candidates = [
        part
        for part in PCPart.objects.filter(part_type='storage').order_by('price')
        if _is_part_suitable('storage', part)
        and _matches_selection_options('storage', part, options=options)
        and _infer_storage_media_type(part) == 'ssd'
        and _storage_upgrade_score(part) > current_storage_score
    ]
    if not storage_candidates:
        return selected_parts

    storage_candidates = sorted(
        storage_candidates,
        key=lambda part: (
            1 if desired_capacity and _infer_storage_capacity_gb(part) >= desired_capacity else 0,
            1 if _infer_storage_media_type(part) == 'ssd' else 0,
            1 if _infer_storage_interface(part) == 'nvme' else 0,
            _infer_storage_capacity_gb(part),
            -part.price,
        ),
        reverse=True,
    )

    best_trial = None
    best_score = None
    current_total = _sum_selected_price(selected_parts)

    for storage_candidate in storage_candidates:
        for cpu_candidate in cpu_candidates:
            trial = dict(selected_parts)
            trial['cpu'] = cpu_candidate
            trial['storage'] = storage_candidate
            trial = _resolve_compatibility(trial, usage, options=options)

            trial_total = _sum_selected_price(trial)

            final_cpu = trial.get('cpu')
            final_storage = trial.get('storage')
            if not final_cpu or not final_storage:
                continue
            if trial_total > budget:
                continue
            if final_cpu.price >= cpu.price:
                continue
            if not _is_gaming_cpu_x3d_preferred(final_cpu):
                continue
            if current_cpu_socket and _get_spec(final_cpu, 'socket') != current_cpu_socket:
                continue
            if _storage_upgrade_score(final_storage) <= current_storage_score:
                continue

            final_capacity = _infer_storage_capacity_gb(final_storage)
            score = (
                1 if desired_capacity and final_capacity >= desired_capacity else 0,
                1 if _infer_storage_media_type(final_storage) == 'ssd' else 0,
                1 if _infer_storage_interface(final_storage) == 'nvme' else 0,
                final_capacity,
                final_cpu.price,
                current_total - trial_total,
            )
            if best_score is None or score > best_score:
                best_trial = trial
                best_score = score

        if best_trial and desired_capacity and best_score[0] == 1:
            break

    return best_trial or selected_parts


def _prefer_higher_gaming_cost_x3d_cpu(selected_parts, budget, usage, options=None):
    options = options or {}
    if usage != 'gaming' or options.get('build_priority') != 'cost':
        return selected_parts

    current_cpu = selected_parts.get('cpu')
    current_memory = selected_parts.get('memory')
    if not current_cpu or not current_memory:
        return selected_parts
    if not _is_gaming_cpu_x3d_preferred(current_cpu):
        return selected_parts

    upgrade_candidates = [
        part
        for part in PCPart.objects.filter(part_type='cpu', price__gt=current_cpu.price).order_by('-price')
        if _is_part_suitable('cpu', part)
        and _matches_selection_options('cpu', part, options=options)
        and _is_gaming_cpu_x3d_preferred(part)
        and not _is_premium_gaming_cpu_for_cost_build(part, budget)
    ]
    if not upgrade_candidates:
        return selected_parts

    current_total = _sum_selected_price(selected_parts)
    target_profile = _target_memory_profile(budget, usage, options=options)
    target_capacity = target_profile['capacity_gb']
    preferred_modules = target_profile['preferred_modules']

    def _memory_downgrade_rank(part):
        return (
            _infer_memory_type(part) == 'DDR5',
            _infer_memory_capacity_gb(part) == target_capacity,
            _infer_memory_module_count(part) == preferred_modules,
            _infer_memory_speed_mhz(part),
            _infer_memory_capacity_gb(part),
            -part.price,
        )

    for cpu_candidate in upgrade_candidates:
        trial_options = dict(options)
        min_memory_speed_mhz = _minimum_memory_speed_for_selected_cpu(
            cpu_candidate,
            usage,
            options=trial_options,
        )
        if min_memory_speed_mhz:
            trial_options['min_memory_speed_mhz'] = min_memory_speed_mhz
        else:
            trial_options.pop('min_memory_speed_mhz', None)

        cheaper_memory_candidates = [
            part
            for part in PCPart.objects.filter(part_type='memory', price__lt=current_memory.price).order_by('price')
            if _is_part_suitable('memory', part)
            and _matches_selection_options('memory', part, options=trial_options)
            and _infer_memory_capacity_gb(part) >= target_capacity
        ]
        cheaper_memory_candidates = sorted(
            cheaper_memory_candidates,
            key=_memory_downgrade_rank,
            reverse=True,
        )

        direct_total = current_total - current_cpu.price + cpu_candidate.price
        if direct_total <= budget:
            adjusted = dict(selected_parts)
            adjusted['cpu'] = cpu_candidate
            adjusted = _resolve_compatibility(adjusted, usage, options=trial_options)
            return adjusted

        required_savings = direct_total - budget
        for memory_candidate in cheaper_memory_candidates:
            memory_savings = current_memory.price - memory_candidate.price
            if memory_savings < required_savings:
                continue

            trial = dict(selected_parts)
            trial['cpu'] = cpu_candidate
            trial['memory'] = memory_candidate
            trial = _resolve_compatibility(trial, usage, options=trial_options)
            if _sum_selected_price(trial) <= budget:
                return trial

    return selected_parts


def _enforce_memory_speed_floor(selected_parts, budget, usage, options=None):
    options = options or {}
    memory = selected_parts.get('memory')
    if not memory:
        return selected_parts

    min_memory_speed_mhz = options.get('min_memory_speed_mhz')
    if not min_memory_speed_mhz:
        return selected_parts
    if _infer_memory_speed_mhz(memory) >= int(min_memory_speed_mhz):
        return selected_parts

    current_total = _sum_selected_price(selected_parts)
    current_memory = selected_parts.get('memory')
    candidates = [
        part
        for part in PCPart.objects.filter(part_type='memory').order_by('price')
        if part.id != current_memory.id
        and _is_part_suitable('memory', part)
        and _matches_selection_options('memory', part, options=options)
        and _infer_memory_capacity_gb(part) >= _infer_memory_capacity_gb(current_memory)
    ]

    for candidate in candidates:
        projected_total = current_total - current_memory.price + candidate.price
        if projected_total <= budget:
            adjusted = dict(selected_parts)
            adjusted['memory'] = candidate
            return adjusted

    return selected_parts


def build_configuration_response(
    budget,
    usage,
    cooler_type='any',
    radiator_size='any',
    cooling_profile='balanced',
    case_size='any',
    case_fan_policy='auto',
    cpu_vendor='any',
    build_priority='balanced',
    storage_preference='ssd',
    storage2_part_id=None,
    storage3_part_id=None,
    os_edition='auto',
    custom_budget_weights=None,
    min_storage_capacity_gb=None,
    max_motherboard_chipset='any',
):
    if not isinstance(budget, int) or budget < 50000 or budget > 1500000:
        return None, Response({'detail': 'budgetは50,000円以上1,500,000円以下で入力してください'}, status=status.HTTP_400_BAD_REQUEST)

    if usage not in USAGE_POWER_MAP:
        return None, Response({'detail': 'usage must be gaming, creator, business, or standard'}, status=status.HTTP_400_BAD_REQUEST)

    selection_options = _normalize_selection_options(
        cooler_type=cooler_type,
        radiator_size=radiator_size,
        cooling_profile=cooling_profile,
        case_size=case_size,
        case_fan_policy=case_fan_policy,
        cpu_vendor=cpu_vendor,
        build_priority=build_priority,
        os_edition=os_edition,
        storage_preference=storage_preference,
        min_storage_capacity_gb=min_storage_capacity_gb,
        max_motherboard_chipset=max_motherboard_chipset,
    )
    selection_options['usage'] = usage
    selection_options['os_edition'] = _resolve_os_edition_by_usage(usage, selection_options['os_edition'])

    if usage == 'gaming':
        selection_options = dict(selection_options)
        if not selection_options.get('min_storage_capacity_gb'):
            if selection_options.get('build_priority') == 'spec':
                selection_options['min_storage_capacity_gb'] = 1000 if budget >= 220000 else 512
            elif selection_options.get('build_priority') == 'cost' and budget >= 450000:
                selection_options['min_storage_capacity_gb'] = 2000
            elif selection_options.get('build_priority') == 'cost' and budget >= 220000:
                selection_options['min_storage_capacity_gb'] = 1000

    if usage == 'gaming' and selection_options.get('build_priority') == 'spec':
        # gaming + spec はストレージ容量を優先するが、低予算では最低容量を抑える。
        selection_options['require_preferred_gaming_gpu'] = True
        selection_options['minimum_gaming_gpu_tier'] = _minimum_gaming_spec_gpu_tier(budget, usage, options=selection_options)

    normalized_custom_budget_weights = _normalize_custom_budget_weights(custom_budget_weights)
    if custom_budget_weights is not None and normalized_custom_budget_weights is None:
        return None, Response({'detail': 'custom_budget_weights must be a positive numeric mapping for part categories'}, status=status.HTTP_400_BAD_REQUEST)

    use_igpu = usage in IGPU_USAGES
    priority_weights = _apply_build_priority_weights(
        usage,
        selection_options['build_priority'],
        use_igpu,
        custom_budget_weights=normalized_custom_budget_weights,
    )

    selected_parts = {}
    total_price = 0

    for part_type in PART_ORDER:
        if use_igpu and part_type == 'gpu':
            continue  # 内蔵GPU使用のためdGPUをスキップ
        # マザーボード選定時は先に確定したCPUのソケットを絞り込み条件に追加
        effective_options = selection_options
        if part_type == 'motherboard':
            cpu_part = selected_parts.get('cpu')
            if cpu_part:
                cpu_socket = _get_spec(cpu_part, 'socket')
                if cpu_socket:
                    effective_options = dict(selection_options)
                    effective_options['cpu_socket'] = cpu_socket
        if part_type == 'memory':
            motherboard_part = selected_parts.get('motherboard')
            if motherboard_part:
                mb_mem_type = _infer_motherboard_memory_type(motherboard_part)
                if mb_mem_type:
                    effective_options = dict(effective_options)
                    effective_options['motherboard_memory_type'] = mb_mem_type
            cpu_part = selected_parts.get('cpu')
            if cpu_part:
                min_memory_speed_mhz = _minimum_memory_speed_for_selected_cpu(cpu_part, usage, options=effective_options)
                if min_memory_speed_mhz:
                    effective_options = dict(effective_options)
                    effective_options['min_memory_speed_mhz'] = min_memory_speed_mhz
        if part_type == 'psu':
            effective_options = dict(effective_options)
            effective_options['required_psu_wattage'] = _required_psu_wattage(selected_parts, usage)
        part = _pick_part_by_target(
            part_type,
            budget,
            usage,
            weights_override=priority_weights,
            options=effective_options,
        )
        if part:
            selected_parts[part_type] = part
            total_price += part.price

    # CPUソケット情報をoptions に付与して、互換チェック・ダウングレード時に引き継ぐ
    cpu_part = selected_parts.get('cpu')
    if cpu_part:
        cpu_socket = _get_spec(cpu_part, 'socket')
        if cpu_socket:
            selection_options = dict(selection_options)
            selection_options['cpu_socket'] = cpu_socket

    motherboard_part = selected_parts.get('motherboard')
    if motherboard_part:
        mb_mem_type = _infer_motherboard_memory_type(motherboard_part)
        if mb_mem_type:
            selection_options = dict(selection_options)
            selection_options['motherboard_memory_type'] = mb_mem_type

    selected_parts = _resolve_compatibility(selected_parts, usage, options=selection_options)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _rebalance_gaming_spec_gpu_memory(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selected_parts = _enforce_gaming_spec_prefers_x3d_cpu(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selected_parts = _resolve_compatibility(selected_parts, usage, options=selection_options)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    if not selected_parts:
        return None, Response({'detail': '該当する構成が見つかりません'}, status=status.HTTP_404_NOT_FOUND)

    selected_parts, total_price = _downgrade_selected_parts(
        selected_parts,
        total_price,
        budget,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)

    selected_parts = _enforce_gaming_spec_gpu_not_lower_than_memory(
        selected_parts,
        usage,
        options=selection_options,
    )
    selected_parts = _enforce_gaming_spec_prefers_rx_xt(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    total_price = _sum_selected_price(selected_parts)

    selected_parts, total_price = _drop_until_budget(selected_parts, total_price, budget)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)

    selected_parts = _rebalance_gaming_spec_gpu_memory(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selected_parts = _resolve_compatibility(selected_parts, usage, options=selection_options)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts, total_price = _downgrade_selected_parts(
        selected_parts,
        total_price,
        budget,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)

    selected_parts = _enforce_gaming_spec_gpu_not_lower_than_memory(
        selected_parts,
        usage,
        options=selection_options,
    )
    selected_parts = _enforce_gaming_spec_prefers_rx_xt(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    total_price = _sum_selected_price(selected_parts)

    selected_parts, total_price = _upgrade_memory_to_capacity_target(
        selected_parts,
        total_price,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)

    selected_parts, total_price = _upgrade_memory_with_surplus(
        selected_parts,
        total_price,
        budget,
        usage,
        options=selection_options,
    )

    selected_parts = _enforce_gaming_spec_gpu_not_lower_than_memory(
        selected_parts,
        usage,
        options=selection_options,
    )
    selected_parts = _enforce_gaming_spec_prefers_rx_xt(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    total_price = _sum_selected_price(selected_parts)

    extra_storage_parts = {}
    selected_storage2 = _resolve_storage_part_by_id(storage2_part_id)
    selected_storage3 = _resolve_storage_part_by_id(storage3_part_id)
    if selected_storage2:
        extra_storage_parts['storage2'] = selected_storage2
        total_price += selected_storage2.price
    if selected_storage3:
        extra_storage_parts['storage3'] = selected_storage3
        total_price += selected_storage3.price

    # 余剰予算の再配分を常に評価する。
    # 実際にアップグレードするかどうかは _upgrade_parts_with_surplus 側で用途/方針ごとに判定する。
    selected_parts, total_price = _upgrade_parts_with_surplus(
        selected_parts,
        total_price,
        budget,
        usage,
        options=selection_options,
    )
    selected_parts = _resolve_compatibility(selected_parts, usage, options=selection_options)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts, total_price = _upgrade_memory_to_capacity_target(
        selected_parts,
        total_price,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _enforce_gaming_spec_prefers_x3d_cpu(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _rightsize_case_after_selection(
        selected_parts,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _rightsize_motherboard_for_gaming_spec(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selected_parts = _resolve_compatibility(selected_parts, usage, options=selection_options)
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _rebalance_gaming_cost_cpu_to_storage(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _prefer_higher_gaming_cost_x3d_cpu(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _enforce_memory_speed_floor(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _enforce_gaming_spec_prefers_nvme_storage(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _enforce_gaming_spec_best_value_gpu(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _upgrade_to_liquid_cooler_with_surplus(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _upgrade_case_for_cooling_with_surplus(
        selected_parts,
        budget,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected_parts = _rightsize_psu_after_selection(
        selected_parts,
        usage,
        options=selection_options,
    )
    selection_options = _refresh_selection_options_with_selected_parts(selection_options, selected_parts)
    total_price = _sum_selected_price(selected_parts)

    selected = []
    for part_type in PART_ORDER:
        part = selected_parts.get(part_type)
        if not part:
            continue
        selected.append({
            'category': part_type,
            'name': part.name,
            'price': part.price,
            'url': part.url,
            'specs': part.specs,
        })

    for part_type in ('storage2', 'storage3'):
        part = extra_storage_parts.get(part_type)
        if not part:
            continue
        selected.append({
            'category': part_type,
            'name': part.name,
            'price': part.price,
            'url': part.url,
            'specs': part.specs,
        })

    # 内蔵GPU使用構成の場合: CPUの直後に統合グラフィックスエントリを挿入
    if use_igpu:
        cpu_part = selected_parts.get('cpu')
        igpu_entry = {
            'category': 'gpu',
            'name': '内蔵GPU（統合グラフィックス）',
            'price': 0,
            'url': cpu_part.url if cpu_part else '',
        }
        cpu_index = next((i for i, p in enumerate(selected) if p['category'] == 'cpu'), -1)
        selected.insert(cpu_index + 1, igpu_entry)

    estimated_power = _estimate_system_power_w({**selected_parts, **extra_storage_parts}, usage)

    configuration = Configuration.objects.create(
        budget=budget,
        usage=usage,
        total_price=total_price,
        cpu=selected_parts.get('cpu'),
        cpu_cooler=selected_parts.get('cpu_cooler'),
        gpu=None,  # iGPU構成はgpu=None、gaming/creatorは後で上書き
        motherboard=selected_parts.get('motherboard'),
        memory=selected_parts.get('memory'),
        storage=selected_parts.get('storage'),
        storage2=extra_storage_parts.get('storage2'),
        storage3=extra_storage_parts.get('storage3'),
        os=selected_parts.get('os'),
        psu=selected_parts.get('psu'),
        case=selected_parts.get('case'),
    ) if use_igpu else Configuration.objects.create(
        budget=budget,
        usage=usage,
        total_price=total_price,
        cpu=selected_parts.get('cpu'),
        cpu_cooler=selected_parts.get('cpu_cooler'),
        gpu=selected_parts.get('gpu'),
        motherboard=selected_parts.get('motherboard'),
        memory=selected_parts.get('memory'),
        storage=selected_parts.get('storage'),
        storage2=extra_storage_parts.get('storage2'),
        storage3=extra_storage_parts.get('storage3'),
        os=selected_parts.get('os'),
        psu=selected_parts.get('psu'),
        case=selected_parts.get('case'),
    )

    return {
        'usage': usage,
        'budget': budget,
        'cooler_type': selection_options['cooler_type'],
        'radiator_size': selection_options['radiator_size'],
        'cooling_profile': selection_options['cooling_profile'],
        'case_size': selection_options['case_size'],
        'case_fan_policy': selection_options['case_fan_policy'],
        'cpu_vendor': selection_options['cpu_vendor'],
        'build_priority': selection_options['build_priority'],
        'storage_preference': selection_options['storage_preference'],
        'os_edition': selection_options['os_edition'],
        'custom_budget_weights': normalized_custom_budget_weights,
        'configuration_id': configuration.id,
        'total_price': total_price,
        'estimated_power_w': estimated_power,
        'parts': selected,
    }, None


PART_TYPE_LABELS = {
    'cpu':         'CPU',
    'cpu_cooler':  'CPUクーラー',
    'gpu':         'GPU',
    'motherboard': 'マザーボード',
    'memory':      'メモリー',
    'storage':     'ストレージ',
    'os':          'OS',
    'psu':         '電源',
    'case':        'ケース',
}


def build_scraper_status_summary():
    latest = ScraperStatus.objects.order_by('-updated_at').first()
    total_parts = PCPart.objects.count()

    # カテゴリ別件数・価格帯を一括集計
    from django.db.models import Count as DbCount2, Min as DbMin, Max as DbMax
    rows = (
        PCPart.objects
        .values('part_type')
        .annotate(count=DbCount2('id'), min_price=DbMin('price'), max_price=DbMax('price'))
        .order_by('part_type')
    )
    category_stats = [
        {
            'part_type': r['part_type'],
            'label': PART_TYPE_LABELS.get(r['part_type'], r['part_type']),
            'count': r['count'],
            'min_price': r['min_price'],
            'max_price': r['max_price'],
        }
        for r in rows
    ]
    cached_categories = sorted([r['part_type'] for r in category_stats])

    return {
        'cache_enabled': latest.cache_enabled if latest else True,
        'cache_ttl_seconds': latest.cache_ttl_seconds if latest else 3600,
        'last_update_time': latest.updated_at.isoformat() if latest else None,
        'cached_categories': cached_categories,
        'category_stats': category_stats,
        'total_parts_in_db': total_parts,
        'retry_count': 3,
        'rate_limit_delay': 1.0,
    }


class PCPartViewSet(viewsets.ModelViewSet):
    """PC パーツの CRUD API"""
    queryset = PCPart.objects.all()
    serializer_class = PCPartSerializer
    filterset_fields = ['part_type']
    search_fields = ['name']
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        part_type = request.query_params.get('type')
        if not part_type:
            return Response({'error': 'type parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        parts = PCPart.objects.filter(part_type=part_type)
        serializer = self.get_serializer(parts, many=True)
        return Response(serializer.data)


class ConfigurationViewSet(viewsets.ModelViewSet):
    """PC 構成の CRUD API"""
    queryset = Configuration.objects.filter(is_deleted=False)
    serializer_class = ConfigurationSerializer
    filterset_fields = ['usage']

    def get_queryset(self):
        return Configuration.objects.filter(is_deleted=False)
    
    def perform_create(self, serializer):
        """構成作成時に合計金額を計算"""
        config = serializer.save()
        self._calculate_total_price(config)
    
    def perform_update(self, serializer):
        """構成更新時に合計金額を再計算"""
        config = serializer.save()
        self._calculate_total_price(config)
    
    def _calculate_total_price(self, config):
        """合計金額を計算"""
        total = 0
        for part_field in ['cpu', 'cpu_cooler', 'gpu', 'motherboard', 'memory', 'storage', 'os', 'psu', 'case']:
            part = getattr(config, part_field)
            if part:
                total += part.price
        for part_field in ['storage2', 'storage3']:
            part = getattr(config, part_field, None)
            if part:
                total += part.price
        config.total_price = total
        config.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        response_data, error_response = build_configuration_response(
            request.data.get('budget'),
            request.data.get('usage'),
            request.data.get('cooler_type'),
            request.data.get('radiator_size'),
            request.data.get('cooling_profile'),
            request.data.get('case_size'),
            request.data.get('case_fan_policy'),
            request.data.get('cpu_vendor'),
            request.data.get('build_priority'),
            request.data.get('storage_preference'),
            request.data.get('storage2_part_id'),
            request.data.get('storage3_part_id'),
            request.data.get('os_edition'),
            request.data.get('custom_budget_weights'),
            request.data.get('min_storage_capacity_gb'),
            request.data.get('max_motherboard_chipset'),
        )
        if error_response:
            return error_response
        return Response(response_data)


class ScraperStatusViewSet(viewsets.ModelViewSet):
    """スクレイパー状態管理 API"""
    queryset = ScraperStatus.objects.all()
    serializer_class = ScraperStatusSerializer

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        return Response(build_scraper_status_summary())


class GenerateConfigAPIView(APIView):
    """Frontend互換: FastAPIの /generate-config 相当"""

    def post(self, request):
        response_data, error_response = build_configuration_response(
            request.data.get('budget'),
            request.data.get('usage'),
            request.data.get('cooler_type'),
            request.data.get('radiator_size'),
            request.data.get('cooling_profile'),
            request.data.get('case_size'),
            request.data.get('case_fan_policy'),
            request.data.get('cpu_vendor'),
            request.data.get('build_priority'),
            request.data.get('storage_preference'),
            request.data.get('storage2_part_id'),
            request.data.get('storage3_part_id'),
            request.data.get('os_edition'),
            request.data.get('custom_budget_weights'),
            request.data.get('min_storage_capacity_gb'),
            request.data.get('max_motherboard_chipset'),
        )
        if error_response:
            return error_response
        return Response(response_data)


class ScraperStatusCompatAPIView(APIView):
    """Frontend互換: FastAPIの /scraper/status 相当"""

    def get(self, request):
        return Response(build_scraper_status_summary())


class MarketPriceRangeAPIView(APIView):
    """フロントエンド向け: ドスパラ相場レンジを返す"""

    def get(self, request):
        data = fetch_dospara_market_price_range(timeout=15)
        return Response(data)


PART_TYPE_LABELS = {
    'cpu':         'CPU',
    'cpu_cooler':  'CPUクーラー',
    'gpu':         'GPU',
    'motherboard': 'マザーボード',
    'memory':      'メモリ',
    'storage':     'ストレージ',
    'os':          'OS',
    'psu':         '電源ユニット',
    'case':        'PCケース',
}

STORAGE_INTERFACE_LABELS = {
    'nvme': 'NVMe',
    'sata': 'SATA',
    'other': 'その他',
}


def _format_storage_capacity_label(capacity_gb):
    if not capacity_gb:
        return '容量不明'
    if capacity_gb >= 1024:
        value_tb = capacity_gb / 1024
        if float(value_tb).is_integer():
            return f'{int(value_tb)}TB'
        return f'{value_tb:.1f}TB'
    return f'{capacity_gb}GB'


def _infer_storage_interface(part):
    interface = str(_get_spec(part, 'interface', '') or '').strip().upper()
    if interface == 'NVME':
        return 'nvme'
    if interface == 'SATA':
        return 'sata'

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}".lower()
    if 'nvme' in text:
        return 'nvme'
    if 'sata' in text:
        return 'sata'
    # WD NVMe models: SN700, SN850, SN750, SN580, SN500
    if re.search(r'\bsn[5-9]\d{2}\b', text):
        return 'nvme'
    # WD SATA SSD models: SA500
    if re.search(r'\bsa\d{3}\b', text):
        return 'sata'
    # Samsung NVMe models: 970 EVO/PRO, 980 PRO, 990 PRO
    if re.search(r'\b(970|980|990)\s*(evo|pro)\b', text):
        return 'nvme'
    # M.2 in product name → NVMe
    if 'm.2' in text:
        return 'nvme'
    return 'other'


def _serialize_storage_part(part):
    capacity_gb = _infer_storage_capacity_gb(part)
    interface_key = _infer_storage_interface(part)
    return {
        'id': part.id,
        'name': part.name,
        'price': part.price,
        'url': part.url,
        'capacity_gb': capacity_gb,
        'capacity_label': _format_storage_capacity_label(capacity_gb),
        'interface': interface_key,
        'interface_label': STORAGE_INTERFACE_LABELS.get(interface_key, 'その他'),
        'form_factor': _get_spec(part, 'form_factor'),
        'updated_at': part.updated_at,
    }


def _build_storage_inventory_summary():
    storage_parts = list(PCPart.objects.filter(part_type='storage').order_by('price', 'name'))
    serialized_items = [_serialize_storage_part(part) for part in storage_parts]

    capacity_groups = defaultdict(list)
    interface_groups = defaultdict(list)
    latest_updated_at = None
    for item in serialized_items:
        capacity_groups[(item['capacity_gb'], item['capacity_label'])].append(item)
        interface_groups[item['interface']].append(item)
        updated_at = item['updated_at']
        if updated_at and (latest_updated_at is None or updated_at > latest_updated_at):
            latest_updated_at = updated_at

    capacity_summary = []
    for (capacity_gb, label), items in sorted(capacity_groups.items(), key=lambda entry: (entry[0][0], entry[0][1])):
        prices = [item['price'] for item in items]
        capacity_summary.append({
            'capacity_gb': capacity_gb,
            'label': label,
            'count': len(items),
            'min_price': min(prices) if prices else None,
            'max_price': max(prices) if prices else None,
            'avg_price': int(sum(prices) / len(prices)) if prices else None,
            'items': items,
        })

    interface_summary = []
    for interface_key in ('nvme', 'sata', 'other'):
        items = interface_groups.get(interface_key, [])
        prices = [item['price'] for item in items]
        interface_summary.append({
            'interface': interface_key,
            'label': STORAGE_INTERFACE_LABELS[interface_key],
            'count': len(items),
            'min_price': min(prices) if prices else None,
            'max_price': max(prices) if prices else None,
            'avg_price': int(sum(prices) / len(prices)) if prices else None,
        })

    return {
        'total_count': len(serialized_items),
        'latest_updated_at': latest_updated_at,
        'capacity_summary': capacity_summary,
        'interface_summary': interface_summary,
    }


class PartPriceRangesAPIView(APIView):
    """パーツ種別ごとの価格レンジ (min/max/avg/count) を DB 集計で返す"""

    def get(self, request):
        result = {}
        for pt, label in PART_TYPE_LABELS.items():
            agg = PCPart.objects.filter(part_type=pt).aggregate(
                min_price=Min('price'),
                max_price=Max('price'),
                avg_price=Avg('price'),
                total=DbCount('id'),
            )
            result[pt] = {
                'label': label,
                'min': agg['min_price'],
                'max': agg['max_price'],
                'avg': int(agg['avg_price']) if agg['avg_price'] else None,
                'count': agg['total'],
            }
        return Response(result)


class StorageInventoryAPIView(APIView):
    """ストレージDBの一覧と容量別・接続別サマリーを返す"""

    def get(self, request):
        return Response(_build_storage_inventory_summary())

