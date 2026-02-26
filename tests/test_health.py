"""Tests for the campaign health computation service."""

import os

os.environ["SENRYAKU_API_KEY"] = "test-key"

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from senryaku.models import (
    AAR,
    AAROutcome,
    Campaign,
    CampaignStatus,
    CognitiveLoad,
    EnergyLevel,
    Mission,
    MissionStatus,
    Sortie,
    SortieStatus,
)
from senryaku.schemas import CampaignHealth
from senryaku.services.health import (
    compute_campaign_health,
    compute_staleness,
    compute_velocity,
    get_dashboard_data,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_campaign(
    session: Session,
    *,
    name: str = "Test Campaign",
    status: CampaignStatus = CampaignStatus.active,
    weekly_block_target: int = 5,
    priority_rank: int = 1,
    colour: str = "#6366f1",
) -> Campaign:
    """Helper to create and persist a campaign."""
    campaign = Campaign(
        name=name,
        description="Test campaign description",
        status=status,
        priority_rank=priority_rank,
        weekly_block_target=weekly_block_target,
        colour=colour,
        tags="",
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def _make_mission(
    session: Session,
    campaign: Campaign,
    *,
    name: str = "Test Mission",
    status: MissionStatus = MissionStatus.in_progress,
    sort_order: int = 1,
) -> Mission:
    """Helper to create and persist a mission."""
    mission = Mission(
        campaign_id=campaign.id,
        name=name,
        description="Test mission description",
        status=status,
        sort_order=sort_order,
    )
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return mission


def _make_sortie(
    session: Session,
    mission: Mission,
    *,
    title: str = "Test Sortie",
    status: SortieStatus = SortieStatus.queued,
    sort_order: int = 1,
    completed_at: datetime | None = None,
) -> Sortie:
    """Helper to create and persist a sortie."""
    sortie = Sortie(
        mission_id=mission.id,
        title=title,
        cognitive_load=CognitiveLoad.medium,
        estimated_blocks=1,
        status=status,
        sort_order=sort_order,
        completed_at=completed_at,
    )
    session.add(sortie)
    session.commit()
    session.refresh(sortie)
    return sortie


def _make_aar(
    session: Session,
    sortie: Sortie,
    *,
    actual_blocks: int = 1,
    created_at: datetime | None = None,
) -> AAR:
    """Helper to create and persist an AAR."""
    aar = AAR(
        sortie_id=sortie.id,
        energy_before=EnergyLevel.green,
        energy_after=EnergyLevel.yellow,
        outcome=AAROutcome.completed,
        actual_blocks=actual_blocks,
    )
    if created_at is not None:
        aar.created_at = created_at
    session.add(aar)
    session.commit()
    session.refresh(aar)
    return aar


# ---------------------------------------------------------------------------
# compute_staleness tests
# ---------------------------------------------------------------------------


class TestComputeStaleness:
    def test_sortie_completed_today(self, session: Session):
        """Campaign with sortie completed today -> staleness = 0."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
        )

        result = compute_staleness(session, campaign.id)
        assert result == 0

    def test_sortie_completed_3_days_ago(self, session: Session):
        """Campaign with sortie completed 3 days ago -> staleness = 3."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow() - timedelta(days=3),
        )

        result = compute_staleness(session, campaign.id)
        assert result == 3

    def test_no_completed_sorties(self, session: Session):
        """Campaign with no completed sorties -> staleness = 999."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        # Create a queued sortie (not completed)
        _make_sortie(session, mission, status=SortieStatus.queued)

        result = compute_staleness(session, campaign.id)
        assert result == 999

    def test_no_sorties_at_all(self, session: Session):
        """Campaign with no sorties at all -> staleness = 999."""
        campaign = _make_campaign(session)
        _make_mission(session, campaign)

        result = compute_staleness(session, campaign.id)
        assert result == 999

    def test_uses_most_recent_completed_sortie(self, session: Session):
        """When multiple completed sorties exist, use the most recent one."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        # Older completion
        _make_sortie(
            session,
            mission,
            title="Old sortie",
            status=SortieStatus.completed,
            completed_at=datetime.utcnow() - timedelta(days=10),
            sort_order=1,
        )
        # Recent completion
        _make_sortie(
            session,
            mission,
            title="Recent sortie",
            status=SortieStatus.completed,
            completed_at=datetime.utcnow() - timedelta(days=2),
            sort_order=2,
        )

        result = compute_staleness(session, campaign.id)
        assert result == 2


# ---------------------------------------------------------------------------
# compute_velocity tests
# ---------------------------------------------------------------------------


class TestComputeVelocity:
    def test_three_aars_in_last_7_days(self, session: Session):
        """Campaign with 3 AARs in last 7 days (actual_blocks: 1, 2, 1) -> velocity = 4."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        for i, blocks in enumerate([1, 2, 1]):
            sortie = _make_sortie(
                session,
                mission,
                title=f"Sortie {i}",
                status=SortieStatus.completed,
                completed_at=now - timedelta(days=i),
                sort_order=i,
            )
            _make_aar(
                session,
                sortie,
                actual_blocks=blocks,
                created_at=now - timedelta(days=i),
            )

        result = compute_velocity(session, campaign.id)
        assert result == 4

    def test_aars_older_than_7_days(self, session: Session):
        """Campaign with AARs older than 7 days -> velocity = 0."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)

        old_time = datetime.utcnow() - timedelta(days=10)
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=old_time,
        )
        _make_aar(session, sortie, actual_blocks=3, created_at=old_time)

        result = compute_velocity(session, campaign.id)
        assert result == 0

    def test_no_aars(self, session: Session):
        """Campaign with no AARs -> velocity = 0."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(session, mission, status=SortieStatus.queued)

        result = compute_velocity(session, campaign.id)
        assert result == 0

    def test_mixed_recent_and_old_aars(self, session: Session):
        """Only AARs within 7 days are counted."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # Recent AAR (2 blocks)
        sortie_recent = _make_sortie(
            session,
            mission,
            title="Recent",
            status=SortieStatus.completed,
            completed_at=now - timedelta(days=1),
            sort_order=1,
        )
        _make_aar(
            session, sortie_recent, actual_blocks=2, created_at=now - timedelta(days=1)
        )

        # Old AAR (5 blocks) - should NOT be counted
        sortie_old = _make_sortie(
            session,
            mission,
            title="Old",
            status=SortieStatus.completed,
            completed_at=now - timedelta(days=10),
            sort_order=2,
        )
        _make_aar(
            session, sortie_old, actual_blocks=5, created_at=now - timedelta(days=10)
        )

        result = compute_velocity(session, campaign.id)
        assert result == 2


# ---------------------------------------------------------------------------
# compute_campaign_health tests
# ---------------------------------------------------------------------------


class TestComputeCampaignHealth:
    def test_green_high_adherence_low_staleness(self, session: Session):
        """80%+ adherence and <=3 days staleness -> green."""
        campaign = _make_campaign(session, weekly_block_target=5)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # 4 blocks in last 7 days = 80% of target 5
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now,
        )
        _make_aar(session, sortie, actual_blocks=4, created_at=now)

        result = compute_campaign_health(session, campaign)
        assert result == "green"

    def test_yellow_medium_adherence(self, session: Session):
        """50% adherence and <=7 days staleness -> yellow (>=0.4 adherence)."""
        campaign = _make_campaign(session, weekly_block_target=10)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # 5 blocks in last 7 days = 50% of target 10
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now - timedelta(days=5),
        )
        _make_aar(session, sortie, actual_blocks=5, created_at=now - timedelta(days=1))

        result = compute_campaign_health(session, campaign)
        assert result == "yellow"

    def test_yellow_low_adherence_recent_staleness(self, session: Session):
        """20% adherence and <=5 days staleness -> yellow (staleness <=7)."""
        campaign = _make_campaign(session, weekly_block_target=10)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # 2 blocks = 20% of target 10, completed 5 days ago
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now - timedelta(days=5),
        )
        _make_aar(session, sortie, actual_blocks=2, created_at=now - timedelta(days=1))

        result = compute_campaign_health(session, campaign)
        assert result == "yellow"

    def test_red_low_adherence_high_staleness(self, session: Session):
        """20% adherence and 10 days stale -> red."""
        campaign = _make_campaign(session, weekly_block_target=10)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # 2 blocks but created 10 days ago -> velocity = 0 (outside 7 days)
        # staleness = 10 days
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now - timedelta(days=10),
        )
        _make_aar(
            session, sortie, actual_blocks=2, created_at=now - timedelta(days=10)
        )

        result = compute_campaign_health(session, campaign)
        assert result == "red"

    def test_zero_target_returns_green(self, session: Session):
        """Campaign with weekly_block_target=0 -> green (no work expected)."""
        campaign = _make_campaign(session, weekly_block_target=0)

        result = compute_campaign_health(session, campaign)
        assert result == "green"

    def test_brand_new_campaign_no_sorties(self, session: Session):
        """Brand new campaign, no sorties -> red (0 adherence, infinite staleness)."""
        campaign = _make_campaign(session, weekly_block_target=5)
        _make_mission(session, campaign)

        result = compute_campaign_health(session, campaign)
        assert result == "red"

    def test_over_100_percent_adherence_capped(self, session: Session):
        """Adherence capped at 1.0 even if velocity exceeds target."""
        campaign = _make_campaign(session, weekly_block_target=3)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        # 6 blocks vs target 3 = 200% -> capped at 100%
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now,
        )
        _make_aar(session, sortie, actual_blocks=6, created_at=now)

        result = compute_campaign_health(session, campaign)
        assert result == "green"


# ---------------------------------------------------------------------------
# get_dashboard_data tests
# ---------------------------------------------------------------------------


class TestGetDashboardData:
    def test_returns_campaign_health_objects(self, session: Session):
        """Returns list of CampaignHealth objects for all active campaigns."""
        campaign = _make_campaign(session, name="Active One")
        _make_mission(session, campaign)

        results = get_dashboard_data(session)

        assert len(results) == 1
        assert isinstance(results[0], CampaignHealth)
        assert results[0].name == "Active One"
        assert results[0].campaign_id == campaign.id

    def test_excludes_archived_campaigns(self, session: Session):
        """Archived campaigns are excluded from the dashboard."""
        _make_campaign(session, name="Active", status=CampaignStatus.active)
        _make_campaign(
            session,
            name="Archived",
            status=CampaignStatus.archived,
            priority_rank=2,
        )

        results = get_dashboard_data(session)

        assert len(results) == 1
        assert results[0].name == "Active"

    def test_includes_mission_counts(self, session: Session):
        """Includes missions_completed and missions_total counts."""
        campaign = _make_campaign(session)
        _make_mission(
            session, campaign, name="Done", status=MissionStatus.completed, sort_order=1
        )
        _make_mission(
            session,
            campaign,
            name="In Progress",
            status=MissionStatus.in_progress,
            sort_order=2,
        )
        _make_mission(
            session,
            campaign,
            name="Not Started",
            status=MissionStatus.not_started,
            sort_order=3,
        )

        results = get_dashboard_data(session)

        assert results[0].missions_total == 3
        assert results[0].missions_completed == 1

    def test_includes_next_sortie_title(self, session: Session):
        """Includes next_sortie_title (first queued sortie by sort_order)."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)

        _make_sortie(
            session,
            mission,
            title="Second queued",
            status=SortieStatus.queued,
            sort_order=2,
        )
        _make_sortie(
            session,
            mission,
            title="First queued",
            status=SortieStatus.queued,
            sort_order=1,
        )
        _make_sortie(
            session,
            mission,
            title="Completed one",
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
            sort_order=0,
        )

        results = get_dashboard_data(session)

        assert results[0].next_sortie_title == "First queued"

    def test_next_sortie_title_none_when_no_queued(self, session: Session):
        """next_sortie_title is None when no queued sorties exist."""
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
        )

        results = get_dashboard_data(session)

        assert results[0].next_sortie_title is None

    def test_ordered_by_priority_rank(self, session: Session):
        """Results are ordered by priority_rank."""
        _make_campaign(session, name="Second", priority_rank=2)
        _make_campaign(session, name="First", priority_rank=1, colour="#FF0000")

        results = get_dashboard_data(session)

        assert len(results) == 2
        assert results[0].name == "First"
        assert results[1].name == "Second"

    def test_includes_health_and_velocity(self, session: Session):
        """Result objects include computed health and velocity values."""
        campaign = _make_campaign(session, weekly_block_target=5)
        mission = _make_mission(session, campaign)

        now = datetime.utcnow()
        sortie = _make_sortie(
            session,
            mission,
            status=SortieStatus.completed,
            completed_at=now,
        )
        _make_aar(session, sortie, actual_blocks=4, created_at=now)

        results = get_dashboard_data(session)

        assert results[0].health == "green"
        assert results[0].velocity == 4
        assert results[0].staleness_days == 0
        assert results[0].weekly_block_target == 5
        assert results[0].blocks_this_week == 4

    def test_empty_when_no_active_campaigns(self, session: Session):
        """Returns empty list when no active campaigns exist."""
        _make_campaign(session, status=CampaignStatus.archived)

        results = get_dashboard_data(session)
        assert results == []
