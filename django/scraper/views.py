import re

from rest_framework import viewsets, status
from django.db.models import Min, Max, Avg, Count as DbCount
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from .dospara_scraper import fetch_dospara_market_price_range
from .models import PCPart, Configuration, ScraperStatus
from .serializers import PCPartSerializer, ConfigurationSerializer, ScraperStatusSerializer


PART_ORDER = ['cpu', 'cpu_cooler', 'gpu', 'motherboard', 'memory', 'storage', 'psu', 'case']
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
        'storage': 0.06,
        'psu': 0.05,
        'case': 0.00,
    },
    # クリエイター: CPU・メモリ・ストレージ重視、GPU中程度
    'creator': {
        'cpu': 0.27,
        'cpu_cooler': 0.06,
        'gpu': 0.18,
        'motherboard': 0.10,
        'memory': 0.16,
        'storage': 0.14,
        'psu': 0.06,
        'case': 0.03,
    },
    # ビジネス: CPU中程度、GPU控えめ、信頼性重視
    'business': {
        'cpu': 0.24,
        'cpu_cooler': 0.03,
        'gpu': 0.08,
        'motherboard': 0.15,
        'memory': 0.18,
        'storage': 0.20,
        'psu': 0.08,
        'case': 0.04,
    },
    # スタンダード: バランス型
    'standard': {
        'cpu': 0.20,
        'cpu_cooler': 0.04,
        'gpu': 0.16,
        'motherboard': 0.14,
        'memory': 0.14,
        'storage': 0.14,
        'psu': 0.10,
        'case': 0.08,
    },
}

# 高予算帯のクリエイター用途では、GPUを上位帯から選定して
# "フラッグシップ予算なのに中位GPU" になりにくくする。
CREATOR_FLAGSHIP_BUDGET_THRESHOLD = 900000
CREATOR_FLAGSHIP_GPU_BUDGET_CAP = 0.75

CATEGORY_DROP_PRIORITY = ['case', 'psu', 'storage', 'memory', 'cpu_cooler', 'motherboard', 'gpu', 'cpu']

# 内蔵GPU(iGPU)使用: ビジネス・スタンダードはdGPU不要
IGPU_USAGES = frozenset({'business', 'standard'})

# GPUウェイト分を他パーツへ再分配した予算配分
IGPU_BUDGET_WEIGHTS = {
    'business': {
        'cpu': 0.25,
        'cpu_cooler': 0.05,
        'motherboard': 0.17,
        'memory': 0.20,
        'storage': 0.21,
        'psu': 0.08,
        'case': 0.04,
    },
    'standard': {
        'cpu': 0.24,
        'cpu_cooler': 0.06,
        'motherboard': 0.18,
        'memory': 0.18,
        'storage': 0.16,
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

    url = (part.url or '').lower()
    for hint in UNSUITABLE_URL_HINTS.get(part_type, []):
        if hint in url:
            return False

    return True


def _normalize_cooler_type(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'air', 'liquid'}:
            return normalized
    return 'any'


def _normalize_radiator_size(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'120', '240', '360'}:
            return normalized
    return 'any'


def _normalize_cooling_profile(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'silent', 'performance'}:
            return normalized
    return 'balanced'


def _normalize_case_size(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'mini', 'mid', 'full'}:
            return normalized
    return 'any'


def _normalize_cpu_vendor(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'intel', 'amd'}:
            return normalized
    return 'any'


def _normalize_build_priority(value):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'cost', 'spec'}:
            return normalized
    return 'balanced'


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


def _normalize_selection_options(cooler_type, radiator_size, cooling_profile, case_size, cpu_vendor, build_priority):
    return {
        'cooler_type': _normalize_cooler_type(cooler_type),
        'radiator_size': _normalize_radiator_size(radiator_size),
        'cooling_profile': _normalize_cooling_profile(cooling_profile),
        'case_size': _normalize_case_size(case_size),
        'cpu_vendor': _normalize_cpu_vendor(cpu_vendor),
        'build_priority': _normalize_build_priority(build_priority),
    }


def _is_cpu_cooler_type_match(part, cooler_type):
    if cooler_type == 'any':
        return True

    text = f"{part.name} {part.url}".lower()
    for keyword in COOLER_TYPE_KEYWORDS.get(cooler_type, []):
        if keyword in text:
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


def _is_gaming_spec_gpu_preferred(part):
    text = f"{part.name} {part.url}".lower()
    if any(keyword in text for keyword in GAMING_SPEC_GPU_KEYWORDS):
        return True

    # "RX 9070" のような表記も拾う
    return re.search(r'\brx\s*\d{3,4}\b', text) is not None


def _extract_numeric_radiator_size(value):
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


def _pick_part_by_target(part_type, budget, usage, weights_override=None, options=None):
    options = options or {}
    cooler_type = options.get('cooler_type', 'any')
    radiator_size = options.get('radiator_size', 'any')
    cooling_profile = options.get('cooling_profile', 'balanced')
    case_size = options.get('case_size', 'any')
    cpu_vendor = options.get('cpu_vendor', 'any')
    build_priority = options.get('build_priority', 'balanced')
    motherboard_memory_type = str(options.get('motherboard_memory_type', '') or '').upper()
    min_storage_capacity_gb = options.get('min_storage_capacity_gb')

    candidates = [p for p in PCPart.objects.filter(part_type=part_type).order_by('price') if _is_part_suitable(part_type, p)]
    if part_type == 'gpu':
        candidates = [p for p in candidates if not _is_gt_series_gpu(p)]
    if part_type == 'cpu_cooler':
        candidates = [p for p in candidates if _is_cpu_cooler_type_match(p, cooler_type)]
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

    if part_type == 'gpu' and usage == 'gaming' and build_priority == 'spec':
        preferred_gpu = [p for p in candidates if _is_gaming_spec_gpu_preferred(p)]
        if preferred_gpu:
            candidates = preferred_gpu

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
        if part_type == 'memory':
            # gaming + spec はGPU優先のため、メモリは目標価格内から選ぶ。
            # それ以外の spec では、候補全体から上位メモリを選んでもよい。
            if build_priority == 'spec' and usage != 'gaming':
                memory_pool = candidates
            else:
                memory_pool = within_target
            profiled = _memory_profile_pick(memory_pool, build_priority)
            if profiled:
                return profiled
        if build_priority == 'spec' and part_type == 'motherboard':
            return candidates[-1]
        if build_priority == 'cost':
            return within_target[0]
        if part_type == 'cpu_cooler':
            return sorted(
                within_target,
                key=lambda p: (_cpu_cooler_profile_score(p, cooling_profile, cooler_type), p.price),
                reverse=True,
            )[0]
        return sorted(within_target, key=lambda p: p.price, reverse=True)[0]

    if build_priority == 'cost':
        if part_type == 'memory':
            profiled = _memory_profile_pick(candidates, build_priority)
            if profiled:
                return profiled
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

    if part_type == 'memory' and build_priority == 'spec':
        profiled = _memory_profile_pick(candidates, build_priority)
        if profiled:
            return profiled

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


def _memory_profile_pick(candidates, build_priority):
    if not candidates:
        return None

    def _normalized_memory_type(part):
        return _infer_memory_type(part)

    def _capacity_gb(part):
        return _infer_memory_capacity_gb(part)

    if build_priority == 'cost':
        # コスト重視: DDR4優先 + 小容量優先 + 同条件なら安価なもの
        return sorted(
            candidates,
            key=lambda p: (
                _normalized_memory_type(p) != 'DDR4',
                _capacity_gb(p) > 16,
                _capacity_gb(p),
                p.price,
            ),
        )[0]

    if build_priority == 'spec':
        # スペック重視: DDR5優先 + 大容量優先 + 同条件なら高価なもの
        return sorted(
            candidates,
            key=lambda p: (
                _normalized_memory_type(p) == 'DDR5',
                _capacity_gb(p),
                p.price,
            ),
            reverse=True,
        )[0]

    return None


def _infer_storage_capacity_gb(part):
    capacity = int(_get_spec(part, 'capacity_gb', 0) or 0)
    if capacity > 0:
        return capacity

    text = f"{getattr(part, 'name', '')} {getattr(part, 'url', '')}"
    match = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB)", text, re.IGNORECASE)
    if not match:
        return 0

    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == 'TB':
        return int(value * 1024)
    return int(value)


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
    if psu and psu_watt:
        if int(psu_watt) < _required_power_w(usage):
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
    motherboard_memory_type = str(options.get('motherboard_memory_type', '') or '').upper()
    min_storage_capacity_gb = options.get('min_storage_capacity_gb')
    require_preferred_gaming_gpu = options.get('require_preferred_gaming_gpu', False)

    if part_type == 'cpu_cooler':
        if not _is_cpu_cooler_type_match(part, cooler_type):
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
        if require_preferred_gaming_gpu and not _is_gaming_spec_gpu_preferred(part):
            return False
        return not _is_gt_series_gpu(part)

    if part_type == 'motherboard':
        cpu_socket = options.get('cpu_socket')
        if cpu_socket:
            mb_socket = _get_spec(part, 'socket')
            if mb_socket and mb_socket != cpu_socket:
                return False
        return True

    if part_type == 'memory':
        if motherboard_memory_type:
            mem_type = _infer_memory_type(part)
            if mem_type and mem_type != motherboard_memory_type:
                return False
        return True

    if part_type == 'storage':
        if min_storage_capacity_gb:
            capacity_gb = _infer_storage_capacity_gb(part)
            if capacity_gb < int(min_storage_capacity_gb):
                return False
        return True

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
                new_mb = _pick_candidate('motherboard', lambda p: _get_spec(p, 'socket') == cpu_socket)
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
                new_mb = _pick_candidate('motherboard', _mb_fits_mem)
                if new_mb:
                    selected_parts['motherboard'] = new_mb
                else:
                    break
            else:
                break

        elif issue == 'psu_too_weak':
            required_w = _required_power_w(usage)
            new_psu = _pick_candidate('psu', lambda p: int(_get_spec(p, 'wattage', 0)) >= required_w)
            if new_psu:
                selected_parts['psu'] = new_psu
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

    changed = True
    while changed and total_price > budget:
        changed = False
        for part_type, current in sorted(selected_parts.items(), key=lambda item: item[1].price if item[1] else 0, reverse=True):
            if current is None:
                continue

            cheaper = None
            for candidate in PCPart.objects.filter(part_type=part_type, price__lt=current.price).order_by('-price'):
                if _is_part_suitable(part_type, candidate) and _matches_selection_options(part_type, candidate, options=options):
                    cheaper = candidate
                    break
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

    preferred = _memory_profile_pick(candidates, 'spec')
    upgraded_memory = preferred or candidates[-1]

    adjusted = dict(selected_parts)
    adjusted['memory'] = upgraded_memory
    return adjusted, _sum_selected_price(adjusted)


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
        preferred = [p for p in candidates if _is_gaming_spec_gpu_preferred(p)]
        return preferred or candidates

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
        'cpu': 0.14 if usage in {'gaming', 'creator'} else 0.10,
        'motherboard': 0.08,
        'memory': 0.05,
        'storage': 0.05,
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

    motherboard_part = selected_parts.get('motherboard')
    if motherboard_part:
        mb_mem_type = _infer_motherboard_memory_type(motherboard_part)
        if mb_mem_type:
            updated['motherboard_memory_type'] = mb_mem_type
        else:
            updated.pop('motherboard_memory_type', None)

    return updated


def build_configuration_response(
    budget,
    usage,
    cooler_type='any',
    radiator_size='any',
    cooling_profile='balanced',
    case_size='any',
    cpu_vendor='any',
    build_priority='balanced',
    custom_budget_weights=None,
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
        cpu_vendor=cpu_vendor,
        build_priority=build_priority,
    )

    if usage == 'gaming' and selection_options.get('build_priority') == 'spec':
        # gaming + spec はストレージ容量を優先し、最低1TBを目標にする。
        selection_options = dict(selection_options)
        selection_options['min_storage_capacity_gb'] = 1000
        selection_options['require_preferred_gaming_gpu'] = True

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
    total_price = _sum_selected_price(selected_parts)

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

    estimated_power = IGPU_POWER_MAP.get(usage, USAGE_POWER_MAP[usage]) if use_igpu else USAGE_POWER_MAP[usage]

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
        'cpu_vendor': selection_options['cpu_vendor'],
        'build_priority': selection_options['build_priority'],
        'custom_budget_weights': normalized_custom_budget_weights,
        'configuration_id': configuration.id,
        'total_price': total_price,
        'estimated_power_w': estimated_power,
        'parts': selected,
    }, None


def build_scraper_status_summary():
    latest = ScraperStatus.objects.order_by('-updated_at').first()
    total_parts = PCPart.objects.count()
    cached_categories = sorted(list(set(PCPart.objects.values_list('part_type', flat=True))))

    return {
        'cache_enabled': latest.cache_enabled if latest else True,
        'cache_ttl_seconds': latest.cache_ttl_seconds if latest else 3600,
        'last_update_time': latest.updated_at.isoformat() if latest else None,
        'cached_categories': cached_categories,
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
        for part_field in ['cpu', 'cpu_cooler', 'gpu', 'motherboard', 'memory', 'storage', 'psu', 'case']:
            part = getattr(config, part_field)
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
            request.data.get('cpu_vendor'),
            request.data.get('build_priority'),
            request.data.get('custom_budget_weights'),
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
            request.data.get('cpu_vendor'),
            request.data.get('build_priority'),
            request.data.get('custom_budget_weights'),
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
    'psu':         '電源ユニット',
    'case':        'PCケース',
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

