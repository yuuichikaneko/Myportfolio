from dataclasses import dataclass

from .db import SessionLocal
from .models import GenerateConfigResponse, Part, PartResponse, UsageType


USAGE_WEIGHTS = {
    UsageType.GAMING: {
        "cpu": 0.23,
        "gpu": 0.39,
        "motherboard": 0.12,
        "memory": 0.08,
        "storage": 0.08,
        "psu": 0.05,
        "case": 0.05,
    },
    UsageType.VIDEO_EDITING: {
        "cpu": 0.3,
        "gpu": 0.24,
        "motherboard": 0.12,
        "memory": 0.14,
        "storage": 0.1,
        "psu": 0.05,
        "case": 0.05,
    },
    UsageType.GENERAL: {
        "cpu": 0.27,
        "gpu": 0.18,
        "motherboard": 0.15,
        "memory": 0.12,
        "storage": 0.13,
        "psu": 0.08,
        "case": 0.07,
    },
}


@dataclass(frozen=True)
class Candidate:
    parts: tuple[Part, ...]
    total_price: int
    score: float
    estimated_power_w: int


def generate_configuration(budget: int, usage: UsageType) -> GenerateConfigResponse | None:
    """
    DB 内のパーツから構成を生成.
    DB が空の場合は None を返す.
    """
    db = SessionLocal()
    try:
        from .repository import PartRepository
        repo = PartRepository(db)
        db_parts = repo.get_all_parts()

        if not db_parts:
            return None

        # DBパーツを domain Part に変換
        parts_dict = {}
        for part in db_parts:
            domain_part = Part(
                id=part.part_id,
                category=part.category,
                name=part.name,
                price=part.price,
                performance_score=part.performance_score,
                url=part.url,
                socket=part.socket,
                memory_standard=part.memory_standard,
                memory_capacity_gb=part.memory_capacity_gb,
                storage_capacity_gb=part.storage_capacity_gb,
                wattage=part.wattage,
                form_factor=part.form_factor,
                supported_form_factors=tuple(
                    part.supported_form_factors.split(",") if part.supported_form_factors else []
                ),
            )
            if part.category not in parts_dict:
                parts_dict[part.category] = []
            parts_dict[part.category].append(domain_part)

        cpus = parts_dict.get("cpu", [])
        gpus = parts_dict.get("gpu", [])
        motherboards = parts_dict.get("motherboard", [])
        memories = parts_dict.get("memory", [])
        storages = parts_dict.get("storage", [])
        psus = parts_dict.get("psu", [])
        cases = parts_dict.get("case", [])

        if not all([cpus, gpus, motherboards, memories, storages, psus, cases]):
            return None

        best_candidate = None

        for cpu in cpus:
            for motherboard in motherboards:
                if not _is_cpu_motherboard_compatible(cpu, motherboard):
                    continue

                for memory in memories:
                    if not _is_memory_compatible(memory, motherboard):
                        continue

                    for gpu in gpus:
                        for storage in storages:
                            estimated_power = _estimate_power(cpu, gpu)

                            for psu in psus:
                                if not _is_psu_compatible(psu, estimated_power):
                                    continue

                                for case in cases:
                                    if not _is_case_compatible(case, motherboard):
                                        continue

                                    parts = (cpu, gpu, motherboard, memory, storage, psu, case)
                                    total_price = sum(part.price for part in parts)
                                    if total_price > budget:
                                        continue

                                    score = _score_build(parts, budget, usage)
                                    candidate = Candidate(
                                        parts=parts,
                                        total_price=total_price,
                                        score=score,
                                        estimated_power_w=estimated_power,
                                    )
                                    best_candidate = _pick_better(best_candidate, candidate)

        if best_candidate is None:
            return None

        visible_categories = {"cpu", "gpu", "memory", "storage", "psu", "case"}
        response_parts = [
            PartResponse(
                category=part.category,
                name=part.name,
                price=part.price,
                url=part.url,
            )
            for part in best_candidate.parts
            if part.category in visible_categories
        ]

        return GenerateConfigResponse(
            usage=usage,
            budget=budget,
            total_price=best_candidate.total_price,
            estimated_power_w=best_candidate.estimated_power_w,
            parts=response_parts,
        )
    finally:
        db.close()


def _pick_better(current: Candidate | None, incoming: Candidate) -> Candidate:
    if current is None:
        return incoming
    if incoming.score > current.score:
        return incoming
    if incoming.score == current.score and incoming.total_price > current.total_price:
        return incoming
    return current


def _is_cpu_motherboard_compatible(cpu: Part, motherboard: Part) -> bool:
    return cpu.socket is not None and cpu.socket == motherboard.socket


def _is_memory_compatible(memory: Part, motherboard: Part) -> bool:
    return memory.memory_standard is not None and memory.memory_standard == motherboard.memory_standard


def _is_psu_compatible(psu: Part, estimated_power: int) -> bool:
    if psu.wattage is None:
        return False
    required = int(estimated_power * 1.3)
    return psu.wattage >= required


def _is_case_compatible(case: Part, motherboard: Part) -> bool:
    return motherboard.form_factor is not None and motherboard.form_factor in case.supported_form_factors


def _estimate_power(cpu: Part, gpu: Part) -> int:
    base = 120
    return base + (cpu.wattage or 65) + (gpu.wattage or 150)


def _score_build(parts: tuple[Part, ...], budget: int, usage: UsageType) -> float:
    weights = USAGE_WEIGHTS[usage]
    part_map = {part.category: part for part in parts}

    weighted_performance = 0.0
    for part in parts:
        if part.category in weights:
            weighted_performance += part.performance_score * weights[part.category]

    total_price = sum(part.price for part in parts)
    budget_efficiency = total_price / budget

    price_score = max(0.0, 1.0 - abs(0.92 - budget_efficiency))
    usage_bonus = _usage_specific_bonus(usage, part_map)
    return weighted_performance * 10 + price_score * 20 + usage_bonus


def _usage_specific_bonus(usage: UsageType, part_map: dict[str, Part]) -> float:
    gpu = part_map.get("gpu")
    memory = part_map.get("memory")
    storage = part_map.get("storage")
    cpu = part_map.get("cpu")

    if usage == UsageType.GAMING:
        # Gaming prefers GPU-first builds with enough memory headroom.
        gpu_bonus = (gpu.performance_score if gpu else 0) * 1.2
        mem_bonus = (memory.memory_capacity_gb or 0) * 0.15 if memory else 0
        return gpu_bonus + mem_bonus

    if usage == UsageType.VIDEO_EDITING:
        # Video editing favors CPU throughput, large memory, and storage capacity.
        cpu_bonus = (cpu.performance_score if cpu else 0) * 0.8
        mem_bonus = (memory.memory_capacity_gb or 0) * 0.6 if memory else 0
        storage_bonus = ((storage.storage_capacity_gb or 0) / 1000) * 4 if storage else 0
        return cpu_bonus + mem_bonus + storage_bonus

    # General usage rewards balanced, efficient systems over extreme specs.
    cpu_score = cpu.performance_score if cpu else 0
    gpu_score = gpu.performance_score if gpu else 0
    balance_penalty = abs(cpu_score - gpu_score) * 0.15
    efficiency_bonus = 18.0
    return efficiency_bonus - balance_penalty
