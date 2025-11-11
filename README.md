# GPay Weekly Pay - FastAPI + Plain JS + SQLite (Starter)

## Quick start (local)

Prereqs:
- Python 3.10+
- pip

Install:
```bash
python -m venv .venv
source .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Run migrations (SQLite auto-creates DB) and start server:
```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000 in your browser.

## Notes
- This is a starter project. Enhance file parsing (PDF), harden security, and set HTTPS for production.
- Environment variables: create a `.env` file with `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (optional).
