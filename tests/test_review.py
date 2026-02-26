"""Tests for the weekly review generator service."""

import os

os.environ["SENRYAKU_API_KEY"] = "test-key"

from datetime import date, datetime, timedelta
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
    DailyCheckIn,
    EnergyLevel,
    Mission,
    MissionStatus,
    Sortie,
    SortieStatus,
)
from senryaku.services.review import (
    generate_weekly_review,
    generate_weekly_review_markdown,
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
    target_date: date | None = None,
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
        target_date=target_date,
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
    completed_at: datetime | None = None,
    created_at: datetime | None = None,
    target_date: date | None = None,
) -> Mission:
    """Helper to create and persist a mission."""
    mission = Mission(
        campaign_id=campaign.id,
        name=name,
        description="Test mission description",
        status=status,
        sort_order=sort_order,
        completed_at=completed_at,
        target_date=target_date,
    )
    if created_at is not None:
        mission.created_at = created_at
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


def _make_checkin(
    session: Session,
    *,
    checkin_date: date,
    energy_level: EnergyLevel = EnergyLevel.green,
    available_blocks: int = 4,
) -> DailyCheckIn:
    """Helper to create and persist a daily check-in."""
    checkin = DailyCheckIn(
        date=checkin_date,
        energy_level=energy_level,
        available_blocks=available_blocks,
    )
    session.add(checkin)
    session.commit()
    session.refresh(checkin)
    return checkin


# ---------------------------------------------------------------------------
# Tests: generate_weekly_review
# ---------------------------------------------------------------------------


class TestEmptyState:
    """Test review with no data."""

    def test_empty_scoreboard(self, session: Session):
        """No campaigns -> empty scoreboard."""
        result = generate_weekly_review(session)
        assert result["scoreboard"] == []

    def test_empty_missions_moved(self, session: Session):
        """No campaigns -> no missions moved."""
        result = generate_weekly_review(session)
        assert result["missions_moved"] == []

    def test_empty_staleness_alerts(self, session: Session):
        """No campaigns -> no staleness alerts."""
        result = generate_weekly_review(session)
        assert result["staleness_alerts"] == []

    def test_empty_energy_patterns(self, session: Session):
        """No check-ins -> zero checkins in energy patterns."""
        result = generate_weekly_review(session)
        assert result["energy_patterns"]["checkins"] == 0
        assert result["energy_patterns"]["daily"] == []
        assert result["energy_patterns"]["average_label"] == "none"

    def test_empty_current_rankings(self, session: Session):
        """No campaigns -> empty rankings."""
        result = generate_weekly_review(session)
        assert result["current_rankings"] == []

    def test_date_fields_present(self, session: Session):
        """Review always has date and week_ending."""
        today = date(2026, 2, 22)
        result = generate_weekly_review(session, today=today)
        assert result["date"] == "2026-02-22"
        assert result["week_ending"] == "2026-02-22"


class TestScoreboard:
    """Test scoreboard section — blocks completed per campaign vs target."""

    def test_single_campaign_with_blocks(self, session: Session):
        """Campaign with AARs this week shows correct block count."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, weekly_block_target=5)
        mission = _make_mission(session, campaign)

        # Create 3 completed sorties with AARs this week
        for i in range(3):
            sortie = _make_sortie(
                session, mission,
                title=f"Sortie {i}",
                status=SortieStatus.completed,
                sort_order=i,
                completed_at=datetime(2026, 2, 20),
            )
            _make_aar(
                session, sortie,
                actual_blocks=1,
                created_at=datetime(2026, 2, 20),
            )

        result = generate_weekly_review(session, today=today)

        assert len(result["scoreboard"]) == 1
        sb = result["scoreboard"][0]
        assert sb["name"] == "Test Campaign"
        assert sb["blocks_completed"] == 3
        assert sb["weekly_target"] == 5
        assert sb["completion_pct"] == 60  # 3/5 = 60%

    def test_multiple_campaigns(self, session: Session):
        """Multiple campaigns appear in scoreboard ordered by priority_rank."""
        today = date(2026, 2, 22)
        c1 = _make_campaign(session, name="Alpha", priority_rank=1, weekly_block_target=4)
        c2 = _make_campaign(session, name="Beta", priority_rank=2, weekly_block_target=3)

        result = generate_weekly_review(session, today=today)

        assert len(result["scoreboard"]) == 2
        assert result["scoreboard"][0]["name"] == "Alpha"
        assert result["scoreboard"][1]["name"] == "Beta"

    def test_old_aars_excluded(self, session: Session):
        """AARs older than 7 days are not counted in scoreboard."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, weekly_block_target=5)
        mission = _make_mission(session, campaign)

        # AAR from 10 days ago (before cutoff)
        old_sortie = _make_sortie(
            session, mission, title="Old",
            status=SortieStatus.completed, sort_order=1,
            completed_at=datetime(2026, 2, 10),
        )
        _make_aar(session, old_sortie, actual_blocks=2, created_at=datetime(2026, 2, 10))

        # AAR from 3 days ago (within window)
        new_sortie = _make_sortie(
            session, mission, title="New",
            status=SortieStatus.completed, sort_order=2,
            completed_at=datetime(2026, 2, 19),
        )
        _make_aar(session, new_sortie, actual_blocks=1, created_at=datetime(2026, 2, 19))

        result = generate_weekly_review(session, today=today)

        assert result["scoreboard"][0]["blocks_completed"] == 1

    def test_zero_target_campaign(self, session: Session):
        """Campaign with weekly_block_target=0 shows 0% completion."""
        today = date(2026, 2, 22)
        _make_campaign(session, weekly_block_target=0)

        result = generate_weekly_review(session, today=today)

        assert result["scoreboard"][0]["completion_pct"] == 0

    def test_paused_campaigns_excluded(self, session: Session):
        """Paused campaigns do not appear in scoreboard."""
        today = date(2026, 2, 22)
        _make_campaign(session, name="Active", status=CampaignStatus.active)
        _make_campaign(
            session, name="Paused",
            status=CampaignStatus.paused, priority_rank=2,
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["scoreboard"]) == 1
        assert result["scoreboard"][0]["name"] == "Active"


class TestMissionsMoved:
    """Test missions moved section."""

    def test_completed_mission_appears(self, session: Session):
        """Mission completed this week appears in missions_moved."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session)
        _make_mission(
            session, campaign,
            name="Done Mission",
            status=MissionStatus.completed,
            completed_at=datetime(2026, 2, 20),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["missions_moved"]) == 1
        mm = result["missions_moved"][0]
        assert mm["name"] == "Done Mission"
        assert mm["new_status"] == "completed"

    def test_started_mission_appears(self, session: Session):
        """Mission started this week appears in missions_moved."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session)
        _make_mission(
            session, campaign,
            name="New Mission",
            status=MissionStatus.in_progress,
            created_at=datetime(2026, 2, 20),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["missions_moved"]) == 1
        mm = result["missions_moved"][0]
        assert mm["name"] == "New Mission"
        assert mm["new_status"] == "in_progress"
        assert mm["old_status"] == "not_started"

    def test_old_mission_not_included(self, session: Session):
        """Mission completed before the week is not included."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session)
        _make_mission(
            session, campaign,
            name="Old Mission",
            status=MissionStatus.completed,
            completed_at=datetime(2026, 2, 10),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["missions_moved"]) == 0


class TestStalenessAlerts:
    """Test staleness alerts — campaigns untouched for >5 days."""

    def test_stale_campaign_triggers_alert(self, session: Session):
        """Campaign with no completed sorties triggers staleness alert."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, name="Stale Campaign")
        # No sorties -> staleness = 999 (sentinel) which is >5

        result = generate_weekly_review(session, today=today)

        assert len(result["staleness_alerts"]) == 1
        assert result["staleness_alerts"][0]["name"] == "Stale Campaign"
        assert result["staleness_alerts"][0]["days"] == 999

    def test_active_campaign_no_alert(self, session: Session):
        """Campaign with recent completed sortie does not trigger alert."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(
            session, mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow(),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["staleness_alerts"]) == 0

    def test_borderline_5_days_no_alert(self, session: Session):
        """Campaign with sortie completed exactly 5 days ago: no alert."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session)
        mission = _make_mission(session, campaign)
        _make_sortie(
            session, mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow() - timedelta(days=5),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["staleness_alerts"]) == 0

    def test_6_days_triggers_alert(self, session: Session):
        """Campaign with sortie completed 6 days ago triggers alert."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, name="Slightly Stale")
        mission = _make_mission(session, campaign)
        _make_sortie(
            session, mission,
            status=SortieStatus.completed,
            completed_at=datetime.utcnow() - timedelta(days=6),
        )

        result = generate_weekly_review(session, today=today)

        assert len(result["staleness_alerts"]) == 1
        assert result["staleness_alerts"][0]["name"] == "Slightly Stale"


class TestEnergyPatterns:
    """Test energy patterns from DailyCheckIn records."""

    def test_all_green_energy(self, session: Session):
        """All green check-ins -> average = 3.0, label = green."""
        today = date(2026, 2, 22)
        for i in range(5):
            _make_checkin(
                session,
                checkin_date=today - timedelta(days=i),
                energy_level=EnergyLevel.green,
            )

        result = generate_weekly_review(session, today=today)

        ep = result["energy_patterns"]
        assert ep["checkins"] == 5
        assert ep["average"] == 3.0
        assert ep["average_label"] == "green"

    def test_all_red_energy(self, session: Session):
        """All red check-ins -> average = 1.0, label = red."""
        today = date(2026, 2, 22)
        for i in range(3):
            _make_checkin(
                session,
                checkin_date=today - timedelta(days=i),
                energy_level=EnergyLevel.red,
            )

        result = generate_weekly_review(session, today=today)

        ep = result["energy_patterns"]
        assert ep["checkins"] == 3
        assert ep["average"] == 1.0
        assert ep["average_label"] == "red"

    def test_mixed_energy(self, session: Session):
        """Mixed check-ins average correctly."""
        today = date(2026, 2, 22)
        _make_checkin(session, checkin_date=today, energy_level=EnergyLevel.green)
        _make_checkin(session, checkin_date=today - timedelta(days=1), energy_level=EnergyLevel.red)

        result = generate_weekly_review(session, today=today)

        ep = result["energy_patterns"]
        assert ep["checkins"] == 2
        assert ep["average"] == 2.0  # (3+1)/2
        assert ep["average_label"] == "yellow"

    def test_no_checkins(self, session: Session):
        """No check-ins -> checkins=0, average_label=none."""
        today = date(2026, 2, 22)

        result = generate_weekly_review(session, today=today)

        ep = result["energy_patterns"]
        assert ep["checkins"] == 0
        assert ep["average_label"] == "none"

    def test_old_checkins_excluded(self, session: Session):
        """Check-ins older than 7 days are excluded."""
        today = date(2026, 2, 22)
        # Check-in from 10 days ago
        _make_checkin(
            session,
            checkin_date=today - timedelta(days=10),
            energy_level=EnergyLevel.green,
        )
        # Check-in from 3 days ago
        _make_checkin(
            session,
            checkin_date=today - timedelta(days=3),
            energy_level=EnergyLevel.red,
        )

        result = generate_weekly_review(session, today=today)

        ep = result["energy_patterns"]
        assert ep["checkins"] == 1
        assert ep["average_label"] == "red"


class TestCurrentRankings:
    """Test current rankings match campaign priority_ranks."""

    def test_rankings_ordered(self, session: Session):
        """Current rankings match campaign priority order."""
        today = date(2026, 2, 22)
        _make_campaign(session, name="Second", priority_rank=2, weekly_block_target=3)
        _make_campaign(session, name="First", priority_rank=1, weekly_block_target=5)

        result = generate_weekly_review(session, today=today)

        assert len(result["current_rankings"]) == 2
        assert result["current_rankings"][0]["name"] == "First"
        assert result["current_rankings"][0]["rank"] == 1
        assert result["current_rankings"][1]["name"] == "Second"
        assert result["current_rankings"][1]["rank"] == 2


class TestNextWeekPreview:
    """Test next week preview section."""

    def test_upcoming_campaign_target(self, session: Session):
        """Campaign with target_date in next week appears in preview."""
        today = date(2026, 2, 22)
        _make_campaign(
            session, name="Deadline Campaign",
            target_date=date(2026, 2, 25),  # 3 days from today
        )

        result = generate_weekly_review(session, today=today)

        targets = result["next_week_preview"]["upcoming_targets"]
        assert len(targets) == 1
        assert targets[0]["name"] == "Deadline Campaign"
        assert targets[0]["target_date"] == "2026-02-25"

    def test_upcoming_mission_target(self, session: Session):
        """Mission with target_date in next week appears in preview."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, name="Parent")
        _make_mission(
            session, campaign,
            name="Due Mission",
            target_date=date(2026, 2, 26),
        )

        result = generate_weekly_review(session, today=today)

        targets = result["next_week_preview"]["upcoming_targets"]
        assert len(targets) == 1
        assert "Due Mission" in targets[0]["name"]

    def test_blocked_sorties_included(self, session: Session):
        """Sorties under blocked missions appear in next week preview."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, name="Blocked Camp")
        mission = _make_mission(
            session, campaign,
            name="Blocked Mission",
            status=MissionStatus.blocked,
        )
        _make_sortie(session, mission, title="Waiting Sortie")

        result = generate_weekly_review(session, today=today)

        blocked = result["next_week_preview"]["blocked_sorties"]
        assert len(blocked) == 1
        assert blocked[0]["title"] == "Waiting Sortie"
        assert blocked[0]["campaign_name"] == "Blocked Camp"

    def test_no_blocked_or_upcoming(self, session: Session):
        """No upcoming targets or blocked sorties -> both empty."""
        today = date(2026, 2, 22)
        _make_campaign(session)

        result = generate_weekly_review(session, today=today)

        assert result["next_week_preview"]["upcoming_targets"] == []
        assert result["next_week_preview"]["blocked_sorties"] == []


class TestDriftSummary:
    """Test drift summary section."""

    def test_drift_with_blocks(self, session: Session):
        """Campaigns with blocks show drift from expected share."""
        today = date(2026, 2, 22)
        c1 = _make_campaign(session, name="Alpha", priority_rank=1, weekly_block_target=5)
        c2 = _make_campaign(session, name="Beta", priority_rank=2, weekly_block_target=5)

        # All blocks go to Alpha (5 blocks to Alpha, 0 to Beta)
        m1 = _make_mission(session, c1)
        for i in range(5):
            s = _make_sortie(
                session, m1, title=f"S{i}", sort_order=i,
                status=SortieStatus.completed,
                completed_at=datetime(2026, 2, 20),
            )
            _make_aar(session, s, actual_blocks=1, created_at=datetime(2026, 2, 20))

        result = generate_weekly_review(session, today=today)

        drift = result["drift_summary"]
        assert len(drift) == 2
        # Alpha should be over-allocated (all work going there)
        alpha_drift = next(d for d in drift if d["name"] == "Alpha")
        assert alpha_drift["actual_share"] == 1.0
        assert alpha_drift["is_misaligned"] is True
        # Beta should be under-allocated
        beta_drift = next(d for d in drift if d["name"] == "Beta")
        assert beta_drift["actual_share"] == 0.0
        assert beta_drift["is_misaligned"] is True

    def test_drift_no_blocks(self, session: Session):
        """No blocks completed -> actual_share is 0 for all."""
        today = date(2026, 2, 22)
        _make_campaign(session, name="Alpha", priority_rank=1, weekly_block_target=5)

        result = generate_weekly_review(session, today=today)

        drift = result["drift_summary"]
        assert len(drift) == 1
        assert drift[0]["actual_share"] == 0.0


class TestMarkdownGeneration:
    """Test markdown output includes all required sections."""

    def test_markdown_all_section_headers(self, session: Session):
        """Markdown output contains all 7 section headers."""
        today = date(2026, 2, 22)
        _make_campaign(session)

        md = generate_weekly_review_markdown(session, today=today)

        assert "# \u632f\u308a\u8fd4\u308a Weekly Review" in md
        assert "## Scoreboard" in md
        assert "## Missions Moved" in md
        assert "## Drift Summary" in md
        assert "## Staleness Alerts" in md
        assert "## Energy Patterns" in md
        assert "## Re-rank Your Campaigns" in md
        assert "## Next Week Preview" in md

    def test_markdown_scoreboard_bar(self, session: Session):
        """Scoreboard shows progress bar in markdown."""
        today = date(2026, 2, 22)
        campaign = _make_campaign(session, weekly_block_target=5)
        mission = _make_mission(session, campaign)
        sortie = _make_sortie(
            session, mission,
            status=SortieStatus.completed,
            completed_at=datetime(2026, 2, 20),
        )
        _make_aar(session, sortie, actual_blocks=2, created_at=datetime(2026, 2, 20))

        md = generate_weekly_review_markdown(session, today=today)

        # Should have block characters in the output
        assert "2/5 blocks" in md
        assert "40%" in md

    def test_markdown_empty_state(self, session: Session):
        """Markdown renders correctly with no data."""
        today = date(2026, 2, 22)

        md = generate_weekly_review_markdown(session, today=today)

        assert "No active campaigns" in md
        assert "No mission status changes this week" in md
        assert "All campaigns active this week" in md
        assert "No check-ins recorded this week" in md

    def test_markdown_energy_with_checkins(self, session: Session):
        """Markdown includes energy data when check-ins exist."""
        today = date(2026, 2, 22)
        _make_checkin(session, checkin_date=today, energy_level=EnergyLevel.green)
        _make_checkin(
            session,
            checkin_date=today - timedelta(days=1),
            energy_level=EnergyLevel.yellow,
        )

        md = generate_weekly_review_markdown(session, today=today)

        assert "Average energy:" in md

    def test_markdown_staleness_alert(self, session: Session):
        """Markdown includes staleness warnings."""
        today = date(2026, 2, 22)
        _make_campaign(session, name="Neglected")

        md = generate_weekly_review_markdown(session, today=today)

        assert "**Neglected**" in md
        assert "untouched for" in md

    def test_markdown_re_rank_section(self, session: Session):
        """Markdown includes re-rank prompt with campaign list."""
        today = date(2026, 2, 22)
        _make_campaign(session, name="First Project", priority_rank=1)
        _make_campaign(session, name="Second Project", priority_rank=2, weekly_block_target=3)

        md = generate_weekly_review_markdown(session, today=today)

        assert "Current priority order:" in md
        assert "1. First Project" in md
        assert "2. Second Project" in md
