"""Operations API router — daily check-in and operational endpoints."""

from datetime import date as date_type

from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from starlette.responses import PlainTextResponse

from senryaku.database import get_session
from senryaku.models import DailyCheckIn, EnergyLevel
from senryaku.schemas import BriefingResponse, BriefingSortie, DailyCheckInCreate, DailyCheckInRead
from senryaku.services.briefing import generate_briefing

router = APIRouter()


@router.post("/checkin", response_model=DailyCheckInRead, status_code=201)
def create_checkin(
    checkin: DailyCheckInCreate,
    session: Session = Depends(get_session),
):
    """Create or update a daily check-in (upsert by date)."""
    # Check if checkin already exists for this date (upsert)
    existing = session.exec(
        select(DailyCheckIn).where(DailyCheckIn.date == checkin.date)
    ).first()

    if existing:
        # Update existing
        for key, value in checkin.model_dump().items():
            setattr(existing, key, value)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # Create new
    db_checkin = DailyCheckIn(**checkin.model_dump())
    session.add(db_checkin)
    session.commit()
    session.refresh(db_checkin)
    return db_checkin


@router.get("/briefing/today")
def get_briefing(
    energy: str | None = None,
    format: str | None = None,
    session: Session = Depends(get_session),
):
    """Generate today's briefing. Uses today's check-in or defaults."""
    # Get today's check-in
    checkin = session.exec(
        select(DailyCheckIn).where(DailyCheckIn.date == date_type.today())
    ).first()

    # Use provided energy or check-in energy or default
    if energy:
        energy_level = EnergyLevel(energy)
    elif checkin:
        energy_level = checkin.energy_level
    else:
        energy_level = EnergyLevel.green

    available_blocks = checkin.available_blocks if checkin else 4

    sorties = generate_briefing(session, energy_level, available_blocks)

    if format == "markdown":
        # Return markdown text
        lines = [f"# Daily Briefing \u2014 {date_type.today()}", ""]
        lines.append(f"Energy: {energy_level.value} | Blocks: {available_blocks}")
        lines.append("")
        for i, s in enumerate(sorties, 1):
            load_emoji = {"deep": "\U0001f9e0", "medium": "\u26a1", "light": "\U0001f33f"}.get(s.cognitive_load.value, "")
            lines.append(f"{i}. {load_emoji} **{s.title}** ({s.campaign_name} \u2192 {s.mission_name})")
        return PlainTextResponse("\n".join(lines))

    return BriefingResponse(
        date=date_type.today(),
        energy_level=energy_level,
        available_blocks=available_blocks,
        sorties=sorties,
    )


@router.get("/briefing/route")
def route_sortie(
    energy: str = "green",
    session: Session = Depends(get_session),
):
    """Return the single best sortie for current energy."""
    energy_level = EnergyLevel(energy)
    sorties = generate_briefing(session, energy_level, 1)  # Just need 1
    if sorties:
        return sorties[0]
    return None


@router.get("/drift")
def get_drift_report(format: str | None = None, session: Session = Depends(get_session)):
    """Return drift report as JSON or markdown."""
    from senryaku.services.drift import compute_drift
    report = compute_drift(session)
    if format == "markdown":
        lines = [f"# Drift Report \u2014 {report.date}", ""]
        for s in report.misalignment_statements:
            lines.append(f"- \u26a0\ufe0f {s}")
        if not report.misalignment_statements:
            lines.append("No significant misalignments detected.")
        lines.append("")
        lines.append("| Campaign | Expected | Actual | Drift | Trend |")
        lines.append("|----------|----------|--------|-------|-------|")
        for c in report.campaigns:
            flag = "\u26a0\ufe0f" if c.is_misaligned else ""
            lines.append(f"| {c.name} | {round(c.expected_share*100)}% | {round(c.actual_share*100)}% | {round(c.drift*100):+}% | {c.trend} {flag} |")
        return PlainTextResponse("\n".join(lines))
    return report


@router.get("/review/weekly")
def get_weekly_review(
    format: str | None = None,
    session: Session = Depends(get_session),
):
    """Generate the weekly review. Returns JSON or markdown."""
    from senryaku.services.review import generate_weekly_review, generate_weekly_review_markdown

    if format == "markdown":
        return PlainTextResponse(generate_weekly_review_markdown(session))
    return generate_weekly_review(session)


@router.get("/dashboard/health")
def get_dashboard_health(session: Session = Depends(get_session)):
    """Campaign health summary as JSON -- also serves Obsidian integration."""
    from senryaku.services.health import get_dashboard_data
    return get_dashboard_data(session)


@router.get("/settings")
def get_settings_api():
    """Return current settings as JSON (read-only)."""
    from senryaku.config import get_settings
    settings = get_settings()
    return {
        "timezone": settings.timezone,
        "webhook_url": settings.webhook_url,
        "webhook_type": settings.webhook_type,
        "briefing_cron": settings.briefing_cron,
        "review_cron": settings.review_cron,
        "base_url": settings.base_url,
    }
