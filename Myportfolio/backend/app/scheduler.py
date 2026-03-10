import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .repository import update_parts_from_web

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def schedule_parts_update(db_factory) -> None:
    """
    パーツ情報を定期的に更新するスケジューラー.
    24時間ごとに実行.
    """
    def update_task():
        try:
            db = db_factory()
            update_parts_from_web(db)
            logger.info("Scheduled parts update completed.")
        except Exception as e:
            logger.error(f"Scheduled parts update failed: {e}")
        finally:
            db.close()

    scheduler.add_job(
        update_task,
        "interval",
        hours=24,
        id="parts_update",
        name="Update PC parts from web",
    )

    if not scheduler.running:
        scheduler.start()
        logger.info("Parts update scheduler started.")


def stop_scheduler() -> None:
    """スケジューラーを停止."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Parts update scheduler stopped.")
