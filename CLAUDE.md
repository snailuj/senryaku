# Senryaku

Personal operations server. Military metaphor: Campaigns -> Missions -> Sorties -> AARs.

## Tech Stack
- FastAPI + Python 3.12
- SQLModel + SQLite + Alembic
- Jinja2 + HTMX + Tailwind CSS (CDN)

## Run Locally
```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn senryaku.main:app --reload --port 8000
```

## Test
```bash
pytest -v
```

## Project Structure
- `senryaku/models.py` — SQLModel data models
- `senryaku/schemas.py` — Pydantic request/response schemas
- `senryaku/routers/` — FastAPI route handlers
- `senryaku/services/` — Business logic (briefing, health, drift, review)
- `senryaku/templates/` — Jinja2 templates (base + partials for HTMX)
- `tests/` — pytest tests

## Conventions
- API endpoints under `/api/v1/`
- HTML views at root paths (`/dashboard`, `/briefing`, etc.)
- API key auth via `X-API-Key` header for API endpoints
- HTMX for all interactive UI (no SPA framework)
- Dark mode default, Tailwind CSS via CDN
