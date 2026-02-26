"""Campaign CRUD API router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from senryaku.database import get_session
from senryaku.models import Campaign, CampaignStatus
from senryaku.schemas import (
    CampaignCreate,
    CampaignRead,
    CampaignUpdate,
    RerankRequest,
)

router = APIRouter()


@router.get("/campaigns", response_model=List[CampaignRead])
def list_campaigns(
    status: Optional[CampaignStatus] = Query(default=None),
    session: Session = Depends(get_session),
):
    """List all campaigns, optionally filtered by status."""
    statement = select(Campaign)
    if status is not None:
        statement = statement.where(Campaign.status == status)
    campaigns = session.exec(statement).all()
    return campaigns


@router.post("/campaigns", response_model=CampaignRead, status_code=201)
def create_campaign(
    campaign_in: CampaignCreate,
    session: Session = Depends(get_session),
):
    """Create a new campaign."""
    campaign = Campaign(
        **campaign_in.model_dump(),
        status=CampaignStatus.active,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


# IMPORTANT: rerank must be defined BEFORE {campaign_id} routes
# to avoid FastAPI treating "rerank" as a campaign_id.
@router.put("/campaigns/rerank", response_model=List[CampaignRead])
def rerank_campaigns(
    rerank: RerankRequest,
    session: Session = Depends(get_session),
):
    """Bulk reorder campaign priorities."""
    for item in rerank.ranks:
        campaign = session.get(Campaign, item.id)
        if campaign is None:
            raise HTTPException(
                status_code=404,
                detail=f"Campaign {item.id} not found",
            )
        campaign.priority_rank = item.rank
        session.add(campaign)
    session.commit()

    # Return all campaigns after reranking
    campaigns = session.exec(select(Campaign)).all()
    return campaigns


@router.get("/campaigns/{campaign_id}")
def get_campaign(
    campaign_id: UUID,
    session: Session = Depends(get_session),
):
    """Get a single campaign by ID, including its missions."""
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Build response with missions included
    data = CampaignRead.model_validate(campaign).model_dump()
    data["missions"] = [
        {
            "id": str(m.id),
            "campaign_id": str(m.campaign_id),
            "name": m.name,
            "description": m.description,
            "status": m.status,
            "target_date": str(m.target_date) if m.target_date else None,
            "sort_order": m.sort_order,
            "created_at": m.created_at.isoformat(),
            "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        }
        for m in campaign.missions
    ]
    return data


@router.put("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: UUID,
    campaign_in: CampaignUpdate,
    session: Session = Depends(get_session),
):
    """Update a campaign. Only non-None fields are updated."""
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    update_data = campaign_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(campaign, key, value)

    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


@router.delete("/campaigns/{campaign_id}", response_model=CampaignRead)
def delete_campaign(
    campaign_id: UUID,
    session: Session = Depends(get_session),
):
    """Soft-delete a campaign by setting its status to archived."""
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = CampaignStatus.archived
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign
