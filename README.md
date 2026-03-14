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

Windows helper scripts:
- `start_django.bat`
- `start_django.ps1`
- `start_django_frontend.bat`
- `start_django_frontend.ps1`

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