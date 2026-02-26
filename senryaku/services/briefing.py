"""Briefing algorithm service.

Implements the morning briefing from PRD sections 4.2 and 8.2:

    Urgency Score per campaign:
        priority_weight = (num_campaigns - priority_rank + 1) / num_campaigns
        deficit = max(0, weekly_block_target - blocks_this_week)
        urgency = deficit * priority_weight + staleness_days * 0.5

    Sortie selection:
        1. Calculate urgency score per active campaign
        2. Filter queued sorties by cognitive load matching energy level
        3. Sort filtered sorties by parent campaign urgency (descending)
        4. Greedy fill until available_blocks reached
        5. 60% cap: no single campaign takes >60% of blocks (unless only campaign)
        6. Return ordered list
"""

from datetime import date, datetime, timedelta
from uuid import UUID

from sqlmodel import Session, col, select

from senryaku.models import (
    Campaign,
    CampaignStatus,
    CognitiveLoad,
    EnergyLevel,
    Mission,
    Sortie,
    SortieStatus,
)
from senryaku.schemas import BriefingSortie, BriefingResponse
from senryaku.services.health import compute_staleness, compute_velocity

ENERGY_ALLOWED_LOADS: dict[EnergyLevel, set[CognitiveLoad]] = {
    EnergyLevel.green: {CognitiveLoad.deep, CognitiveLoad.medium, CognitiveLoad.light},
    EnergyLevel.yellow: {CognitiveLoad.medium, CognitiveLoad.light},
    EnergyLevel.red: {CognitiveLoad.light},
}


def compute_urgency_score(
    session: Session, campaign: Campaign, num_campaigns: int
) -> float:
    """Compute urgency score for a single campaign.

    Higher score = more urgent = should be worked on first.
    """
    priority_weight = (num_campaigns - campaign.priority_rank + 1) / num_campaigns
    blocks_this_week = compute_velocity(session, campaign.id)
    deficit = max(0, campaign.weekly_block_target - blocks_this_week)
    staleness = compute_staleness(session, campaign.id)
    return deficit * priority_weight + staleness * 0.5


def generate_briefing(
    session: Session, energy: EnergyLevel, available_blocks: int
) -> list[BriefingSortie]:
    """Generate a prioritised list of sorties for the morning briefing.

    Returns an ordered list of BriefingSortie objects that fit within
    the available_blocks budget, filtered by energy-appropriate cognitive
    loads, and balanced across campaigns via the 60% cap.
    """
    # Get active campaigns
    campaigns = session.exec(
        select(Campaign).where(Campaign.status == CampaignStatus.active)
    ).all()

    if not campaigns:
        return []

    num_campaigns = len(campaigns)

    # Compute urgency per campaign
    campaign_urgency: dict[UUID, float] = {}
    campaign_map: dict[UUID, Campaign] = {}
    for c in campaigns:
        campaign_urgency[c.id] = compute_urgency_score(session, c, num_campaigns)
        campaign_map[c.id] = c

    # Collect all queued sorties with campaign/mission context, filtered by energy
    allowed_loads = ENERGY_ALLOWED_LOADS[energy]

    sorties_with_context: list[dict] = []
    for campaign in campaigns:
        missions = session.exec(
            select(Mission).where(Mission.campaign_id == campaign.id)
        ).all()
        for mission in missions:
            queued_sorties = session.exec(
                select(Sortie)
                .where(Sortie.mission_id == mission.id)
                .where(Sortie.status == SortieStatus.queued)
                .order_by(Sortie.sort_order)
            ).all()
            for sortie in queued_sorties:
                if sortie.cognitive_load in allowed_loads:
                    sorties_with_context.append(
                        {
                            "sortie": sortie,
                            "mission": mission,
                            "campaign": campaign,
                            "urgency": campaign_urgency[campaign.id],
                        }
                    )

    # Sort by urgency descending, then by sort_order ascending
    sorties_with_context.sort(
        key=lambda x: (-x["urgency"], x["sortie"].sort_order)
    )

    # Greedy fill with 60% cap
    result: list[BriefingSortie] = []
    blocks_used = 0
    campaign_blocks: dict[UUID, int] = {}  # campaign_id -> blocks allocated
    max_blocks_per_campaign = max(1, int(available_blocks * 0.6))  # 60% cap

    for item in sorties_with_context:
        if blocks_used >= available_blocks:
            break

        sortie = item["sortie"]
        campaign = item["campaign"]

        current_campaign_blocks = campaign_blocks.get(campaign.id, 0)

        # Apply 60% cap only if multiple campaigns exist
        if (
            num_campaigns > 1
            and current_campaign_blocks + sortie.estimated_blocks
            > max_blocks_per_campaign
        ):
            continue

        if blocks_used + sortie.estimated_blocks > available_blocks:
            continue

        result.append(
            BriefingSortie(
                id=sortie.id,
                title=sortie.title,
                cognitive_load=sortie.cognitive_load,
                estimated_blocks=sortie.estimated_blocks,
                campaign_name=campaign.name,
                campaign_colour=campaign.colour,
                mission_name=item["mission"].name,
                campaign_id=campaign.id,
            )
        )

        blocks_used += sortie.estimated_blocks
        campaign_blocks[campaign.id] = current_campaign_blocks + sortie.estimated_blocks

    return result
