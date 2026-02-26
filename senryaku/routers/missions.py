"""Mission CRUD API router."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from senryaku.database import get_session
from senryaku.models import Campaign, Mission, MissionStatus
from senryaku.schemas import MissionCreate, MissionRead, MissionUpdate

router = APIRouter()


@router.post("/missions", response_model=MissionRead, status_code=201)
def create_mission(
    mission_in: MissionCreate,
    session: Session = Depends(get_session),
):
    """Create a new mission linked to a campaign."""
    # Verify campaign exists
    campaign = session.get(Campaign, mission_in.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    mission = Mission(
        **mission_in.model_dump(),
        status=MissionStatus.not_started,
    )
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission


@router.get(
    "/campaigns/{campaign_id}/missions", response_model=List[MissionRead]
)
def list_missions(
    campaign_id: UUID,
    session: Session = Depends(get_session),
):
    """List all missions for a campaign, ordered by sort_order."""
    statement = (
        select(Mission)
        .where(Mission.campaign_id == campaign_id)
        .order_by(Mission.sort_order)
    )
    missions = session.exec(statement).all()
    return missions


@router.put("/missions/{mission_id}", response_model=MissionRead)
def update_mission(
    mission_id: UUID,
    mission_in: MissionUpdate,
    session: Session = Depends(get_session),
):
    """Update a mission. Only non-None fields are updated."""
    mission = session.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")

    update_data = mission_in.model_dump(exclude_unset=True)

    # If status is changing to completed, set completed_at
    if (
        "status" in update_data
        and update_data["status"] == MissionStatus.completed
        and mission.status != MissionStatus.completed
    ):
        mission.completed_at = datetime.utcnow()

    for key, value in update_data.items():
        setattr(mission, key, value)

    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission


@router.delete("/missions/{mission_id}", response_model=MissionRead)
def delete_mission(
    mission_id: UUID,
    session: Session = Depends(get_session),
):
    """Soft-delete a mission by setting its status to completed."""
    mission = session.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")

    mission.status = MissionStatus.completed
    if mission.completed_at is None:
        mission.completed_at = datetime.utcnow()
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission
