"""Pydantic request/response schemas for the Senryaku API."""

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from senryaku.models import (
    AAROutcome,
    CampaignStatus,
    CognitiveLoad,
    EnergyLevel,
    MissionStatus,
    SortieStatus,
)


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str
    description: str = ""
    priority_rank: int
    weekly_block_target: int
    colour: str = "#6366f1"
    tags: str = ""
    target_date: Optional[date] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    priority_rank: Optional[int] = None
    weekly_block_target: Optional[int] = None
    colour: Optional[str] = None
    tags: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[CampaignStatus] = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    status: CampaignStatus
    priority_rank: int
    weekly_block_target: int
    colour: str
    tags: str
    target_date: Optional[date]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------


class MissionCreate(BaseModel):
    campaign_id: UUID
    name: str
    description: str = ""
    target_date: Optional[date] = None
    sort_order: int = 0


class MissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[date] = None
    sort_order: Optional[int] = None
    status: Optional[MissionStatus] = None


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    name: str
    description: str
    status: MissionStatus
    target_date: Optional[date]
    sort_order: int
    created_at: datetime
    completed_at: Optional[datetime]


# ---------------------------------------------------------------------------
# Sortie
# ---------------------------------------------------------------------------


class SortieCreate(BaseModel):
    mission_id: UUID
    title: str
    cognitive_load: CognitiveLoad
    description: Optional[str] = None
    estimated_blocks: int = 1
    sort_order: int = 0


class SortieUpdate(BaseModel):
    title: Optional[str] = None
    cognitive_load: Optional[CognitiveLoad] = None
    description: Optional[str] = None
    estimated_blocks: Optional[int] = None
    sort_order: Optional[int] = None
    status: Optional[SortieStatus] = None


class SortieRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mission_id: UUID
    title: str
    description: Optional[str]
    cognitive_load: CognitiveLoad
    estimated_blocks: int
    status: SortieStatus
    sort_order: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


# ---------------------------------------------------------------------------
# AAR
# ---------------------------------------------------------------------------


class AARCreate(BaseModel):
    sortie_id: UUID
    energy_before: EnergyLevel
    energy_after: EnergyLevel
    outcome: AAROutcome
    actual_blocks: int = 1
    notes: Optional[str] = None


class SortieCompleteRequest(BaseModel):
    """Body for PUT /sorties/{id}/complete — AAR data without sortie_id."""
    energy_before: EnergyLevel
    energy_after: EnergyLevel
    outcome: AAROutcome
    actual_blocks: int = 1
    notes: Optional[str] = None


class AARRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sortie_id: UUID
    energy_before: EnergyLevel
    energy_after: EnergyLevel
    outcome: AAROutcome
    actual_blocks: int
    notes: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# DailyCheckIn
# ---------------------------------------------------------------------------


class DailyCheckInCreate(BaseModel):
    date: date
    energy_level: EnergyLevel
    available_blocks: int
    focus_note: Optional[str] = None


class DailyCheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: date
    energy_level: EnergyLevel
    available_blocks: int
    focus_note: Optional[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Specialized: Briefing & Dashboard
# ---------------------------------------------------------------------------


class BriefingSortie(BaseModel):
    id: UUID
    title: str
    cognitive_load: CognitiveLoad
    estimated_blocks: int
    campaign_name: str
    campaign_colour: str
    mission_name: str
    campaign_id: UUID


class CampaignHealth(BaseModel):
    campaign_id: UUID
    name: str
    colour: str
    priority_rank: int
    health: str  # green / yellow / red
    velocity: int  # blocks last 7 days
    weekly_block_target: int
    blocks_this_week: int
    staleness_days: int
    missions_completed: int
    missions_total: int
    next_sortie_title: Optional[str]


class RerankItem(BaseModel):
    id: UUID
    rank: int


class RerankRequest(BaseModel):
    ranks: List[RerankItem]


class BulkStatusUpdate(BaseModel):
    """Body for PUT /sorties/bulk — batch update sortie statuses."""
    ids: List[UUID]
    status: SortieStatus


class MoveSortieRequest(BaseModel):
    """Body for PUT /sorties/{id}/move — move sortie to a different mission."""
    new_mission_id: UUID


class BriefingResponse(BaseModel):
    date: date
    energy_level: EnergyLevel
    available_blocks: int
    sorties: List[BriefingSortie]


# ---------------------------------------------------------------------------
# Drift Detection
# ---------------------------------------------------------------------------


class CampaignDrift(BaseModel):
    campaign_id: UUID
    name: str
    colour: str
    priority_rank: int
    weekly_block_target: int
    blocks_this_week: int
    expected_share: float  # 0.0 to 1.0
    actual_share: float    # 0.0 to 1.0
    drift: float           # actual - expected
    is_misaligned: bool    # abs(drift) > 0.15
    trend: str             # "improving", "worsening", "stable", "new"


class DriftReport(BaseModel):
    date: date
    total_blocks_this_week: int
    campaigns: List[CampaignDrift]
    misalignment_statements: List[str]
