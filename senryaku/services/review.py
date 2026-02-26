"""Weekly review generator service.

Implements the weekly review from PRD section 4.6.

The weekly review is generated Sunday evening (or on-demand) and contains
seven sections:

    1. Scoreboard — blocks completed per campaign vs target
    2. Missions moved — which missions changed status this week
    3. Drift summary — time-allocation drift from priority ranking
    4. Staleness alerts — campaigns untouched for >5 days
    5. Energy patterns — average energy trend across the week
    6. Re-rank prompt — current campaign ranking for re-evaluation
    7. Next week preview — upcoming target dates, blocked sorties
"""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlmodel import Session, col, func, select

from senryaku.models import (
    AAR,
    Campaign,
    CampaignStatus,
    DailyCheckIn,
    EnergyLevel,
    Mission,
    MissionStatus,
    Sortie,
    SortieStatus,
)
from senryaku.services.health import compute_staleness, compute_velocity

# Energy level numeric mapping for averaging
ENERGY_VALUES = {
    EnergyLevel.green: 3,
    EnergyLevel.yellow: 2,
    EnergyLevel.red: 1,
}

ENERGY_LABELS = {3: "green", 2: "yellow", 1: "red"}

DAY_SHORT_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _blocks_this_week(session: Session, campaign_id: UUID, cutoff: datetime) -> int:
    """Sum actual_blocks from AARs for a campaign since cutoff."""
    statement = (
        select(func.coalesce(func.sum(AAR.actual_blocks), 0))
        .join(Sortie, col(AAR.sortie_id) == col(Sortie.id))
        .join(Mission, col(Sortie.mission_id) == col(Mission.id))
        .where(Mission.campaign_id == campaign_id)
        .where(AAR.created_at >= cutoff)
    )
    result = session.exec(statement).one()
    return int(result)


def _compute_drift_summary(
    session: Session,
    campaigns: list[Campaign],
    cutoff: datetime,
) -> list[dict]:
    """Compute drift inline (no dependency on drift service)."""
    total_target = sum(c.weekly_block_target for c in campaigns) or 1
    total_actual = 0
    per_campaign: list[dict] = []

    for c in campaigns:
        blocks = _blocks_this_week(session, c.id, cutoff)
        total_actual += blocks
        per_campaign.append({"campaign": c, "blocks": blocks})

    result = []
    for item in per_campaign:
        c = item["campaign"]
        expected_share = c.weekly_block_target / total_target
        actual_share = item["blocks"] / total_actual if total_actual > 0 else 0.0
        drift = actual_share - expected_share
        result.append({
            "name": c.name,
            "colour": c.colour,
            "expected_share": round(expected_share, 2),
            "actual_share": round(actual_share, 2),
            "drift": round(drift, 2),
            "is_misaligned": abs(drift) > 0.15,
        })

    return result


def generate_weekly_review(session: Session, today: date | None = None) -> dict:
    """Generate the weekly review data structure.

    Parameters
    ----------
    session : Session
        SQLModel database session.
    today : date | None
        Override for today's date (useful for testing). Defaults to date.today().

    Returns
    -------
    dict
        Complete weekly review data with all seven sections.
    """
    if today is None:
        today = date.today()

    # Cutoff is 7 days ago at midnight
    cutoff = datetime.combine(today - timedelta(days=7), datetime.min.time())

    campaigns = session.exec(
        select(Campaign)
        .where(Campaign.status == CampaignStatus.active)
        .order_by(Campaign.priority_rank)
    ).all()

    # ---- 1. Scoreboard ----
    scoreboard = []
    for campaign in campaigns:
        blocks = _blocks_this_week(session, campaign.id, cutoff)
        target = campaign.weekly_block_target
        scoreboard.append({
            "name": campaign.name,
            "colour": campaign.colour,
            "priority_rank": campaign.priority_rank,
            "blocks_completed": blocks,
            "weekly_target": target,
            "completion_pct": round(blocks / target * 100) if target > 0 else 0,
        })

    # ---- 2. Missions moved ----
    missions_moved = []
    # Missions completed this week
    completed_missions = session.exec(
        select(Mission)
        .where(Mission.completed_at >= cutoff)
        .where(Mission.completed_at.is_not(None))  # type: ignore[union-attr]
    ).all()
    for m in completed_missions:
        campaign = session.get(Campaign, m.campaign_id)
        campaign_name = campaign.name if campaign else "Unknown"
        missions_moved.append({
            "name": m.name,
            "campaign_name": campaign_name,
            "old_status": "in_progress",
            "new_status": m.status.value,
        })

    # Missions started this week (created recently with in_progress status)
    started_missions = session.exec(
        select(Mission)
        .where(Mission.created_at >= cutoff)
        .where(Mission.status == MissionStatus.in_progress)
    ).all()
    # Avoid duplicates with completed
    completed_ids = {m.id for m in completed_missions}
    for m in started_missions:
        if m.id not in completed_ids:
            campaign = session.get(Campaign, m.campaign_id)
            campaign_name = campaign.name if campaign else "Unknown"
            missions_moved.append({
                "name": m.name,
                "campaign_name": campaign_name,
                "old_status": "not_started",
                "new_status": m.status.value,
            })

    # ---- 3. Drift summary ----
    drift_summary = _compute_drift_summary(session, campaigns, cutoff)

    # ---- 4. Staleness alerts ----
    staleness_alerts = []
    for campaign in campaigns:
        days = compute_staleness(session, campaign.id)
        if days > 5:
            staleness_alerts.append({
                "name": campaign.name,
                "days": days,
            })

    # ---- 5. Energy patterns ----
    checkins = session.exec(
        select(DailyCheckIn)
        .where(DailyCheckIn.date >= today - timedelta(days=7))
        .where(DailyCheckIn.date <= today)
        .order_by(DailyCheckIn.date)
    ).all()

    daily_energy: list[dict] = []
    total_energy = 0
    for ci in checkins:
        val = ENERGY_VALUES.get(ci.energy_level, 2)
        total_energy += val
        daily_energy.append({
            "date": ci.date.isoformat(),
            "short_day": DAY_SHORT_NAMES[ci.date.weekday()],
            "level": ci.energy_level.value,
        })

    avg_energy = total_energy / len(checkins) if checkins else 0
    avg_label = ENERGY_LABELS.get(round(avg_energy), "yellow") if checkins else "none"

    energy_patterns = {
        "checkins": len(checkins),
        "daily": daily_energy,
        "average": round(avg_energy, 1) if checkins else 0,
        "average_label": avg_label,
    }

    # ---- 6. Current rankings ----
    current_rankings = [
        {"name": c.name, "rank": c.priority_rank}
        for c in campaigns
    ]

    # ---- 7. Next week preview ----
    next_week_start = today + timedelta(days=1)
    next_week_end = today + timedelta(days=8)

    # Upcoming target dates (campaigns and missions)
    upcoming_targets: list[dict] = []
    for c in campaigns:
        if c.target_date and next_week_start <= c.target_date <= next_week_end:
            upcoming_targets.append({
                "type": "campaign",
                "name": c.name,
                "target_date": c.target_date.isoformat(),
            })
        missions = session.exec(
            select(Mission).where(Mission.campaign_id == c.id)
        ).all()
        for m in missions:
            if m.target_date and next_week_start <= m.target_date <= next_week_end:
                upcoming_targets.append({
                    "type": "mission",
                    "name": f"{c.name} > {m.name}",
                    "target_date": m.target_date.isoformat(),
                })

    # Blocked sorties
    blocked_sorties_list = session.exec(
        select(Sortie)
        .join(Mission, col(Sortie.mission_id) == col(Mission.id))
        .join(Campaign, col(Mission.campaign_id) == col(Campaign.id))
        .where(Campaign.status == CampaignStatus.active)
        .where(
            Mission.status == MissionStatus.blocked
        )
    ).all()
    blocked_sorties = []
    for s in blocked_sorties_list:
        mission = session.get(Mission, s.mission_id)
        campaign = session.get(Campaign, mission.campaign_id) if mission else None
        blocked_sorties.append({
            "title": s.title,
            "mission_name": mission.name if mission else "Unknown",
            "campaign_name": campaign.name if campaign else "Unknown",
        })

    next_week_preview = {
        "upcoming_targets": upcoming_targets,
        "blocked_sorties": blocked_sorties,
    }

    return {
        "date": today.isoformat(),
        "week_ending": today.isoformat(),
        "scoreboard": scoreboard,
        "missions_moved": missions_moved,
        "drift_summary": drift_summary,
        "staleness_alerts": staleness_alerts,
        "energy_patterns": energy_patterns,
        "current_rankings": current_rankings,
        "next_week_preview": next_week_preview,
    }


def generate_weekly_review_markdown(session: Session, today: date | None = None) -> str:
    """Generate the weekly review as markdown.

    Parameters
    ----------
    session : Session
        SQLModel database session.
    today : date | None
        Override for today's date (useful for testing). Defaults to date.today().

    Returns
    -------
    str
        Complete weekly review formatted as markdown.
    """
    data = generate_weekly_review(session, today=today)

    lines = [f"# \u632f\u308a\u8fd4\u308a Weekly Review \u2014 {data['week_ending']}", ""]

    # ---- Scoreboard ----
    lines.append("## Scoreboard")
    if data["scoreboard"]:
        for s in data["scoreboard"]:
            bar = "\u2588" * s["blocks_completed"] + "\u2591" * max(0, s["weekly_target"] - s["blocks_completed"])
            lines.append(
                f"- **{s['name']}**: {s['blocks_completed']}/{s['weekly_target']} "
                f"blocks [{bar}] ({s['completion_pct']}%)"
            )
    else:
        lines.append("- No active campaigns")
    lines.append("")

    # ---- Missions moved ----
    lines.append("## Missions Moved")
    if data["missions_moved"]:
        for m in data["missions_moved"]:
            lines.append(
                f"- {m['campaign_name']} \u2192 **{m['name']}**: "
                f"{m['old_status']} \u2192 {m['new_status']}"
            )
    else:
        lines.append("- No mission status changes this week")
    lines.append("")

    # ---- Drift summary ----
    lines.append("## Drift Summary")
    if data["drift_summary"]:
        misaligned = [d for d in data["drift_summary"] if d["is_misaligned"]]
        if misaligned:
            for d in misaligned:
                direction = "over" if d["drift"] > 0 else "under"
                lines.append(
                    f"- **{d['name']}**: {direction}-allocated by "
                    f"{abs(d['drift']) * 100:.0f}%"
                )
        else:
            lines.append("- All campaigns within alignment thresholds")
    else:
        lines.append("- No drift data available")
    lines.append("")

    # ---- Staleness alerts ----
    lines.append("## Staleness Alerts")
    if data["staleness_alerts"]:
        for a in data["staleness_alerts"]:
            lines.append(f"- \u26a0\ufe0f **{a['name']}** untouched for {a['days']} days")
    else:
        lines.append("- All campaigns active this week")
    lines.append("")

    # ---- Energy patterns ----
    lines.append("## Energy Patterns")
    ep = data["energy_patterns"]
    if ep["checkins"] > 0:
        day_labels = " ".join(d["short_day"] for d in ep["daily"])
        day_levels = " ".join(
            {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}.get(d["level"], "\u26aa")
            for d in ep["daily"]
        )
        lines.append(f"  {day_labels}")
        lines.append(f"  {day_levels}")
        lines.append(f"- Average energy: **{ep['average_label']}** ({ep['average']})")
    else:
        lines.append("- No check-ins recorded this week")
    lines.append("")

    # ---- Re-rank prompt ----
    lines.append("## Re-rank Your Campaigns")
    lines.append("Current priority order:")
    for r in data["current_rankings"]:
        lines.append(f"  {r['rank']}. {r['name']}")
    lines.append("")

    # ---- Next week preview ----
    lines.append("## Next Week Preview")
    nwp = data["next_week_preview"]
    if nwp["upcoming_targets"]:
        lines.append("**Upcoming deadlines:**")
        for t in nwp["upcoming_targets"]:
            lines.append(f"- {t['name']} \u2014 {t['target_date']}")
    if nwp["blocked_sorties"]:
        lines.append("**Blocked sorties:**")
        for b in nwp["blocked_sorties"]:
            lines.append(f"- {b['campaign_name']} > {b['mission_name']} > {b['title']}")
    if not nwp["upcoming_targets"] and not nwp["blocked_sorties"]:
        lines.append("- No upcoming deadlines or blocked work")
    lines.append("")

    return "\n".join(lines)
