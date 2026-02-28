"""APScheduler cron jobs for morning briefing and weekly review."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from senryaku.config import get_settings

scheduler = BackgroundScheduler()


def init_scheduler():
    """Initialize and start the scheduler."""
    settings = get_settings()

    # Parse cron expressions (format: "minute hour day month dow")
    # Morning briefing
    if settings.briefing_cron:
        parts = settings.briefing_cron.split()
        if len(parts) == 5:
            scheduler.add_job(
                run_morning_briefing,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                ),
                id="morning_briefing",
                replace_existing=True,
            )

    # Weekly review
    if settings.review_cron:
        parts = settings.review_cron.split()
        if len(parts) == 5:
            scheduler.add_job(
                run_weekly_review,
                CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                ),
                id="weekly_review",
                replace_existing=True,
            )

    scheduler.start()


def shutdown_scheduler():
    """Shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()


def run_morning_briefing():
    """Generate morning briefing and optionally send webhook."""
    from senryaku.database import engine
    from sqlmodel import Session, select
    from senryaku.services.briefing import generate_briefing
    from senryaku.models import DailyCheckIn, EnergyLevel
    from datetime import date

    with Session(engine) as session:
        # Get today's check-in or use defaults
        checkin = session.exec(
            select(DailyCheckIn).where(DailyCheckIn.date == date.today())
        ).first()

        energy = checkin.energy_level if checkin else EnergyLevel.green
        blocks = checkin.available_blocks if checkin else 4

        briefing = generate_briefing(session, energy, blocks)

        # Send webhook if configured
        settings = get_settings()
        if settings.webhook_url:
            from senryaku.services.notifications import send_notification

            # Format briefing as text
            lines = [f"Morning Briefing -- {date.today()}", ""]
            for i, s in enumerate(briefing, 1):
                lines.append(f"{i}. {s.title} ({s.campaign_name})")
            send_notification("\n".join(lines))


def run_weekly_review():
    """Generate weekly review and optionally send webhook."""
    from senryaku.database import engine
    from sqlmodel import Session
    from senryaku.services.review import generate_weekly_review_markdown

    with Session(engine) as session:
        markdown = generate_weekly_review_markdown(session)

        settings = get_settings()
        if settings.webhook_url:
            from senryaku.services.notifications import send_notification

            send_notification(markdown)
