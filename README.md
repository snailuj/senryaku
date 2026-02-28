# Senryaku (戦略)

Personal operations server. Allocates finite attention across competing campaigns using 90-minute work blocks, tracks drift between priorities and actual investment, and generates daily briefings and weekly reviews.

**Military metaphor throughout:** Campaigns → Missions → Sorties → After-Action Reports.

## Quick Start

```bash
pip install -e ".[dev]"
alembic upgrade head
python3 scripts/seed.py          # optional: populate sample data
uvicorn senryaku.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Features

- **Campaign Dashboard** — health indicators, velocity, staleness per campaign
- **Daily Briefing** — urgency-scored work plan filtered by energy state
- **Energy Routing** — "What should I do?" returns the best next sortie
- **Sortie Focus View** — 90-minute countdown timer with micro-break reminders
- **After-Action Reports** — capture outcome + energy shift in <30 seconds
- **Drift Detection** — surfaces gaps between stated priorities and actual time allocation
- **Weekly Review** — 7-section structured summary with scoreboard and trends
- **Campaign Reranking** — drag-and-drop priority reordering (SortableJS)
- **Dark/Light Mode** — toggle with localStorage persistence
- **Webhook Notifications** — ntfy, Telegram, or generic webhook
- **Cron Scheduling** — automated briefing and review generation (APScheduler)
- **Mobile Responsive** — all views usable on phone

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| Database | SQLite + SQLModel + Alembic |
| Frontend | Jinja2 + HTMX + Tailwind CSS (CDN) |
| Scheduling | APScheduler |
| Drag-and-drop | SortableJS |

## API

All API endpoints are under `/api/v1/` and require an `X-API-Key` header.

Interactive docs at [/docs](http://localhost:8000/docs) (Swagger UI) or [/redoc](http://localhost:8000/redoc).

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/campaigns` | List campaigns |
| POST | `/api/v1/campaigns` | Create campaign |
| GET | `/api/v1/briefing/today` | Generate daily briefing |
| GET | `/api/v1/briefing/route` | Get single best sortie for energy level |
| POST | `/api/v1/checkin` | Submit daily check-in |
| PUT | `/api/v1/sorties/{id}/start` | Start a sortie |
| PUT | `/api/v1/sorties/{id}/complete` | Complete sortie with AAR |
| GET | `/api/v1/drift` | Drift detection report |
| GET | `/api/v1/review/weekly` | Weekly review |
| GET | `/api/v1/dashboard/health` | Campaign health summary (Obsidian integration) |
| GET | `/api/v1/settings` | Current settings (read-only) |

Add `?format=markdown` to briefing, drift, and review endpoints for plain-text output.

## Configuration

All settings via environment variables (prefix `SENRYAKU_`) or `.env` file:

```
SENRYAKU_API_KEY=your-secret-key
SENRYAKU_TIMEZONE=Pacific/Auckland
SENRYAKU_WEBHOOK_URL=https://ntfy.sh/your-topic
SENRYAKU_WEBHOOK_TYPE=ntfy
SENRYAKU_BRIEFING_CRON=0 7 * * *
SENRYAKU_REVIEW_CRON=0 18 * * 0
SENRYAKU_BASE_URL=https://senryaku.example.com
```

## Deploy

```bash
./deploy.sh --domain senryaku.example.com
```

Creates a systemd service behind Caddy (auto-HTTPS). See `deploy.sh` for details.

## Test

```bash
pytest -v
```

## Project Structure

```
senryaku/
├── main.py              # FastAPI app, lifespan, middleware
├── config.py            # Settings from env vars
├── models.py            # SQLModel data models (5 entities, 6 enums)
├── schemas.py           # Pydantic request/response schemas
├── database.py          # Engine, session, init
├── routers/
│   ├── campaigns.py     # Campaign CRUD
│   ├── missions.py      # Mission CRUD
│   ├── sorties.py       # Sortie CRUD + lifecycle
│   ├── operations.py    # Briefing, drift, review, check-in
│   └── dashboard.py     # HTML view routes
├── services/
│   ├── briefing.py      # Urgency scoring + energy filtering
│   ├── health.py        # Campaign health computation
│   ├── drift.py         # Priority vs actual drift detection
│   ├── review.py        # Weekly review generation
│   ├── notifications.py # Webhook dispatch
│   └── scheduler.py     # APScheduler cron jobs
├── templates/           # Jinja2 templates (base + partials)
└── static/              # CSS + JS
```
