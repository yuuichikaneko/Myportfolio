# Myportfolio

## Documents
- Requirements: `docs/requirements.md`
- Frontend: `frontend/README.md`
- Django: `django/`
- Django packages: `django/DJANGO_INSTALLED_PACKAGES.txt`
- FastAPI: moved to `F:\Python\Myportfolio_FastAPI\backend`

## Project Split
- FastAPI files: `F:\Python\Myportfolio_FastAPI\backend`
- Django files: `django/`
- FastAPI helper scripts: `F:\Python\Myportfolio_FastAPI\backend\scripts`

## Quick Start

### Backend (FastAPI)
```bash
cd F:\Python\Myportfolio_FastAPI\backend
python -m uvicorn app.main:app --reload
```
Runs on `http://localhost:8000`

### Django
```bash
cd django
python manage.py runserver 8001
```
Runs on `http://localhost:8001`

#### PostgreSQL migration preparation (Django)
1. Install/update Django dependencies:
```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe -m pip install -r django/django_requirements.txt
```
2. Create `django/.env` from `django/.env.postgresql.example` and set DB values.
	- On Windows, keep `DB_CLIENT_ENCODING=UTF8` to avoid psycopg2 decode errors.
	- Set `DJANGO_SECRET_KEY` (required). Example generation:
	  `f:/Python/Myportfolio/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(64))"`
3. Run migrations:
```bash
cd django
f:/Python/Myportfolio/.venv/Scripts/python.exe manage.py migrate
```
4. Verify DB connection:
```bash
cd django
f:/Python/Myportfolio/.venv/Scripts/python.exe manage.py showmigrations
```

If `DB_ENGINE` is not set to `postgresql`, Django continues to use SQLite.

#### PostgreSQL freeze mitigation and diagnostics
Operations tools policy (portfolio scope):

- Local administrator use only. Do not expose these tools via HTTP endpoints.
- Manual operations only. Do not run automatically from normal app flows.
- Restrict execution rights on shared environments to designated operators.
- Keep disabled by default in production; enable only when needed for incident response.

Target tools:

- `postgres_pg_activity.py`
- `safe_postgres_migrate.ps1`
- `postgres_freeze_watch.ps1`

Add or tune these variables in `django/.env` when using PostgreSQL:

```bash
DB_CONNECT_TIMEOUT=5
DB_STATEMENT_TIMEOUT_MS=15000
DB_LOCK_TIMEOUT_MS=5000
DB_IDLE_IN_TX_TIMEOUT_MS=10000
```

Quick diagnostics from repo root:

```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action snapshot --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action blockers --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action locks --env-path django/.env
```

Timeout-guarded migration (recommended to avoid long VS Code hangs):

```powershell
./safe_postgres_migrate.ps1 -TimeoutSec 300 -EnvPath django/.env
```

One-shot auto-unfreeze mode (timeout -> detect idle blockers -> terminate -> retry once):

```powershell
./safe_postgres_migrate.ps1 -TimeoutSec 180 -AutoTerminateIdleBlockers -MinIdleTxSec 30 -RetryTimeoutSec 180 -EnvPath django/.env
```

Or run it from VS Code task: `PostgreSQL Safe Migrate`.

PowerShell helper (uses psql):

```powershell
./postgres_pg_activity_tools.ps1 -Action snapshot -EnvPath .\django\.env
./postgres_pg_activity_tools.ps1 -Action blockers -EnvPath .\django\.env
```

Continuous freeze watcher (captures blockers/locks/snapshot repeatedly to a log file):

```powershell
./postgres_freeze_watch.ps1 -EnvPath django/.env -DurationSec 300 -IntervalSec 2
```

When a blocker PID is identified, use cancel first, then terminate only if needed:

```bash
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action cancel --target-pid <PID> --env-path django/.env
f:/Python/Myportfolio/.venv/Scripts/python.exe postgres_pg_activity.py --action terminate --target-pid <PID> --env-path django/.env
```

Windows helper scripts:
- `start_django.bat`
- `start_django.ps1`
- `start_django_frontend.bat`
- `start_django_frontend.ps1`

`start_django_frontend.bat` / `start_django_frontend.ps1` launches all of the following:
- Django server (8001)
- Frontend dev server (auto-selected port)
- Celery Worker (auto scraper)
- Celery Beat (scheduler)

If Redis is not running on `127.0.0.1:6379`, the scripts try to start `redis-server` when available.

### Frontend (React via Vite)
```bash
cd frontend
npm install
npm run dev
```
Runs on `http://127.0.0.1:5173` (or next free port)

### Frontend (CDN Alternative - No Node.js required)
Open `frontend/index-cdn.html` in a browser or serve with:
```bash
python -m http.server -d frontend 8080
# Open http://localhost:8080/index-cdn.html
```