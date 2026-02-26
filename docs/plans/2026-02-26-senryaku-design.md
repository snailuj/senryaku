# Senryaku Design Document

**Date:** 2026-02-26
**Source:** Senryaku-PRD.md v1.0

## Design Status: Approved

The PRD at `../../../Senryaku-PRD.md` serves as the canonical design document. It covers:

- **Data model**: Campaign → Mission → Sortie → AAR hierarchy, plus DailyCheckIn
- **Algorithms**: Campaign health score, urgency scoring, drift detection (sections 8.1-8.3)
- **API spec**: Full REST API at `/api/v1` with API key auth (section 7)
- **Tech stack**: FastAPI + SQLite/SQLModel + Jinja2/HTMX + Tailwind CDN (section 5)
- **UI/UX**: Dark-mode default, sidebar layout, mobile-responsive, HTMX interactions (section 6)
- **Directory structure**: Prescribed in section 10

## Implementation Decisions

Decisions made during build that diverge from or clarify the PRD:

_(To be updated during implementation)_
