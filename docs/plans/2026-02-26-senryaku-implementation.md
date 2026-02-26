# Senryaku Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted personal operations server that allocates attention across campaigns using 90-minute work blocks, tracks drift between priorities and actual work, and generates daily briefings and weekly reviews.

**Architecture:** FastAPI backend with SQLite/SQLModel, server-rendered Jinja2 templates with HTMX for interactivity, Tailwind CSS via CDN for styling. Single-user, self-hosted. Military metaphor: Campaigns → Missions → Sorties → AARs.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, SQLite, Alembic, Jinja2, HTMX, Tailwind CSS (CDN), APScheduler, SortableJS

**Source PRD:** `../../Senryaku-PRD.md` — canonical reference for all data models, algorithms, and API specs.

**Repo:** `github.com/snailuj/senryaku`

---

## Phase 1: Project Scaffold & Data Model

### Task 1.1: Initialize Git Repo and Project Structure

**Files:**
- Create: `pyproject.toml`
- Create: `senryaku/__init__.py`
- Create: `senryaku/config.py`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `CLAUDE.md`

**Step 1: Create GitHub repo**

```bash
cd /home/agent/projects/dojo/senryaku
git init
gh repo create snailuj/senryaku --public --description "戦略 — Personal operations server. Campaigns → Missions → Sorties → AARs." --source=. --remote=origin
```

**Step 2: Create pyproject.toml with all dependencies**

```toml
[project]
name = "senryaku"
version = "0.1.0"
description = "Personal operations server"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlmodel>=0.0.22",
    "alembic>=1.14.0",
    "jinja2>=3.1.0",
    "python-dotenv>=1.0.0",
    "apscheduler>=3.10.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

**Step 3: Create config.py**

Settings class using pydantic-settings, reading from env vars: `SENRYAKU_API_KEY`, `SENRYAKU_DB_PATH` (default `./data/senryaku.db`), `SENRYAKU_TIMEZONE` (default `Pacific/Auckland`), plus all optional webhook/SMTP/cron settings from PRD section 9.

**Step 4: Create .gitignore, .env.example, CLAUDE.md**

.gitignore: standard Python + `data/`, `.env`, `__pycache__/`
.env.example: all env vars from PRD section 9
CLAUDE.md: project conventions, how to run, test commands

**Step 5: Install dependencies**

```bash
pip install -e ".[dev]"
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: project scaffold with dependencies and config"
git push -u origin main
```

---

### Task 1.2: SQLModel Data Models

**Files:**
- Create: `senryaku/models.py`
- Test: `tests/test_models.py`

**Step 1: Write model tests**

Test that all 5 models can be instantiated with required fields:
- `Campaign`: name, description, status, priority_rank, weekly_block_target, colour
- `Mission`: campaign_id, name, description, status, sort_order
- `Sortie`: mission_id, title, cognitive_load, estimated_blocks, status, sort_order
- `AAR`: sortie_id, energy_before, energy_after, outcome, actual_blocks
- `DailyCheckIn`: date, energy_level, available_blocks

Test enum values match PRD exactly. Test foreign key relationships. Test default values (created_at auto-set, optional fields nullable).

**Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_models.py -v
```

**Step 3: Implement models.py**

All 5 models as SQLModel classes with `table=True`. Use Python enums for status fields. UUIDs as primary keys (`default_factory=uuid4`). All datetime fields with `default_factory=datetime.utcnow`. Foreign keys with proper relationships.

Enum definitions:
- `CampaignStatus`: active, paused, completed, archived
- `MissionStatus`: not_started, in_progress, blocked, completed
- `SortieStatus`: queued, active, completed, abandoned
- `CognitiveLoad`: deep, medium, light
- `EnergyLevel`: green, yellow, red
- `AAROutcome`: completed, partial, blocked, pivoted

**Step 4: Run tests — expect PASS**

```bash
pytest tests/test_models.py -v
```

**Step 5: Commit**

```bash
git add senryaku/models.py tests/test_models.py
git commit -m "feat: SQLModel data models for all 5 entities"
```

---

### Task 1.3: Database Setup and Alembic Migrations

**Files:**
- Create: `senryaku/database.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/` (auto-generated)

**Step 1: Create database.py**

Engine creation using `SENRYAKU_DB_PATH` from config. Session factory. `init_db()` function. `get_session()` dependency for FastAPI.

**Step 2: Initialize Alembic**

```bash
cd /home/agent/projects/dojo/senryaku
alembic init alembic
```

**Step 3: Configure alembic env.py**

Point at SQLModel metadata. Use `senryaku.models` to import all models. Configure SQLite URL from config.

**Step 4: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```

**Step 5: Run migration**

```bash
mkdir -p data
alembic upgrade head
```

**Step 6: Verify schema**

```bash
python -c "import sqlite3; conn = sqlite3.connect('data/senryaku.db'); print([t[0] for t in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"
```

Expected: all 5 tables present.

**Step 7: Commit**

```bash
git add senryaku/database.py alembic.ini alembic/
git commit -m "feat: database setup with Alembic migrations"
git push
```

---

### Task 1.4: Pydantic Request/Response Schemas

**Files:**
- Create: `senryaku/schemas.py`

**Step 1: Create schemas.py**

Request and response schemas for all entities. Separate Create/Update/Read schemas:
- `CampaignCreate`, `CampaignUpdate`, `CampaignRead` (includes computed fields placeholder)
- `MissionCreate`, `MissionUpdate`, `MissionRead`
- `SortieCreate`, `SortieUpdate`, `SortieRead`
- `AARCreate`, `AARRead`
- `DailyCheckInCreate`, `DailyCheckInRead`
- `BriefingSortie` (sortie + campaign name + mission context for briefing display)
- `CampaignHealth` (campaign + health indicators for dashboard)
- `RerankRequest` (list of {id, rank} pairs)

**Step 2: Commit**

```bash
git add senryaku/schemas.py
git commit -m "feat: Pydantic request/response schemas"
```

---

## Phase 2: CRUD API Endpoints

### Task 2.1: FastAPI App Bootstrap + Campaign CRUD API

**Files:**
- Create: `senryaku/main.py`
- Create: `senryaku/routers/__init__.py`
- Create: `senryaku/routers/campaigns.py`
- Test: `tests/test_api.py`
- Test: `tests/conftest.py`

**Step 1: Write API tests for campaigns**

Test fixtures in conftest.py: test client using TestClient, test database (in-memory SQLite), session override.

Tests:
- POST /api/v1/campaigns — create campaign, verify 201 + returned data
- GET /api/v1/campaigns — list campaigns, verify filtering by status
- GET /api/v1/campaigns/{id} — get campaign with missions
- PUT /api/v1/campaigns/{id} — update fields
- DELETE /api/v1/campaigns/{id} — soft delete (status → archived)
- PUT /api/v1/campaigns/rerank — bulk reorder

**Step 2: Run tests — expect FAIL**

**Step 3: Create main.py**

FastAPI app with lifespan (init_db on startup). Mount static files. Include routers. API key middleware for `/api/v1/*` routes. Jinja2 template setup.

**Step 4: Create campaigns router**

All 6 campaign endpoints per PRD section 7. Use `get_session` dependency. Return proper HTTP status codes. Soft delete via status change.

**Step 5: Run tests — expect PASS**

**Step 6: Commit**

```bash
git add senryaku/main.py senryaku/routers/ tests/conftest.py tests/test_api.py
git commit -m "feat: FastAPI app + campaign CRUD API"
git push
```

---

### Task 2.2: Mission CRUD API

**Files:**
- Create: `senryaku/routers/missions.py`
- Modify: `tests/test_api.py`

**Step 1: Write mission API tests**

- POST /api/v1/missions — create mission linked to campaign
- GET /api/v1/campaigns/{id}/missions — list missions for campaign
- PUT /api/v1/missions/{id} — update
- DELETE /api/v1/missions/{id} — soft delete

**Step 2: Implement mission router**

**Step 3: Tests pass, commit**

```bash
git commit -m "feat: mission CRUD API"
```

---

### Task 2.3: Sortie CRUD API

**Files:**
- Create: `senryaku/routers/sorties.py`
- Modify: `tests/test_api.py`

**Step 1: Write sortie API tests**

- POST /api/v1/sorties — create sortie linked to mission
- GET /api/v1/missions/{id}/sorties — list sorties for mission
- GET /api/v1/sorties/queued — all queued sorties across campaigns
- PUT /api/v1/sorties/{id} — update
- PUT /api/v1/sorties/{id}/start — mark active, set started_at
- PUT /api/v1/sorties/{id}/complete — submit AAR inline, create AAR record
- DELETE /api/v1/sorties/{id} — soft delete

**Step 2: Implement sortie router**

Note: The `/complete` endpoint creates an AAR record AND updates sortie status. This is the key workflow endpoint.

**Step 3: Tests pass, commit**

```bash
git commit -m "feat: sortie CRUD API with start/complete lifecycle"
```

---

### Task 2.4: Check-in API

**Files:**
- Create: `senryaku/routers/operations.py`
- Modify: `tests/test_api.py`

**Step 1: Write check-in API test**

- POST /api/v1/checkin — create daily check-in
- Verify only one check-in per date (upsert behavior)

**Step 2: Implement in operations router**

**Step 3: Tests pass, commit + push**

```bash
git commit -m "feat: daily check-in API"
git push
```

---

## Phase 3: Base UI + Campaign Dashboard

### Task 3.1: Base Template with HTMX + Tailwind

**Files:**
- Create: `senryaku/templates/base.html`
- Create: `senryaku/static/app.css`
- Create: `senryaku/static/app.js`
- Create: `senryaku/routers/dashboard.py`

**Step 1: Create base.html**

Full HTML layout with:
- Tailwind CSS CDN link
- HTMX CDN link
- Dark mode default (class="dark" on html)
- Sidebar: campaign list (HTMX-loaded), nav links (Dashboard, Briefing, Review, Settings)
- Top bar: current date, energy indicator, "What should I do?" button
- Main content area with `{% block content %}`
- Mobile: sidebar collapses to hamburger menu
- System font stack

**Step 2: Create app.css**

Minimal custom CSS: campaign colour left-border accent, cognitive load badge colours (indigo/amber/green), dark mode variables.

**Step 3: Create app.js**

Minimal: hamburger toggle, timer functions (for sortie focus), SortableJS init placeholder.

**Step 4: Create dashboard router**

GET `/` → redirect to dashboard
GET `/dashboard` → render dashboard.html

**Step 5: Verify app starts**

```bash
cd /home/agent/projects/dojo/senryaku
uvicorn senryaku.main:app --reload --port 8000
```

**Step 6: Commit**

```bash
git commit -m "feat: base template with HTMX, Tailwind, sidebar layout"
```

---

### Task 3.2: Health Computation Service

**Files:**
- Create: `senryaku/services/__init__.py`
- Create: `senryaku/services/health.py`
- Create: `tests/test_health.py`

**Step 1: Write health service tests**

Test `compute_campaign_health()`:
- Campaign with 80%+ adherence and ≤3 days staleness → green
- Campaign with 40-80% adherence or ≤7 days staleness → yellow
- Campaign below both thresholds → red
- Campaign with zero target → handle gracefully
- Edge cases: new campaign with no sorties

Test `compute_velocity()`:
- Returns completed blocks in last 7 days for a campaign

Test `compute_staleness()`:
- Returns days since last completed sortie

**Step 2: Implement health.py**

Functions: `compute_campaign_health()`, `compute_velocity()`, `compute_staleness()`, `get_dashboard_data()` (aggregates all campaign health for dashboard).

Algorithm from PRD section 8.1.

**Step 3: Tests pass, commit**

```bash
git commit -m "feat: campaign health computation service"
```

---

### Task 3.3: Campaign Dashboard Page

**Files:**
- Create: `senryaku/templates/dashboard.html`
- Create: `senryaku/templates/partials/campaign_card.html`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create campaign_card.html partial**

HTMX fragment showing:
- Campaign name + colour left-border accent
- Priority rank badge
- Health indicator (green/yellow/red dot)
- Velocity: "X/Y blocks this week" with mini bar
- Staleness: "N days since last sortie"
- Mission progress: "X of Y missions completed"
- Next queued sortie title
- Click → drill to campaign detail (hx-get)

**Step 2: Create dashboard.html**

Extends base.html. Lists campaign cards sorted by priority_rank. Shows summary stats at top: total blocks today, available blocks, current energy.

**Step 3: Update dashboard router**

Fetch all active campaigns with health data. Pass to template.

**Step 4: Verify visually**

Start server, navigate to `/dashboard`, verify campaign cards render.

**Step 5: Commit + push**

```bash
git commit -m "feat: campaign dashboard with health indicators"
git push
```

---

### Task 3.4: Campaign Detail Page

**Files:**
- Create: `senryaku/templates/campaign_detail.html`
- Create: `senryaku/templates/partials/sortie_row.html`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create campaign_detail.html**

Shows campaign info (editable inline via HTMX), mission list (each expandable to show sorties), and sortie rows within each mission. Include "Add Mission" and "Add Sortie" buttons.

**Step 2: Create sortie_row.html partial**

Shows: title, cognitive load badge, status, estimated blocks. Clickable to start sortie or view details.

**Step 3: Add route**

GET `/campaigns/{id}` → render campaign_detail.html

**Step 4: Commit**

```bash
git commit -m "feat: campaign detail page with missions and sorties"
```

---

### Task 3.5: CRUD Forms (Campaign/Mission/Sortie Create/Edit)

**Files:**
- Create: `senryaku/templates/partials/campaign_form.html`
- Create: `senryaku/templates/partials/mission_form.html`
- Create: `senryaku/templates/partials/sortie_form.html`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create campaign form partial**

HTMX modal form: name, description, priority_rank, weekly_block_target, colour (color picker), tags. POST to API, swap campaign list on success.

**Step 2: Create mission form partial**

Name, description, target_date. Pre-filled campaign_id from context.

**Step 3: Create sortie form partial**

Title, cognitive_load (3 radio buttons with badges), description (optional), estimated_blocks (default 1). Pre-filled mission_id.

**Step 4: Add dashboard routes for form rendering and submissions**

HTMX routes that return form partials, and routes that handle form POST → API call → return updated HTML fragment.

**Step 5: Commit**

```bash
git commit -m "feat: CRUD forms for campaigns, missions, sorties"
git push
```

---

## Phase 4: Daily Check-in + Briefing

### Task 4.1: Check-in Form UI

**Files:**
- Create: `senryaku/templates/partials/checkin_form.html`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create checkin_form.html**

Three large energy buttons (green/yellow/red), available_blocks number input (stepper), optional focus_note text input. Must be completable in <15 seconds. HTMX POST to check-in API.

**Step 2: Add check-in route**

GET `/checkin` → render form
The form POSTs to API and then redirects to briefing.

**Step 3: Commit**

```bash
git commit -m "feat: daily check-in form UI"
```

---

### Task 4.2: Briefing Algorithm Service

**Files:**
- Create: `senryaku/services/briefing.py`
- Create: `tests/test_briefing.py`

**Step 1: Write briefing algorithm tests**

Test `generate_briefing()`:
- With green energy → includes deep, medium, light sorties
- With yellow energy → excludes deep sorties
- With red energy → only light sorties
- Urgency scoring: campaign with bigger deficit scores higher
- 60% cap: no single campaign takes >60% of blocks (unless only campaign)
- Empty state: no queued sorties → empty briefing
- Blocks limit: stops filling when available_blocks reached

Test `compute_urgency_score()`:
- Matches PRD formula: `(weekly_block_target - blocks_this_week) * priority_weight + staleness_days * 0.5`

**Step 2: Implement briefing.py**

Algorithm from PRD section 4.2 and 8.2:
1. Calculate urgency score per campaign
2. Filter queued sorties by cognitive load ≤ energy
3. Sort by parent campaign urgency descending
4. Greedy fill, 60% cap per campaign
5. Return ordered list of `BriefingSortie` objects

**Step 3: Tests pass, commit**

```bash
git commit -m "feat: briefing algorithm with urgency scoring and energy filtering"
```

---

### Task 4.3: Briefing Page + API

**Files:**
- Create: `senryaku/templates/briefing.html`
- Modify: `senryaku/routers/operations.py`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Add briefing API endpoint**

GET `/api/v1/briefing/today` — returns JSON (or markdown with `?format=markdown`). Requires today's check-in to exist (or uses defaults).

**Step 2: Create briefing.html**

Extends base.html. Shows:
- Today's energy + available blocks at top
- Ordered list of sorties as cards: title, campaign name (colour accent), cognitive load badge, mission context
- Each sortie has "Start" button (hx-put to start sortie)
- If no check-in today, show check-in form first

**Step 3: Add page route**

GET `/briefing` → render briefing.html

**Step 4: Commit + push**

```bash
git commit -m "feat: daily briefing page and API endpoint"
git push
```

---

### Task 4.4: Energy-State Routing ("What Should I Do?")

**Files:**
- Create: `senryaku/templates/partials/route_result.html`
- Modify: `senryaku/routers/operations.py`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Add routing API endpoint**

GET `/api/v1/briefing/route?energy=green|yellow|red` — returns single best sortie.

**Step 2: Create route_result.html partial**

Shows the single recommended sortie: title, campaign, cognitive load, mission context, prominent "Start" button. If no sortie available, show a "Nothing queued" message.

**Step 3: Wire the top bar "What should I do?" button**

HTMX: clicking the button opens a small energy selector (3 buttons), then fetches route_result partial and swaps it into a modal or inline area.

**Step 4: Commit**

```bash
git commit -m "feat: energy-state routing - What should I do?"
```

---

## Phase 5: Sortie Focus View + AAR

### Task 5.1: Sortie Focus View with Timer

**Files:**
- Create: `senryaku/templates/sortie_focus.html`
- Modify: `senryaku/static/app.js`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create sortie_focus.html**

Clean, distraction-free view:
- Campaign name + colour accent at top
- Mission context (small text)
- Sortie title (large, prominent)
- Sortie description (if present)
- 90-minute countdown timer (large, visual)
- "Complete" button (opens AAR form)
- "Abandon" button (smaller, secondary)

**Step 2: Add timer JS to app.js**

Countdown from 90 minutes. At 30-min and 60-min marks, show a subtle micro-break reminder (toast/notification). Timer is visual only — doesn't block anything.

**Step 3: Add route**

GET `/sorties/{id}/focus` → mark sortie as active (started_at), render focus view.

**Step 4: Commit**

```bash
git commit -m "feat: sortie focus view with 90-minute timer"
```

---

### Task 5.2: After-Action Report Form

**Files:**
- Create: `senryaku/templates/partials/aar_form.html`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Create aar_form.html**

Must be completable in <30 seconds:
- Energy before (pre-filled from today's check-in): 3 radio buttons (green/yellow/red)
- Energy after: 3 radio buttons
- Outcome: 4 large buttons (completed ✓ / partial ◐ / blocked ⊘ / pivoted ↻)
- Actual blocks: number input (default 1)
- Notes: collapsed by default, click to expand textarea
- If outcome = blocked, show notes field expanded with placeholder "What's blocking?"
- Submit button

HTMX POST to `/api/v1/sorties/{id}/complete`. On success, redirect to dashboard.

**Step 2: Wire "Complete" button on focus view**

Clicking "Complete" swaps in the AAR form via HTMX.

**Step 3: Commit + push**

```bash
git commit -m "feat: after-action report form"
git push
```

---

## Phase 6: Mobile Responsiveness

### Task 6.1: Responsive Layout Pass

**Files:**
- Modify: `senryaku/templates/base.html`
- Modify: `senryaku/templates/dashboard.html`
- Modify: `senryaku/templates/briefing.html`
- Modify: `senryaku/templates/sortie_focus.html`
- Modify: `senryaku/static/app.css`
- Modify: `senryaku/static/app.js`

**Step 1: Sidebar → hamburger on mobile**

Tailwind responsive classes: sidebar hidden on small screens, hamburger button visible. JS toggle to show/hide sidebar as overlay.

**Step 2: Campaign cards stack vertically on mobile**

Grid → single column on small screens.

**Step 3: Forms use full-width inputs on mobile**

All inputs/buttons full width below sm breakpoint.

**Step 4: Touch-friendly AAR**

Outcome buttons large enough for thumb taps. Energy selectors are big radio buttons.

**Step 5: Test key mobile flows**

Verify in browser dev tools (mobile viewport):
- Morning check-in
- View dashboard
- "What should I do?"
- Start sortie → focus → AAR

**Step 6: Commit**

```bash
git commit -m "feat: mobile-responsive layout for all views"
git push
```

---

## Phase 7: Drift Detection + Weekly Review (P0.2)

### Task 7.1: Drift Detection Service

**Files:**
- Create: `senryaku/services/drift.py`
- Create: `tests/test_drift.py`

**Step 1: Write drift detection tests**

Test `compute_drift()`:
- Campaign getting more blocks than expected → positive drift
- Campaign getting fewer → negative drift
- Flag campaigns where abs(drift) > 0.15
- Edge case: no blocks completed → handle gracefully
- 4-week trend: improving vs worsening drift

Test output format: plain-language misalignment statements per PRD section 4.5.

**Step 2: Implement drift.py**

Algorithm from PRD section 8.3. Returns structured data + generated plain-language statements.

**Step 3: Tests pass, commit**

```bash
git commit -m "feat: drift detection service"
```

---

### Task 7.2: Drift Report Page + API

**Files:**
- Create: `senryaku/templates/drift.html`
- Modify: `senryaku/routers/operations.py`
- Modify: `senryaku/routers/dashboard.py`

**Step 1: Add drift API endpoint**

GET `/api/v1/drift` — JSON or markdown. Shows per-campaign expected vs actual share, drift value, misalignment flags, 4-week trend.

**Step 2: Create drift.html**

Visual table/cards showing each campaign's expected vs actual allocation. Highlighted misalignments. Trend arrows (↑ improving, ↓ worsening).

**Step 3: Commit**

```bash
git commit -m "feat: drift detection report page"
```

---

### Task 7.3: Weekly Review Generator

**Files:**
- Create: `senryaku/services/review.py`
- Create: `senryaku/templates/review.html`
- Modify: `senryaku/routers/operations.py`

**Step 1: Implement review.py**

Generates structured markdown per PRD section 4.6:
1. Scoreboard: blocks per campaign vs target
2. Missions moved: status changes this week
3. Drift summary
4. Staleness alerts (>5 days untouched)
5. Energy patterns (average across the week)
6. Campaign re-rank prompt
7. Next week preview

**Step 2: Create review.html**

Renders the weekly review as a nicely formatted page. "Export as Markdown" button.

**Step 3: Add API endpoint**

GET `/api/v1/review/weekly` — JSON or markdown format.

**Step 4: Commit + push**

```bash
git commit -m "feat: weekly review generator"
git push
```

---

### Task 7.4: Campaign Reranking (Drag-and-Drop)

**Files:**
- Modify: `senryaku/templates/dashboard.html`
- Modify: `senryaku/static/app.js`

**Step 1: Add SortableJS**

Include SortableJS via CDN in base.html. Initialize on campaign card list.

**Step 2: Wire drag-and-drop to API**

On sort end, collect new order, HTMX PUT to `/api/v1/campaigns/rerank`. Update priority_rank values.

**Step 3: Fallback: up/down arrows**

For mobile or accessibility, add up/down arrow buttons on each campaign card.

**Step 4: Commit**

```bash
git commit -m "feat: campaign reranking via drag-and-drop"
```

---

### Task 7.5: Bulk Operations

**Files:**
- Modify: `senryaku/routers/sorties.py`
- Modify: `senryaku/templates/campaign_detail.html`

**Step 1: Add bulk endpoints**

- PUT `/api/v1/sorties/bulk` — accept array of {id, status} to batch-complete/abandon
- PUT `/api/v1/sorties/{id}/move` — move sortie to different mission

**Step 2: Add UI controls**

Checkboxes on sortie rows. "Bulk Complete" / "Bulk Abandon" buttons. "Move to..." dropdown on individual sorties.

**Step 3: Commit + push**

```bash
git commit -m "feat: bulk sortie operations"
git push
```

---

## Phase 8: P1 Features

### Task 8.1: Dashboard Health API (for Obsidian)

**Files:**
- Modify: `senryaku/routers/operations.py`

**Step 1: Add health API endpoint**

GET `/api/v1/dashboard/health` — JSON summary of all campaign health metrics. This serves both the internal dashboard and the Obsidian integration.

**Step 2: Verify API key auth works**

Test that all `/api/v1/*` endpoints require `X-API-Key` header.

**Step 3: Commit**

```bash
git commit -m "feat: dashboard health API endpoint"
```

---

### Task 8.2: APScheduler Cron Jobs

**Files:**
- Create: `senryaku/services/scheduler.py`
- Modify: `senryaku/main.py`

**Step 1: Implement scheduler.py**

APScheduler setup:
- Morning briefing generation at configured cron time
- Weekly review generation at configured cron time
- Jobs stored in memory (single-process, single-user)

**Step 2: Wire into FastAPI lifespan**

Start scheduler on app startup, shut down on app shutdown.

**Step 3: Commit**

```bash
git commit -m "feat: APScheduler cron for briefings and reviews"
```

---

### Task 8.3: Webhook Notifications

**Files:**
- Create: `senryaku/services/notifications.py`
- Create: `senryaku/routers/settings.py`
- Create: `senryaku/templates/settings.html`

**Step 1: Implement notifications.py**

Send markdown payload to configured webhook. Support types: ntfy, telegram, email (SMTP), generic POST.

**Step 2: Create settings page**

Form for: webhook URL, webhook type, timezone, briefing cron time, review cron time. Save to a settings table or env file.

**Step 3: Wire scheduler to send notifications**

After generating briefing/review, fire webhook if configured.

**Step 4: Commit**

```bash
git commit -m "feat: webhook notifications and settings page"
```

---

### Task 8.4: Dark/Light Mode Toggle

**Files:**
- Modify: `senryaku/templates/base.html`
- Modify: `senryaku/static/app.js`
- Modify: `senryaku/static/app.css`

**Step 1: Add toggle to sidebar/settings**

Button that toggles `dark` class on html element. Persist preference in localStorage.

**Step 2: Ensure all templates use Tailwind dark: variants**

Audit all templates for proper dark mode styling.

**Step 3: Commit**

```bash
git commit -m "feat: dark/light mode toggle"
```

---

### Task 8.5: Deploy Script

**Files:**
- Create: `deploy.sh`

**Step 1: Create deploy.sh**

Per PRD section 10:
1. Create Python venv and install dependencies
2. Run Alembic migrations
3. Create systemd service file for uvicorn
4. Configure Caddy reverse proxy block
5. Start/restart service

**Step 2: Commit + final push**

```bash
git commit -m "feat: deployment script for Ubuntu + Caddy"
git push
```

---

## Phase 9: Final Polish + Verification

### Task 9.1: End-to-End Walkthrough

Run through all acceptance criteria from PRD section 12:

- [ ] Create campaigns with priority ranks and weekly block targets
- [ ] Decompose campaigns into missions and missions into sorties
- [ ] Dashboard shows health indicators, velocity, staleness
- [ ] Morning check-in in <15 seconds
- [ ] Briefing generates ordered work plan respecting energy
- [ ] "What should I do?" returns best next sortie
- [ ] Sortie focus view with 90-minute timer + micro-break reminders
- [ ] AAR captures outcome + energy in <30 seconds
- [ ] All views usable on mobile
- [ ] API documented via OpenAPI
- [ ] SQLite with proper migrations

### Task 9.2: Seed Data

Create a script or fixture that populates the database with realistic sample data (3-4 campaigns, missions, sorties) so the user can see the app in action immediately.

### Task 9.3: README

Write a README.md with: what it is, how to run locally, how to deploy, API docs link, screenshots placeholder.

---

## Execution Notes

- **Commit frequently**: every task gets at least one commit
- **Push regularly**: after each phase minimum
- **Test first**: write failing tests before implementation where applicable
- **PRD is canonical**: when in doubt, reference `../../Senryaku-PRD.md`
- **YAGNI**: don't add features not in the PRD
- **Mobile from the start**: use responsive Tailwind classes as you build, not as an afterthought
