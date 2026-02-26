"""Campaign health computation service.

Implements the health algorithm from PRD section 8.1:

    staleness = days_since_last_completed_sortie
    velocity  = completed_blocks_last_7_days  (sum of actual_blocks from AARs)
    target_adherence = velocity / weekly_block_target  (capped at 1.0)

    if target_adherence >= 0.8 and staleness <= 3:  health = "green"
    elif target_adherence >= 0.4 or staleness <= 7: health = "yellow"
    else:                                           health = "red"
"""

from datetime import datetime, timedelta
from uuid import UUID

from sqlmodel import Session, select, func, col

from senryaku.models import (
    AAR,
    Campaign,
    CampaignStatus,
    Mission,
    MissionStatus,
    Sortie,
    SortieStatus,
)
from senryaku.schemas import CampaignHealth


def compute_staleness(session: Session, campaign_id: UUID) -> int:
    """Days since last completed sortie for this campaign.

    Returns 999 if no completed sorties exist (sentinel for "never worked on").
    """
    statement = (
        select(func.max(Sortie.completed_at))
        .join(Mission, col(Sortie.mission_id) == col(Mission.id))
        .where(Mission.campaign_id == campaign_id)
        .where(Sortie.status == SortieStatus.completed)
        .where(Sortie.completed_at.is_not(None))  # type: ignore[union-attr]
    )
    last_completed = session.exec(statement).one()

    if last_completed is None:
        return 999

    delta = datetime.utcnow() - last_completed
    return delta.days


def compute_velocity(session: Session, campaign_id: UUID) -> int:
    """Total actual_blocks from AARs in last 7 days for this campaign.

    Joins AAR -> Sortie -> Mission where mission.campaign_id matches,
    filtering by AAR.created_at within the last 7 days.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)

    statement = (
        select(func.coalesce(func.sum(AAR.actual_blocks), 0))
        .join(Sortie, col(AAR.sortie_id) == col(Sortie.id))
        .join(Mission, col(Sortie.mission_id) == col(Mission.id))
        .where(Mission.campaign_id == campaign_id)
        .where(AAR.created_at >= cutoff)
    )
    result = session.exec(statement).one()
    return int(result)


def compute_campaign_health(session: Session, campaign: Campaign) -> str:
    """Returns 'green', 'yellow', or 'red' per PRD algorithm."""
    if campaign.weekly_block_target == 0:
        return "green"

    staleness = compute_staleness(session, campaign.id)
    velocity = compute_velocity(session, campaign.id)

    target_adherence = min(velocity / campaign.weekly_block_target, 1.0)

    if target_adherence >= 0.8 and staleness <= 3:
        return "green"
    elif target_adherence >= 0.4 or staleness <= 7:
        return "yellow"
    else:
        return "red"


def get_dashboard_data(session: Session) -> list[CampaignHealth]:
    """Get health data for all active campaigns, ordered by priority_rank."""
    campaigns = session.exec(
        select(Campaign)
        .where(Campaign.status == CampaignStatus.active)
        .order_by(Campaign.priority_rank)
    ).all()

    results = []
    for campaign in campaigns:
        # Count missions
        missions = session.exec(
            select(Mission).where(Mission.campaign_id == campaign.id)
        ).all()
        missions_total = len(missions)
        missions_completed = len(
            [m for m in missions if m.status == MissionStatus.completed]
        )

        # Get next queued sortie (first by sort_order)
        next_sortie = session.exec(
            select(Sortie)
            .join(Mission, col(Sortie.mission_id) == col(Mission.id))
            .where(Mission.campaign_id == campaign.id)
            .where(Sortie.status == SortieStatus.queued)
            .order_by(Sortie.sort_order)
        ).first()

        velocity = compute_velocity(session, campaign.id)
        staleness = compute_staleness(session, campaign.id)
        health = compute_campaign_health(session, campaign)

        results.append(
            CampaignHealth(
                campaign_id=campaign.id,
                name=campaign.name,
                colour=campaign.colour,
                priority_rank=campaign.priority_rank,
                health=health,
                velocity=velocity,
                weekly_block_target=campaign.weekly_block_target,
                blocks_this_week=velocity,
                staleness_days=staleness,
                missions_completed=missions_completed,
                missions_total=missions_total,
                next_sortie_title=next_sortie.title if next_sortie else None,
            )
        )

    return results
