"""Sortie CRUD API router with start/complete lifecycle."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from senryaku.database import get_session
from senryaku.models import AAR, Campaign, Mission, Sortie, SortieStatus
from senryaku.schemas import (
    BulkStatusUpdate,
    MoveSortieRequest,
    SortieCompleteRequest,
    SortieCreate,
    SortieRead,
    SortieUpdate,
)

router = APIRouter()


@router.post("/sorties", response_model=SortieRead, status_code=201)
def create_sortie(
    sortie_in: SortieCreate,
    session: Session = Depends(get_session),
):
    """Create a new sortie linked to a mission."""
    # Verify mission exists
    mission = session.get(Mission, sortie_in.mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")

    sortie = Sortie(
        **sortie_in.model_dump(),
        status=SortieStatus.queued,
    )
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


@router.get(
    "/missions/{mission_id}/sorties", response_model=List[SortieRead]
)
def list_sorties(
    mission_id: UUID,
    session: Session = Depends(get_session),
):
    """List all sorties for a mission, ordered by sort_order."""
    statement = (
        select(Sortie)
        .where(Sortie.mission_id == mission_id)
        .order_by(Sortie.sort_order)
    )
    sorties = session.exec(statement).all()
    return sorties


# IMPORTANT: /sorties/queued must be defined BEFORE /sorties/{sortie_id}
# to avoid "queued" being parsed as an ID.
@router.get("/sorties/queued", response_model=List[SortieRead])
def list_queued_sorties(
    session: Session = Depends(get_session),
):
    """List all queued sorties across all campaigns."""
    statement = (
        select(Sortie)
        .join(Mission)
        .join(Campaign)
        .where(Sortie.status == SortieStatus.queued)
        .order_by(Campaign.priority_rank, Mission.sort_order, Sortie.sort_order)
    )
    sorties = session.exec(statement).all()
    return sorties


@router.put("/sorties/bulk")
def bulk_update_sorties(
    update: BulkStatusUpdate,
    session: Session = Depends(get_session),
):
    """Batch complete/abandon sorties."""
    updated = []
    for sortie_id in update.ids:
        sortie = session.get(Sortie, sortie_id)
        if sortie:
            sortie.status = update.status
            if update.status == SortieStatus.completed:
                sortie.completed_at = datetime.utcnow()
            session.add(sortie)
            updated.append(sortie)
    session.commit()
    return {"updated": len(updated)}


@router.put("/sorties/{sortie_id}/move")
def move_sortie(
    sortie_id: UUID,
    move: MoveSortieRequest,
    session: Session = Depends(get_session),
):
    """Move sortie to a different mission."""
    sortie = session.get(Sortie, sortie_id)
    if not sortie:
        raise HTTPException(status_code=404, detail="Sortie not found")
    new_mission = session.get(Mission, move.new_mission_id)
    if not new_mission:
        raise HTTPException(status_code=404, detail="Target mission not found")
    sortie.mission_id = move.new_mission_id
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


@router.put("/sorties/{sortie_id}", response_model=SortieRead)
def update_sortie(
    sortie_id: UUID,
    sortie_in: SortieUpdate,
    session: Session = Depends(get_session),
):
    """Update a sortie. Only non-None fields are updated."""
    sortie = session.get(Sortie, sortie_id)
    if sortie is None:
        raise HTTPException(status_code=404, detail="Sortie not found")

    update_data = sortie_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(sortie, key, value)

    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


@router.put("/sorties/{sortie_id}/start", response_model=SortieRead)
def start_sortie(
    sortie_id: UUID,
    session: Session = Depends(get_session),
):
    """Start a sortie: set status to active and started_at to now."""
    sortie = session.get(Sortie, sortie_id)
    if sortie is None:
        raise HTTPException(status_code=404, detail="Sortie not found")

    if sortie.status != SortieStatus.queued:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start sortie with status '{sortie.status.value}'",
        )

    sortie.status = SortieStatus.active
    sortie.started_at = datetime.utcnow()
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


@router.put("/sorties/{sortie_id}/complete", response_model=SortieRead)
def complete_sortie(
    sortie_id: UUID,
    aar_data: SortieCompleteRequest,
    session: Session = Depends(get_session),
):
    """Complete a sortie: create AAR record and update status based on outcome."""
    sortie = session.get(Sortie, sortie_id)
    if sortie is None:
        raise HTTPException(status_code=404, detail="Sortie not found")

    # Create the AAR record
    aar = AAR(
        sortie_id=sortie_id,
        energy_before=aar_data.energy_before,
        energy_after=aar_data.energy_after,
        outcome=aar_data.outcome,
        actual_blocks=aar_data.actual_blocks,
        notes=aar_data.notes,
    )
    session.add(aar)

    # Set sortie status based on outcome
    if aar_data.outcome.value == "completed":
        sortie.status = SortieStatus.completed
    # Otherwise keep current status (active)

    sortie.completed_at = datetime.utcnow()
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


@router.delete("/sorties/{sortie_id}", response_model=SortieRead)
def delete_sortie(
    sortie_id: UUID,
    session: Session = Depends(get_session),
):
    """Soft-delete a sortie by setting its status to abandoned."""
    sortie = session.get(Sortie, sortie_id)
    if sortie is None:
        raise HTTPException(status_code=404, detail="Sortie not found")

    sortie.status = SortieStatus.abandoned
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie
