# Myportfolio

## Documents
- Requirements: `docs/requirements.md`
- Backend: `backend/README.md`
- Frontend: `frontend/README.md`

## Quick Start

### Backend (FastAPI)
```bash
cd backend
python -m uvicorn app.main:app --reload
```
Runs on `http://localhost:8000`

### Frontend (React via Vite)
```bash
cd frontend
npm install
npm run dev
```
Runs on `http://localhost:5173`

### Frontend (CDN Alternative - No Node.js required)
Open `frontend/index-cdn.html` in a browser or serve with:
```bash
python -m http.server -d frontend 8080
# Open http://localhost:8080/index-cdn.html
```