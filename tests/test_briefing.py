"""Tests for the briefing algorithm service."""

import os

os.environ["SENRYAKU_API_KEY"] = "test-key"

from datetime import datetime, timedelta

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
from senryaku.services.briefing import compute_urgency_score, generate_briefing


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_campaign(
    session: Session,
    name: str = "Test Campaign",
    priority_rank: int = 1,
    weekly_block_target: int = 5,
    status: CampaignStatus = CampaignStatus.active,
    **kwargs,
) -> Campaign:
    c = Campaign(
        name=name,
        priority_rank=priority_rank,
        weekly_block_target=weekly_block_target,
        status=status,
        description="",
        colour=kwargs.pop("colour", "#6366f1"),
        tags="",
        **kwargs,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def make_mission(
    session: Session,
    campaign_id,
    name: str = "Mission",
    status: MissionStatus = MissionStatus.in_progress,
    **kwargs,
) -> Mission:
    m = Mission(
        campaign_id=campaign_id,
        name=name,
        description="",
        status=status,
        sort_order=kwargs.pop("sort_order", 0),
        **kwargs,
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m


def make_sortie(
    session: Session,
    mission_id,
    title: str = "Sortie",
    cognitive_load: CognitiveLoad = CognitiveLoad.medium,
    estimated_blocks: int = 1,
    status: SortieStatus = SortieStatus.queued,
    sort_order: int = 0,
    **kwargs,
) -> Sortie:
    s = Sortie(
        mission_id=mission_id,
        title=title,
        cognitive_load=cognitive_load,
        estimated_blocks=estimated_blocks,
        status=status,
        sort_order=sort_order,
        **kwargs,
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def make_aar(
    session: Session,
    sortie_id,
    actual_blocks: int = 1,
    created_at: datetime | None = None,
) -> AAR:
    aar = AAR(
        sortie_id=sortie_id,
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
# compute_urgency_score tests
# ---------------------------------------------------------------------------


class TestComputeUrgencyScore:
    def test_high_priority_with_deficit(self, session: Session):
        """Campaign with deficit and high priority -> higher urgency."""
        # Campaign rank 1 of 2, target=5, 0 blocks done this week
        # priority_weight = (2-1+1)/2 = 1.0
        # deficit = max(0, 5-0) = 5
        # staleness = 999 (no completed sorties)
        # urgency = 5 * 1.0 + 999 * 0.5 = 504.5
        c = make_campaign(session, name="High Priority", priority_rank=1, weekly_block_target=5)
        make_mission(session, c.id)

        score = compute_urgency_score(session, c, num_campaigns=2)
        assert score == pytest.approx(5 * 1.0 + 999 * 0.5)

    def test_no_deficit_only_staleness(self, session: Session):
        """Campaign with no deficit -> only staleness contribution."""
        c = make_campaign(session, name="Met Target", priority_rank=1, weekly_block_target=2)
        m = make_mission(session, c.id)
        # Complete 2 blocks this week -> deficit = 0
        s = make_sortie(
            session, m.id, status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
        )
        make_aar(session, s.id, actual_blocks=2, created_at=datetime.utcnow())

        score = compute_urgency_score(session, c, num_campaigns=1)
        # deficit = max(0, 2-2) = 0
        # staleness = 0 (completed today)
        # urgency = 0 * 1.0 + 0 * 0.5 = 0.0
        assert score == pytest.approx(0.0)

    def test_multiple_campaigns_highest_priority_biggest_deficit_scores_highest(self, session: Session):
        """Among multiple campaigns, highest priority with biggest deficit scores highest."""
        # Campaign A: rank 1, target=10, 0 blocks done
        c_a = make_campaign(session, name="Campaign A", priority_rank=1, weekly_block_target=10)
        make_mission(session, c_a.id)

        # Campaign B: rank 2, target=3, 0 blocks done
        c_b = make_campaign(session, name="Campaign B", priority_rank=2, weekly_block_target=3, colour="#FF0000")
        make_mission(session, c_b.id)

        score_a = compute_urgency_score(session, c_a, num_campaigns=2)
        score_b = compute_urgency_score(session, c_b, num_campaigns=2)

        # A: priority_weight = (2-1+1)/2 = 1.0, deficit=10
        #    urgency_a = 10*1.0 + 999*0.5 = 509.5
        # B: priority_weight = (2-2+1)/2 = 0.5, deficit=3
        #    urgency_b = 3*0.5 + 999*0.5 = 501.0
        assert score_a > score_b


# ---------------------------------------------------------------------------
# generate_briefing — energy filtering tests
# ---------------------------------------------------------------------------


class TestEnergyFiltering:
    def test_green_includes_all_loads(self, session: Session):
        """Green energy -> includes deep, medium, light sorties."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        make_sortie(session, m.id, title="Deep", cognitive_load=CognitiveLoad.deep, sort_order=0)
        make_sortie(session, m.id, title="Medium", cognitive_load=CognitiveLoad.medium, sort_order=1)
        make_sortie(session, m.id, title="Light", cognitive_load=CognitiveLoad.light, sort_order=2)

        result = generate_briefing(session, EnergyLevel.green, available_blocks=10)
        titles = [s.title for s in result]
        assert "Deep" in titles
        assert "Medium" in titles
        assert "Light" in titles

    def test_yellow_excludes_deep(self, session: Session):
        """Yellow energy -> excludes deep sorties (only medium + light)."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        make_sortie(session, m.id, title="Deep", cognitive_load=CognitiveLoad.deep, sort_order=0)
        make_sortie(session, m.id, title="Medium", cognitive_load=CognitiveLoad.medium, sort_order=1)
        make_sortie(session, m.id, title="Light", cognitive_load=CognitiveLoad.light, sort_order=2)

        result = generate_briefing(session, EnergyLevel.yellow, available_blocks=10)
        titles = [s.title for s in result]
        assert "Deep" not in titles
        assert "Medium" in titles
        assert "Light" in titles

    def test_red_only_light(self, session: Session):
        """Red energy -> only light sorties."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        make_sortie(session, m.id, title="Deep", cognitive_load=CognitiveLoad.deep, sort_order=0)
        make_sortie(session, m.id, title="Medium", cognitive_load=CognitiveLoad.medium, sort_order=1)
        make_sortie(session, m.id, title="Light", cognitive_load=CognitiveLoad.light, sort_order=2)

        result = generate_briefing(session, EnergyLevel.red, available_blocks=10)
        titles = [s.title for s in result]
        assert "Deep" not in titles
        assert "Medium" not in titles
        assert "Light" in titles

    def test_no_sorties_match_energy(self, session: Session):
        """No sorties match energy filter -> empty list."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        # Only deep sorties, but energy is red
        make_sortie(session, m.id, title="Deep", cognitive_load=CognitiveLoad.deep, sort_order=0)

        result = generate_briefing(session, EnergyLevel.red, available_blocks=10)
        assert result == []


# ---------------------------------------------------------------------------
# generate_briefing — capacity tests
# ---------------------------------------------------------------------------


class TestCapacity:
    def test_respects_available_blocks(self, session: Session):
        """Available blocks = 3, 5 queued sorties -> returns only 3."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        for i in range(5):
            make_sortie(
                session, m.id,
                title=f"Sortie {i}",
                cognitive_load=CognitiveLoad.medium,
                estimated_blocks=1,
                sort_order=i,
            )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=3)
        assert len(result) == 3
        total_blocks = sum(s.estimated_blocks for s in result)
        assert total_blocks == 3

    def test_multi_block_sortie_fills_correctly(self, session: Session):
        """Sortie with estimated_blocks=2 fills 2 slots."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        make_sortie(
            session, m.id, title="Big Sortie",
            cognitive_load=CognitiveLoad.medium,
            estimated_blocks=2, sort_order=0,
        )
        make_sortie(
            session, m.id, title="Small Sortie",
            cognitive_load=CognitiveLoad.medium,
            estimated_blocks=1, sort_order=1,
        )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=3)
        total_blocks = sum(s.estimated_blocks for s in result)
        assert total_blocks == 3
        titles = [s.title for s in result]
        assert "Big Sortie" in titles
        assert "Small Sortie" in titles


# ---------------------------------------------------------------------------
# generate_briefing — 60% cap tests
# ---------------------------------------------------------------------------


class TestSixtyCap:
    def test_cap_prevents_single_campaign_dominance(self, session: Session):
        """5 available blocks, 2 campaigns: campaign A should not take more than 3 blocks (60% of 5)."""
        c_a = make_campaign(
            session, name="Campaign A", priority_rank=1,
            weekly_block_target=10,
        )
        m_a = make_mission(session, c_a.id, name="Mission A")
        for i in range(5):
            make_sortie(
                session, m_a.id, title=f"A-Sortie-{i}",
                cognitive_load=CognitiveLoad.medium,
                estimated_blocks=1, sort_order=i,
            )

        c_b = make_campaign(
            session, name="Campaign B", priority_rank=2,
            weekly_block_target=10, colour="#FF0000",
        )
        m_b = make_mission(session, c_b.id, name="Mission B")
        for i in range(5):
            make_sortie(
                session, m_b.id, title=f"B-Sortie-{i}",
                cognitive_load=CognitiveLoad.medium,
                estimated_blocks=1, sort_order=i,
            )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=5)

        # Count blocks per campaign
        a_blocks = sum(s.estimated_blocks for s in result if s.campaign_name == "Campaign A")
        b_blocks = sum(s.estimated_blocks for s in result if s.campaign_name == "Campaign B")

        assert a_blocks <= 3  # 60% of 5 = 3
        assert b_blocks <= 3
        assert a_blocks + b_blocks == 5

    def test_single_campaign_no_cap(self, session: Session):
        """Single active campaign -> no 60% cap applies."""
        c = make_campaign(session, name="Only Campaign", priority_rank=1, weekly_block_target=10)
        m = make_mission(session, c.id)
        for i in range(5):
            make_sortie(
                session, m.id, title=f"Sortie {i}",
                cognitive_load=CognitiveLoad.medium,
                estimated_blocks=1, sort_order=i,
            )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=5)
        total_blocks = sum(s.estimated_blocks for s in result)
        assert total_blocks == 5
        # All from single campaign
        assert all(s.campaign_name == "Only Campaign" for s in result)


# ---------------------------------------------------------------------------
# generate_briefing — ordering tests
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_higher_urgency_campaigns_first(self, session: Session):
        """Sorties from higher-urgency campaigns appear first."""
        # Campaign A: rank 1, high target, no blocks done -> high urgency
        c_a = make_campaign(
            session, name="Urgent", priority_rank=1, weekly_block_target=10,
        )
        m_a = make_mission(session, c_a.id, name="Mission A")
        make_sortie(
            session, m_a.id, title="Urgent-Sortie",
            cognitive_load=CognitiveLoad.medium, sort_order=0,
        )

        # Campaign B: rank 2, low target, blocks done -> low urgency
        c_b = make_campaign(
            session, name="Relaxed", priority_rank=2, weekly_block_target=1,
            colour="#FF0000",
        )
        m_b = make_mission(session, c_b.id, name="Mission B")
        # Complete some work so deficit is 0
        s_done = make_sortie(
            session, m_b.id, title="Done",
            cognitive_load=CognitiveLoad.medium,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
            sort_order=0,
        )
        make_aar(session, s_done.id, actual_blocks=1, created_at=datetime.utcnow())
        make_sortie(
            session, m_b.id, title="Relaxed-Sortie",
            cognitive_load=CognitiveLoad.medium, sort_order=1,
        )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=5)
        assert len(result) >= 2
        # First sortie should be from the urgent campaign
        assert result[0].campaign_name == "Urgent"

    def test_within_campaign_maintains_sort_order(self, session: Session):
        """Within same campaign, maintain sort_order."""
        c = make_campaign(session, weekly_block_target=10)
        m = make_mission(session, c.id)
        make_sortie(session, m.id, title="Third", cognitive_load=CognitiveLoad.medium, sort_order=2)
        make_sortie(session, m.id, title="First", cognitive_load=CognitiveLoad.medium, sort_order=0)
        make_sortie(session, m.id, title="Second", cognitive_load=CognitiveLoad.medium, sort_order=1)

        result = generate_briefing(session, EnergyLevel.green, available_blocks=10)
        titles = [s.title for s in result]
        assert titles == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# generate_briefing — empty state tests
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_no_queued_sorties(self, session: Session):
        """No queued sorties -> empty list."""
        c = make_campaign(session)
        m = make_mission(session, c.id)
        # Only a completed sortie exists
        make_sortie(
            session, m.id, title="Completed",
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
        )

        result = generate_briefing(session, EnergyLevel.green, available_blocks=5)
        assert result == []

    def test_no_campaigns(self, session: Session):
        """No campaigns -> empty list."""
        result = generate_briefing(session, EnergyLevel.green, available_blocks=5)
        assert result == []
