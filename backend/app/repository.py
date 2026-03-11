import logging
from datetime import datetime

from sqlalchemy.orm import Session

from .models_db import Part as DBPart
from .scraper import ConfigScraper, ScrapingConfig

logger = logging.getLogger(__name__)


# グローバルスクレイパー状態
class ScraperStateManager:
    """スクレイパーの状態を管理."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.scraper = ConfigScraper(config=ScrapingConfig())
            cls._instance.last_update_time: datetime | None = None
            cls._instance.total_parts_cached = {}
        return cls._instance
    
    def update_scrape_time(self):
        """最後のスクレイピング時刻を更新."""
        self.last_update_time = datetime.now()
    
    def get_status(self) -> dict:
        """現在の状態を返す."""
        return {
            "cache_enabled": self.scraper.config.cache_enabled,
            "cache_ttl_seconds": self.scraper.config.cache_ttl,
            "last_update_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "cached_categories": list(self.scraper._cache.keys()),
            "retry_count": self.scraper.config.retry_count,
            "rate_limit_delay": self.scraper.config.rate_limit_delay,
        }


def get_scraper_state_manager() -> ScraperStateManager:
    """スクレイパー状態マネージャーを取得."""
    return ScraperStateManager()


class PartRepository:
    """パーツ情報の DB 操作."""

    def __init__(self, db: Session):
        self.db = db

    def upsert_parts(self, parts_data: list[dict]) -> int:
        """パーツ情報を作成または更新."""
        count = 0
        for part in parts_data:
            existing = self.db.query(DBPart).filter_by(part_id=part["part_id"]).first()
            if existing:
                for key, value in part.items():
                    setattr(existing, key, value)
                logger.info(f"Updated: {part['part_id']}")
            else:
                new_part = DBPart(**part)
                self.db.add(new_part)
                logger.info(f"Created: {part['part_id']}")
            count += 1
        self.db.commit()
        return count

    def get_parts_by_category(self, category: str) -> list[DBPart]:
        """カテゴリ別にパーツを取得."""
        return self.db.query(DBPart).filter_by(category=category).all()

    def get_all_parts(self) -> list[DBPart]:
        """全パーツを取得."""
        return self.db.query(DBPart).all()

    def search_by_socket(self, socket: str) -> list[DBPart]:
        """ソケット別に検索."""
        return self.db.query(DBPart).filter_by(socket=socket).all()

    def search_by_memory_standard(self, standard: str) -> list[DBPart]:
        """メモリ規格別に検索."""
        return self.db.query(DBPart).filter_by(memory_standard=standard).all()


def update_parts_from_web(db: Session) -> dict:
    """Web からパーツ情報をスクレイピングして DB に保存."""
    state_manager = get_scraper_state_manager()
    scraper = state_manager.scraper
    
    scraped = scraper.scrape_all()
    repo = PartRepository(db)

    results = {}
    for category, parts_list in scraped.items():
        count = repo.upsert_parts(parts_list)
        results[category] = count
    
    # スクレイピング時刻を更新
    state_manager.update_scrape_time()
    state_manager.total_parts_cached = results

    logger.info(f"Update complete: {results}")
    return results
