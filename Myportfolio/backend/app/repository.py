import logging

from sqlalchemy.orm import Session

from .models_db import Part as DBPart
from .scraper import ConfigScraper

logger = logging.getLogger(__name__)


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
    scraper = ConfigScraper()
    scraped = scraper.scrape_all()
    repo = PartRepository(db)

    results = {}
    for category, parts_list in scraped.items():
        count = repo.upsert_parts(parts_list)
        results[category] = count

    logger.info(f"Update complete: {results}")
    return results
