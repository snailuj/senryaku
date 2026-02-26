"""Tests for Senryaku SQLModel data models and enums."""

from datetime import date, datetime
from uuid import UUID, uuid4

import pytest

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


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestCampaignStatus:
    def test_members(self):
        assert set(CampaignStatus) == {
            CampaignStatus.active,
            CampaignStatus.paused,
            CampaignStatus.completed,
            CampaignStatus.archived,
        }

    def test_values(self):
        assert CampaignStatus.active.value == "active"
        assert CampaignStatus.paused.value == "paused"
        assert CampaignStatus.completed.value == "completed"
        assert CampaignStatus.archived.value == "archived"

    def test_is_str(self):
        assert isinstance(CampaignStatus.active, str)


class TestMissionStatus:
    def test_members(self):
        assert set(MissionStatus) == {
            MissionStatus.not_started,
            MissionStatus.in_progress,
            MissionStatus.blocked,
            MissionStatus.completed,
        }

    def test_values(self):
        assert MissionStatus.not_started.value == "not_started"
        assert MissionStatus.in_progress.value == "in_progress"
        assert MissionStatus.blocked.value == "blocked"
        assert MissionStatus.completed.value == "completed"

    def test_is_str(self):
        assert isinstance(MissionStatus.not_started, str)


class TestSortieStatus:
    def test_members(self):
        assert set(SortieStatus) == {
            SortieStatus.queued,
            SortieStatus.active,
            SortieStatus.completed,
            SortieStatus.abandoned,
        }

    def test_values(self):
        assert SortieStatus.queued.value == "queued"
        assert SortieStatus.active.value == "active"
        assert SortieStatus.completed.value == "completed"
        assert SortieStatus.abandoned.value == "abandoned"

    def test_is_str(self):
        assert isinstance(SortieStatus.queued, str)


class TestCognitiveLoad:
    def test_members(self):
        assert set(CognitiveLoad) == {
            CognitiveLoad.deep,
            CognitiveLoad.medium,
            CognitiveLoad.light,
        }

    def test_values(self):
        assert CognitiveLoad.deep.value == "deep"
        assert CognitiveLoad.medium.value == "medium"
        assert CognitiveLoad.light.value == "light"

    def test_is_str(self):
        assert isinstance(CognitiveLoad.deep, str)


class TestEnergyLevel:
    def test_members(self):
        assert set(EnergyLevel) == {
            EnergyLevel.green,
            EnergyLevel.yellow,
            EnergyLevel.red,
        }

    def test_values(self):
        assert EnergyLevel.green.value == "green"
        assert EnergyLevel.yellow.value == "yellow"
        assert EnergyLevel.red.value == "red"

    def test_is_str(self):
        assert isinstance(EnergyLevel.green, str)


class TestAAROutcome:
    def test_members(self):
        assert set(AAROutcome) == {
            AAROutcome.completed,
            AAROutcome.partial,
            AAROutcome.blocked,
            AAROutcome.pivoted,
        }

    def test_values(self):
        assert AAROutcome.completed.value == "completed"
        assert AAROutcome.partial.value == "partial"
        assert AAROutcome.blocked.value == "blocked"
        assert AAROutcome.pivoted.value == "pivoted"

    def test_is_str(self):
        assert isinstance(AAROutcome.completed, str)


# ---------------------------------------------------------------------------
# Campaign model tests
# ---------------------------------------------------------------------------


class TestCampaign:
    def test_instantiation_required_fields(self):
        campaign = Campaign(
            name="Metaforge",
            description="Build the forge",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=5,
            colour="#FF5733",
            tags="ai,strategy",
        )
        assert campaign.name == "Metaforge"
        assert campaign.description == "Build the forge"
        assert campaign.status == CampaignStatus.active
        assert campaign.priority_rank == 1
        assert campaign.weekly_block_target == 5
        assert campaign.colour == "#FF5733"
        assert campaign.tags == "ai,strategy"

    def test_uuid_auto_generated(self):
        campaign = Campaign(
            name="Test",
            description="Test desc",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=3,
            colour="#000000",
            tags="",
        )
        assert isinstance(campaign.id, UUID)

    def test_created_at_auto_set(self):
        before = datetime.utcnow()
        campaign = Campaign(
            name="Test",
            description="Test desc",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=3,
            colour="#000000",
            tags="",
        )
        after = datetime.utcnow()
        assert isinstance(campaign.created_at, datetime)
        assert before <= campaign.created_at <= after

    def test_updated_at_auto_set(self):
        campaign = Campaign(
            name="Test",
            description="Test desc",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=3,
            colour="#000000",
            tags="",
        )
        assert isinstance(campaign.updated_at, datetime)

    def test_optional_target_date_defaults_none(self):
        campaign = Campaign(
            name="Test",
            description="Test desc",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=3,
            colour="#000000",
            tags="",
        )
        assert campaign.target_date is None

    def test_optional_target_date_accepts_date(self):
        d = date(2026, 6, 15)
        campaign = Campaign(
            name="Test",
            description="Test desc",
            status=CampaignStatus.active,
            priority_rank=1,
            weekly_block_target=3,
            colour="#000000",
            tags="",
            target_date=d,
        )
        assert campaign.target_date == d

    def test_table_name(self):
        assert Campaign.__tablename__ == "campaign"

    def test_two_campaigns_have_different_ids(self):
        c1 = Campaign(
            name="A", description="A", status=CampaignStatus.active,
            priority_rank=1, weekly_block_target=1, colour="#000", tags="",
        )
        c2 = Campaign(
            name="B", description="B", status=CampaignStatus.active,
            priority_rank=2, weekly_block_target=1, colour="#000", tags="",
        )
        assert c1.id != c2.id


# ---------------------------------------------------------------------------
# Mission model tests
# ---------------------------------------------------------------------------


class TestMission:
    def test_instantiation_required_fields(self):
        cid = uuid4()
        mission = Mission(
            campaign_id=cid,
            name="Design core loop",
            description="Prototype the core feedback loop",
            status=MissionStatus.not_started,
            sort_order=1,
        )
        assert mission.campaign_id == cid
        assert mission.name == "Design core loop"
        assert mission.description == "Prototype the core feedback loop"
        assert mission.status == MissionStatus.not_started
        assert mission.sort_order == 1

    def test_uuid_auto_generated(self):
        mission = Mission(
            campaign_id=uuid4(),
            name="Test",
            description="Desc",
            status=MissionStatus.not_started,
            sort_order=0,
        )
        assert isinstance(mission.id, UUID)

    def test_created_at_auto_set(self):
        mission = Mission(
            campaign_id=uuid4(),
            name="Test",
            description="Desc",
            status=MissionStatus.not_started,
            sort_order=0,
        )
        assert isinstance(mission.created_at, datetime)

    def test_optional_fields_default_none(self):
        mission = Mission(
            campaign_id=uuid4(),
            name="Test",
            description="Desc",
            status=MissionStatus.not_started,
            sort_order=0,
        )
        assert mission.target_date is None
        assert mission.completed_at is None

    def test_foreign_key_accepts_uuid(self):
        cid = uuid4()
        mission = Mission(
            campaign_id=cid,
            name="Test",
            description="Desc",
            status=MissionStatus.not_started,
            sort_order=0,
        )
        assert mission.campaign_id == cid
        assert isinstance(mission.campaign_id, UUID)

    def test_table_name(self):
        assert Mission.__tablename__ == "mission"


# ---------------------------------------------------------------------------
# Sortie model tests
# ---------------------------------------------------------------------------


class TestSortie:
    def test_instantiation_required_fields(self):
        mid = uuid4()
        sortie = Sortie(
            mission_id=mid,
            title="Write intro section",
            cognitive_load=CognitiveLoad.deep,
            estimated_blocks=1,
            status=SortieStatus.queued,
            sort_order=1,
        )
        assert sortie.mission_id == mid
        assert sortie.title == "Write intro section"
        assert sortie.cognitive_load == CognitiveLoad.deep
        assert sortie.estimated_blocks == 1
        assert sortie.status == SortieStatus.queued
        assert sortie.sort_order == 1

    def test_uuid_auto_generated(self):
        sortie = Sortie(
            mission_id=uuid4(),
            title="Test",
            cognitive_load=CognitiveLoad.light,
            estimated_blocks=1,
            status=SortieStatus.queued,
            sort_order=0,
        )
        assert isinstance(sortie.id, UUID)

    def test_created_at_auto_set(self):
        sortie = Sortie(
            mission_id=uuid4(),
            title="Test",
            cognitive_load=CognitiveLoad.light,
            estimated_blocks=1,
            status=SortieStatus.queued,
            sort_order=0,
        )
        assert isinstance(sortie.created_at, datetime)

    def test_optional_fields_default_none(self):
        sortie = Sortie(
            mission_id=uuid4(),
            title="Test",
            cognitive_load=CognitiveLoad.light,
            estimated_blocks=1,
            status=SortieStatus.queued,
            sort_order=0,
        )
        assert sortie.description is None
        assert sortie.started_at is None
        assert sortie.completed_at is None

    def test_foreign_key_accepts_uuid(self):
        mid = uuid4()
        sortie = Sortie(
            mission_id=mid,
            title="Test",
            cognitive_load=CognitiveLoad.light,
            estimated_blocks=1,
            status=SortieStatus.queued,
            sort_order=0,
        )
        assert sortie.mission_id == mid
        assert isinstance(sortie.mission_id, UUID)

    def test_table_name(self):
        assert Sortie.__tablename__ == "sortie"


# ---------------------------------------------------------------------------
# AAR model tests
# ---------------------------------------------------------------------------


class TestAAR:
    def test_instantiation_required_fields(self):
        sid = uuid4()
        aar = AAR(
            sortie_id=sid,
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.yellow,
            outcome=AAROutcome.completed,
            actual_blocks=1,
        )
        assert aar.sortie_id == sid
        assert aar.energy_before == EnergyLevel.green
        assert aar.energy_after == EnergyLevel.yellow
        assert aar.outcome == AAROutcome.completed
        assert aar.actual_blocks == 1

    def test_uuid_auto_generated(self):
        aar = AAR(
            sortie_id=uuid4(),
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green,
            outcome=AAROutcome.completed,
            actual_blocks=1,
        )
        assert isinstance(aar.id, UUID)

    def test_created_at_auto_set(self):
        aar = AAR(
            sortie_id=uuid4(),
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green,
            outcome=AAROutcome.completed,
            actual_blocks=1,
        )
        assert isinstance(aar.created_at, datetime)

    def test_optional_notes_defaults_none(self):
        aar = AAR(
            sortie_id=uuid4(),
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green,
            outcome=AAROutcome.completed,
            actual_blocks=1,
        )
        assert aar.notes is None

    def test_notes_accepts_text(self):
        aar = AAR(
            sortie_id=uuid4(),
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green,
            outcome=AAROutcome.completed,
            actual_blocks=1,
            notes="Good focus session, completed ahead of time.",
        )
        assert aar.notes == "Good focus session, completed ahead of time."

    def test_foreign_key_accepts_uuid(self):
        sid = uuid4()
        aar = AAR(
            sortie_id=sid,
            energy_before=EnergyLevel.green,
            energy_after=EnergyLevel.green,
            outcome=AAROutcome.completed,
            actual_blocks=1,
        )
        assert aar.sortie_id == sid
        assert isinstance(aar.sortie_id, UUID)

    def test_table_name(self):
        assert AAR.__tablename__ == "aar"


# ---------------------------------------------------------------------------
# DailyCheckIn model tests
# ---------------------------------------------------------------------------


class TestDailyCheckIn:
    def test_instantiation_required_fields(self):
        d = date(2026, 2, 26)
        checkin = DailyCheckIn(
            date=d,
            energy_level=EnergyLevel.green,
            available_blocks=4,
        )
        assert checkin.date == d
        assert checkin.energy_level == EnergyLevel.green
        assert checkin.available_blocks == 4

    def test_uuid_auto_generated(self):
        checkin = DailyCheckIn(
            date=date.today(),
            energy_level=EnergyLevel.yellow,
            available_blocks=2,
        )
        assert isinstance(checkin.id, UUID)

    def test_created_at_auto_set(self):
        checkin = DailyCheckIn(
            date=date.today(),
            energy_level=EnergyLevel.yellow,
            available_blocks=2,
        )
        assert isinstance(checkin.created_at, datetime)

    def test_optional_focus_note_defaults_none(self):
        checkin = DailyCheckIn(
            date=date.today(),
            energy_level=EnergyLevel.red,
            available_blocks=1,
        )
        assert checkin.focus_note is None

    def test_focus_note_accepts_text(self):
        checkin = DailyCheckIn(
            date=date.today(),
            energy_level=EnergyLevel.green,
            available_blocks=5,
            focus_note="Ship the MVP today",
        )
        assert checkin.focus_note == "Ship the MVP today"

    def test_table_name(self):
        assert DailyCheckIn.__tablename__ == "dailycheckin"
