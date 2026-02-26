"""SQLModel data models for Senryaku — all 5 entities and 6 enums."""

import enum
from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CampaignStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    archived = "archived"


class MissionStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"


class SortieStatus(str, enum.Enum):
    queued = "queued"
    active = "active"
    completed = "completed"
    abandoned = "abandoned"


class CognitiveLoad(str, enum.Enum):
    deep = "deep"
    medium = "medium"
    light = "light"


class EnergyLevel(str, enum.Enum):
    green = "green"
    yellow = "yellow"
    red = "red"


class AAROutcome(str, enum.Enum):
    completed = "completed"
    partial = "partial"
    blocked = "blocked"
    pivoted = "pivoted"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Campaign(SQLModel, table=True):
    __tablename__ = "campaign"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    description: str
    status: CampaignStatus
    priority_rank: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column_kwargs={"onupdate": datetime.utcnow},
    )
    target_date: Optional[date] = Field(default=None)
    weekly_block_target: int
    colour: str
    tags: str

    missions: List["Mission"] = Relationship(back_populates="campaign")


class Mission(SQLModel, table=True):
    __tablename__ = "mission"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    campaign_id: UUID = Field(foreign_key="campaign.id")
    name: str
    description: str
    status: MissionStatus
    target_date: Optional[date] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    sort_order: int

    campaign: Optional[Campaign] = Relationship(back_populates="missions")
    sorties: List["Sortie"] = Relationship(back_populates="mission")


class Sortie(SQLModel, table=True):
    __tablename__ = "sortie"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    mission_id: UUID = Field(foreign_key="mission.id")
    title: str
    description: Optional[str] = Field(default=None)
    cognitive_load: CognitiveLoad
    estimated_blocks: int
    status: SortieStatus
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    sort_order: int

    mission: Optional[Mission] = Relationship(back_populates="sorties")
    aar: Optional["AAR"] = Relationship(back_populates="sortie")


class AAR(SQLModel, table=True):
    __tablename__ = "aar"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sortie_id: UUID = Field(foreign_key="sortie.id")
    energy_before: EnergyLevel
    energy_after: EnergyLevel
    outcome: AAROutcome
    notes: Optional[str] = Field(default=None)
    actual_blocks: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

    sortie: Optional[Sortie] = Relationship(back_populates="aar")


class DailyCheckIn(SQLModel, table=True):
    __tablename__ = "dailycheckin"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    date: date
    energy_level: EnergyLevel
    available_blocks: int
    focus_note: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
