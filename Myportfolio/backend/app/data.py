from .models import Part


CPUS = [
    Part(
        id="cpu-12400f",
        category="cpu",
        name="Intel Core i5-12400F",
        price=21000,
        performance_score=79,
        socket="LGA1700",
        wattage=65,
        url="https://example.com/cpu-12400f",
    ),
    Part(
        id="cpu-7600",
        category="cpu",
        name="AMD Ryzen 5 7600",
        price=31000,
        performance_score=88,
        socket="AM5",
        wattage=65,
        url="https://example.com/cpu-7600",
    ),
]

GPUS = [
    Part(
        id="gpu-4060",
        category="gpu",
        name="GeForce RTX 4060",
        price=49000,
        performance_score=86,
        wattage=115,
        url="https://example.com/gpu-4060",
    ),
    Part(
        id="gpu-7600xt",
        category="gpu",
        name="Radeon RX 7600 XT",
        price=47000,
        performance_score=83,
        wattage=190,
        url="https://example.com/gpu-7600xt",
    ),
]

MOTHERBOARDS = [
    Part(
        id="mb-b760m",
        category="motherboard",
        name="B760M DDR4",
        price=17000,
        performance_score=70,
        socket="LGA1700",
        memory_standard="DDR4",
        form_factor="mATX",
        url="https://example.com/mb-b760m",
    ),
    Part(
        id="mb-b650m",
        category="motherboard",
        name="B650M DDR5",
        price=22000,
        performance_score=78,
        socket="AM5",
        memory_standard="DDR5",
        form_factor="mATX",
        url="https://example.com/mb-b650m",
    ),
]

MEMORIES = [
    Part(
        id="mem-ddr4-16",
        category="memory",
        name="DDR4 16GB (8x2)",
        price=7000,
        performance_score=58,
        memory_standard="DDR4",
        memory_capacity_gb=16,
        url="https://example.com/mem-ddr4-16",
    ),
    Part(
        id="mem-ddr5-32",
        category="memory",
        name="DDR5 32GB (16x2)",
        price=14500,
        performance_score=83,
        memory_standard="DDR5",
        memory_capacity_gb=32,
        url="https://example.com/mem-ddr5-32",
    ),
]

STORAGES = [
    Part(
        id="ssd-1tb",
        category="storage",
        name="NVMe SSD 1TB",
        price=9800,
        performance_score=72,
        storage_capacity_gb=1000,
        url="https://example.com/ssd-1tb",
    ),
    Part(
        id="ssd-2tb",
        category="storage",
        name="NVMe SSD 2TB",
        price=16500,
        performance_score=81,
        storage_capacity_gb=2000,
        url="https://example.com/ssd-2tb",
    ),
]

PSUS = [
    Part(
        id="psu-650",
        category="psu",
        name="650W 80+ Bronze",
        price=9000,
        performance_score=62,
        wattage=650,
        url="https://example.com/psu-650",
    ),
    Part(
        id="psu-750",
        category="psu",
        name="750W 80+ Gold",
        price=12800,
        performance_score=76,
        wattage=750,
        url="https://example.com/psu-750",
    ),
]

CASES = [
    Part(
        id="case-mini",
        category="case",
        name="Compact mATX Case",
        price=7800,
        performance_score=60,
        supported_form_factors=("mATX", "ITX"),
        url="https://example.com/case-mini",
    ),
    Part(
        id="case-mid",
        category="case",
        name="Mid Tower Case",
        price=10500,
        performance_score=74,
        supported_form_factors=("ATX", "mATX", "ITX"),
        url="https://example.com/case-mid",
    ),
]
