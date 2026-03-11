# Backend (FastAPI)

## Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Or from project root:
```bash
python -m uvicorn backend.app.main:app --reload
```

## Database
- **Development**: SQLite (`config_generator.db`)
- **Production**: PostgreSQL (configure via environment variable)

### Initialize DB
Database schema is auto-created on startup.
Mock part data is loaded from scraper on first run.

## API

### Healthcheck
- `GET /`

Response example:
```json
{
  "status": "ok"
}
```

### Generate Config
- `POST /generate-config`

Request example:
```json
{
  "budget": 150000,
  "usage": "gaming"
}
```

Response example:
```json
{
  "usage": "gaming",
  "budget": 150000,
  "total_price": 118500,
  "estimated_power_w": 300,
  "parts": [
    {
      "category": "cpu",
      "name": "Intel Core i5-12400F (Web)",
      "price": 20500,
      "url": "https://example.com/cpu-12400f"
    }
  ]
}
```

## Architecture

### Modules

| Module | Purpose |
|--------|---------|
| `models.py` | Pydantic request/response models |
| `models_db.py` | SQLAlchemy ORM models |
| `db.py` | Database connection & session factory |
| `scraper.py` | PC part web scraper (BeautifulSoup/Requests) |
| `repository.py` | Data access layer for parts |
| `algorithm.py` | Configuration generation algorithm (using DB parts) |
| `scheduler.py` | APScheduler for periodic scraping (24h interval) |
| `main.py` | FastAPI app & lifecycle management |

### Data Flow

```
User Request
    ↓
POST /generate-config
    ↓
algorithm.py (generate_configuration)
    ↓
repository.py (fetch parts from DB)
    ↓
Compatibility check & scoring
    ↓
response (JSON parts list + total price)
```

### Scraping Flow (Background)

```
startup_event triggered
    ↓
Create DB schema
    ↓
Initial scrape (if DB empty)
    ↓
Start scheduler (24h interval)
    ↓
Periodically call scraper.py → repository.py
    ↓
Update DB parts
```

## Next Steps

1. Implement actual web scraper for kakaku.com
   - Respect robots.txt & rate limiting
   - Parse CPU/GPU/Storage prices
   - Handle pagination & error recovery

2. Production DB setup
   - PostgreSQL connection string via `DATABASE_URL` env var
   - Connection pooling (SQLAlchemy connection.pool)

3. Frontend (React)
   - Budget input form
   - Usage selection
   - Display generated config results

4. Deployment
   - Docker containerization
   - AWS EC2/RDS or Vercel/Supabase

