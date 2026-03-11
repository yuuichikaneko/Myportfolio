import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .algorithm import generate_configuration
from .db import engine, SessionLocal
from .models import GenerateConfigRequest, GenerateConfigResponse, ScraperStatus
from .models_db import Part as DBPart
from .repository import update_parts_from_web, get_scraper_state_manager
from .scheduler import schedule_parts_update, stop_scheduler

logger = logging.getLogger(__name__)

app = FastAPI(title="PC Config Generator API", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """アプリ起動時に DB を初期化してパーツを取得."""
    logger.info("Initializing database...")
    DBPart.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # DB が空なら初期スクレイピング
        parts_count = db.query(DBPart).count()
        if parts_count == 0:
            logger.info("Database is empty. Running initial scrape...")
            update_parts_from_web(db)
    finally:
        db.close()
    
    # スケジューラー起動
    schedule_parts_update(SessionLocal)
    logger.info("Startup complete.")


@app.on_event("shutdown")
def shutdown_event():
    """アプリシャットダウン時処理."""
    logger.info("Shutting down...")
    stop_scheduler()


@app.get("/")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/scraper/status", response_model=ScraperStatus)
def get_scraper_status() -> ScraperStatus:
    """スクレイパーの状態をレスポンス."""
    state_manager = get_scraper_state_manager()
    status_dict = state_manager.get_status()
    
    # データベースの合計パーツ数を取得
    db = SessionLocal()
    try:
        total_parts = db.query(DBPart).count()
    finally:
        db.close()
    
    return ScraperStatus(
        cache_enabled=status_dict["cache_enabled"],
        cache_ttl_seconds=status_dict["cache_ttl_seconds"],
        last_update_time=status_dict["last_update_time"],
        cached_categories=status_dict["cached_categories"],
        total_parts_in_db=total_parts,
        retry_count=status_dict["retry_count"],
        rate_limit_delay=status_dict["rate_limit_delay"],
    )


@app.post("/generate-config", response_model=GenerateConfigResponse)
def generate_config(payload: GenerateConfigRequest) -> GenerateConfigResponse:
    config = generate_configuration(budget=payload.budget, usage=payload.usage)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="No compatible configuration found under the specified budget.",
        )
    return config
