import logging

from requests import Session

logger = logging.getLogger(__name__)


class ConfigScraper:
    """
    PC パーツ情報スクレイパー.
    実装例として価格ドットコムをターゲットにしていますが、
    実装はベストプラクティスに従う必要があります。
    """

    def __init__(self, session: Session | None = None):
        self.session = session or Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def scrape_cpus(self) -> list[dict]:
        """
        CPU 情報をスクレイピング.
        価格ドットコムの利用規約に準拠する実装後に置き換え.
        """
        logger.info("Scraping CPUs from kakaku.com...")
        return [
            {
                "part_id": "cpu-12400f-web",
                "category": "cpu",
                "name": "Intel Core i5-12400F (Web)",
                "price": 20500,
                "performance_score": 80,
                "socket": "LGA1700",
                "wattage": 65,
                "url": "https://example.com/cpu-12400f",
            },
            {
                "part_id": "cpu-13400f-web",
                "category": "cpu",
                "name": "Intel Core i5-13400F (Web)",
                "price": 29800,
                "performance_score": 88,
                "socket": "LGA1700",
                "wattage": 65,
                "url": "https://example.com/cpu-13400f",
            },
            {
                "part_id": "cpu-7600-web",
                "category": "cpu",
                "name": "AMD Ryzen 5 7600 (Web)",
                "price": 32200,
                "performance_score": 90,
                "socket": "AM5",
                "wattage": 65,
                "url": "https://example.com/cpu-7600",
            },
            {
                "part_id": "cpu-7700-web",
                "category": "cpu",
                "name": "AMD Ryzen 7 7700 (Web)",
                "price": 45800,
                "performance_score": 101,
                "socket": "AM5",
                "wattage": 65,
                "url": "https://example.com/cpu-7700",
            },
            {
                "part_id": "cpu-13600k-web",
                "category": "cpu",
                "name": "Intel Core i5-13600K (Web)",
                "price": 49800,
                "performance_score": 106,
                "socket": "LGA1700",
                "wattage": 125,
                "url": "https://example.com/cpu-13600k",
            },
        ]

    def scrape_gpus(self) -> list[dict]:
        """GPU 情報をスクレイピング."""
        logger.info("Scraping GPUs from kakaku.com...")
        return [
            {
                "part_id": "gpu-4060-web",
                "category": "gpu",
                "name": "GeForce RTX 4060 (Web)",
                "price": 48500,
                "performance_score": 87,
                "wattage": 115,
                "url": "https://example.com/gpu-4060",
            },
            {
                "part_id": "gpu-4060ti-web",
                "category": "gpu",
                "name": "GeForce RTX 4060 Ti (Web)",
                "price": 65800,
                "performance_score": 96,
                "wattage": 160,
                "url": "https://example.com/gpu-4060ti",
            },
            {
                "part_id": "gpu-4070-web",
                "category": "gpu",
                "name": "GeForce RTX 4070 (Web)",
                "price": 86800,
                "performance_score": 108,
                "wattage": 200,
                "url": "https://example.com/gpu-4070",
            },
            {
                "part_id": "gpu-4070super-web",
                "category": "gpu",
                "name": "GeForce RTX 4070 SUPER (Web)",
                "price": 102800,
                "performance_score": 116,
                "wattage": 220,
                "url": "https://example.com/gpu-4070super",
            },
            {
                "part_id": "gpu-4080-web",
                "category": "gpu",
                "name": "GeForce RTX 4080 (Web)",
                "price": 164800,
                "performance_score": 136,
                "wattage": 320,
                "url": "https://example.com/gpu-4080",
            },
        ]

    def scrape_motherboards(self) -> list[dict]:
        """マザーボード情報をスクレイピング."""
        logger.info("Scraping Motherboards from kakaku.com...")
        return [
            {
                "part_id": "mb-b760m-web",
                "category": "motherboard",
                "name": "B760M DDR4 (Web)",
                "price": 16800,
                "performance_score": 71,
                "socket": "LGA1700",
                "memory_standard": "DDR4",
                "form_factor": "mATX",
                "url": "https://example.com/mb-b760m",
            },
            {
                "part_id": "mb-b760-atx-web",
                "category": "motherboard",
                "name": "B760 ATX DDR5 (Web)",
                "price": 24800,
                "performance_score": 80,
                "socket": "LGA1700",
                "memory_standard": "DDR5",
                "form_factor": "ATX",
                "url": "https://example.com/mb-b760-atx",
            },
            {
                "part_id": "mb-b650m-web",
                "category": "motherboard",
                "name": "B650M DDR5 (Web)",
                "price": 22600,
                "performance_score": 79,
                "socket": "AM5",
                "memory_standard": "DDR5",
                "form_factor": "mATX",
                "url": "https://example.com/mb-b650m",
            },
            {
                "part_id": "mb-x670-web",
                "category": "motherboard",
                "name": "X670 ATX DDR5 (Web)",
                "price": 39800,
                "performance_score": 93,
                "socket": "AM5",
                "memory_standard": "DDR5",
                "form_factor": "ATX",
                "url": "https://example.com/mb-x670",
            },
            {
                "part_id": "mb-z790-web",
                "category": "motherboard",
                "name": "Z790 ATX DDR5 (Web)",
                "price": 42800,
                "performance_score": 95,
                "socket": "LGA1700",
                "memory_standard": "DDR5",
                "form_factor": "ATX",
                "url": "https://example.com/mb-z790",
            },
        ]

    def scrape_memories(self) -> list[dict]:
        """メモリ情報をスクレイピング."""
        logger.info("Scraping Memory from kakaku.com...")
        return [
            {
                "part_id": "mem-ddr4-16-web",
                "category": "memory",
                "name": "DDR4 16GB (8x2) (Web)",
                "price": 6800,
                "performance_score": 59,
                "memory_standard": "DDR4",
                "memory_capacity_gb": 16,
                "url": "https://example.com/mem-ddr4-16",
            },
            {
                "part_id": "mem-ddr5-32-web",
                "category": "memory",
                "name": "DDR5 32GB (16x2) (Web)",
                "price": 14900,
                "performance_score": 83,
                "memory_standard": "DDR5",
                "memory_capacity_gb": 32,
                "url": "https://example.com/mem-ddr5-32",
            },
            {
                "part_id": "mem-ddr5-64-web",
                "category": "memory",
                "name": "DDR5 64GB (32x2) (Web)",
                "price": 26800,
                "performance_score": 95,
                "memory_standard": "DDR5",
                "memory_capacity_gb": 64,
                "url": "https://example.com/mem-ddr5-64",
            },
            {
                "part_id": "mem-ddr5-96-web",
                "category": "memory",
                "name": "DDR5 96GB (48x2) (Web)",
                "price": 41800,
                "performance_score": 102,
                "memory_standard": "DDR5",
                "memory_capacity_gb": 96,
                "url": "https://example.com/mem-ddr5-96",
            },
            {
                "part_id": "mem-ddr4-32-web",
                "category": "memory",
                "name": "DDR4 32GB (16x2) (Web)",
                "price": 12800,
                "performance_score": 72,
                "memory_standard": "DDR4",
                "memory_capacity_gb": 32,
                "url": "https://example.com/mem-ddr4-32",
            },
        ]

    def scrape_storages(self) -> list[dict]:
        """ストレージ情報をスクレイピング."""
        logger.info("Scraping Storage from kakaku.com...")
        return [
            {
                "part_id": "ssd-1tb-web",
                "category": "storage",
                "name": "NVMe SSD 1TB (Web)",
                "price": 9500,
                "performance_score": 73,
                "storage_capacity_gb": 1000,
                "url": "https://example.com/ssd-1tb",
            },
            {
                "part_id": "ssd-2tb-web",
                "category": "storage",
                "name": "NVMe SSD 2TB (Web)",
                "price": 17200,
                "performance_score": 82,
                "storage_capacity_gb": 2000,
                "url": "https://example.com/ssd-2tb",
            },
            {
                "part_id": "ssd-4tb-web",
                "category": "storage",
                "name": "NVMe SSD 4TB (Web)",
                "price": 33800,
                "performance_score": 91,
                "storage_capacity_gb": 4000,
                "url": "https://example.com/ssd-4tb",
            },
            {
                "part_id": "ssd-500gb-web",
                "category": "storage",
                "name": "NVMe SSD 500GB (Web)",
                "price": 6200,
                "performance_score": 64,
                "storage_capacity_gb": 500,
                "url": "https://example.com/ssd-500gb",
            },
            {
                "part_id": "ssd-8tb-web",
                "category": "storage",
                "name": "NVMe SSD 8TB (Web)",
                "price": 77800,
                "performance_score": 104,
                "storage_capacity_gb": 8000,
                "url": "https://example.com/ssd-8tb",
            },
        ]

    def scrape_psus(self) -> list[dict]:
        """PSU 情報をスクレイピング."""
        logger.info("Scraping PSU from kakaku.com...")
        return [
            {
                "part_id": "psu-650-web",
                "category": "psu",
                "name": "650W 80+ Bronze (Web)",
                "price": 8800,
                "performance_score": 63,
                "wattage": 650,
                "url": "https://example.com/psu-650",
            },
            {
                "part_id": "psu-750-web",
                "category": "psu",
                "name": "750W 80+ Gold (Web)",
                "price": 13200,
                "performance_score": 78,
                "wattage": 750,
                "url": "https://example.com/psu-750",
            },
            {
                "part_id": "psu-850-web",
                "category": "psu",
                "name": "850W 80+ Gold (Web)",
                "price": 16500,
                "performance_score": 84,
                "wattage": 850,
                "url": "https://example.com/psu-850",
            },
            {
                "part_id": "psu-550-web",
                "category": "psu",
                "name": "550W 80+ Bronze (Web)",
                "price": 6900,
                "performance_score": 56,
                "wattage": 550,
                "url": "https://example.com/psu-550",
            },
            {
                "part_id": "psu-1000-web",
                "category": "psu",
                "name": "1000W 80+ Platinum (Web)",
                "price": 26800,
                "performance_score": 96,
                "wattage": 1000,
                "url": "https://example.com/psu-1000",
            },
        ]

    def scrape_cases(self) -> list[dict]:
        """ケース情報をスクレイピング."""
        logger.info("Scraping Cases from kakaku.com...")
        return [
            {
                "part_id": "case-mini-web",
                "category": "case",
                "name": "Compact mATX Case (Web)",
                "price": 7600,
                "performance_score": 61,
                "supported_form_factors": "mATX,ITX",
                "url": "https://example.com/case-mini",
            },
            {
                "part_id": "case-mid-web",
                "category": "case",
                "name": "Mid Tower Airflow Case (Web)",
                "price": 10800,
                "performance_score": 74,
                "supported_form_factors": "ATX,mATX,ITX",
                "url": "https://example.com/case-mid",
            },
            {
                "part_id": "case-premium-web",
                "category": "case",
                "name": "Premium Silent Tower Case (Web)",
                "price": 18200,
                "performance_score": 86,
                "supported_form_factors": "ATX,mATX,ITX",
                "url": "https://example.com/case-premium",
            },
            {
                "part_id": "case-budget-web",
                "category": "case",
                "name": "Budget mATX Case (Web)",
                "price": 5200,
                "performance_score": 51,
                "supported_form_factors": "mATX,ITX",
                "url": "https://example.com/case-budget",
            },
            {
                "part_id": "case-full-web",
                "category": "case",
                "name": "Full Tower Showcase Case (Web)",
                "price": 25800,
                "performance_score": 94,
                "supported_form_factors": "ATX,mATX,ITX",
                "url": "https://example.com/case-full",
            },
        ]

    def scrape_all(self) -> dict[str, list[dict]]:
        """全パーツ情報をスクレイピング."""
        logger.info("Starting full scrape cycle...")
        return {
            "cpus": self.scrape_cpus(),
            "gpus": self.scrape_gpus(),
            "motherboards": self.scrape_motherboards(),
            "memories": self.scrape_memories(),
            "storages": self.scrape_storages(),
            "psus": self.scrape_psus(),
            "cases": self.scrape_cases(),
        }
