"""Tests for the Campaign CRUD API endpoints."""

import pytest


API_KEY_HEADER = {"X-API-Key": "test-key"}


def create_campaign(client, **overrides):
    """Helper to create a campaign via the API."""
    data = {
        "name": "Test Campaign",
        "description": "Test description",
        "priority_rank": 1,
        "weekly_block_target": 5,
        "colour": "#6366f1",
        "tags": "test",
    }
    data.update(overrides)
    return client.post("/api/v1/campaigns", json=data, headers=API_KEY_HEADER)


class TestCreateCampaign:
    def test_create_campaign_returns_201(self, client):
        response = create_campaign(client)
        assert response.status_code == 201

    def test_create_campaign_returns_correct_data(self, client):
        response = create_campaign(client, name="Metaforge", description="Build the forge")
        data = response.json()
        assert data["name"] == "Metaforge"
        assert data["description"] == "Build the forge"
        assert data["priority_rank"] == 1
        assert data["weekly_block_target"] == 5
        assert data["colour"] == "#6366f1"
        assert data["tags"] == "test"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_campaign_with_target_date(self, client):
        response = create_campaign(client, target_date="2026-06-15")
        data = response.json()
        assert data["target_date"] == "2026-06-15"

    def test_create_campaign_default_target_date_is_null(self, client):
        response = create_campaign(client)
        data = response.json()
        assert data["target_date"] is None


class TestListCampaigns:
    def test_list_campaigns_empty(self, client):
        response = client.get("/api/v1/campaigns", headers=API_KEY_HEADER)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_campaigns_returns_all(self, client):
        create_campaign(client, name="Campaign A", priority_rank=1)
        create_campaign(client, name="Campaign B", priority_rank=2)
        response = client.get("/api/v1/campaigns", headers=API_KEY_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"Campaign A", "Campaign B"}

    def test_list_campaigns_filter_by_status(self, client):
        resp_a = create_campaign(client, name="Active Campaign", priority_rank=1)
        resp_b = create_campaign(client, name="To Archive", priority_rank=2)
        # Soft-delete the second campaign (sets status to archived)
        campaign_b_id = resp_b.json()["id"]
        client.delete(f"/api/v1/campaigns/{campaign_b_id}", headers=API_KEY_HEADER)

        # Filter for active only
        response = client.get(
            "/api/v1/campaigns", params={"status": "active"}, headers=API_KEY_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Active Campaign"

    def test_list_campaigns_filter_by_archived(self, client):
        create_campaign(client, name="Active Campaign", priority_rank=1)
        resp_b = create_campaign(client, name="Archived Campaign", priority_rank=2)
        campaign_b_id = resp_b.json()["id"]
        client.delete(f"/api/v1/campaigns/{campaign_b_id}", headers=API_KEY_HEADER)

        response = client.get(
            "/api/v1/campaigns", params={"status": "archived"}, headers=API_KEY_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Archived Campaign"


class TestGetCampaign:
    def test_get_campaign_by_id(self, client):
        resp = create_campaign(client, name="Detail Campaign")
        campaign_id = resp.json()["id"]

        response = client.get(
            f"/api/v1/campaigns/{campaign_id}", headers=API_KEY_HEADER
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail Campaign"
        assert data["id"] == campaign_id

    def test_get_campaign_nonexistent_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(
            f"/api/v1/campaigns/{fake_id}", headers=API_KEY_HEADER
        )
        assert response.status_code == 404

    def test_get_campaign_includes_missions(self, client):
        resp = create_campaign(client, name="With Missions")
        campaign_id = resp.json()["id"]

        response = client.get(
            f"/api/v1/campaigns/{campaign_id}", headers=API_KEY_HEADER
        )
        data = response.json()
        # Should have a missions key (empty list since none created)
        assert "missions" in data
        assert data["missions"] == []


class TestUpdateCampaign:
    def test_update_campaign_changes_specified_fields(self, client):
        resp = create_campaign(client, name="Original Name")
        campaign_id = resp.json()["id"]

        response = client.put(
            f"/api/v1/campaigns/{campaign_id}",
            json={"name": "Updated Name"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        # Other fields should remain unchanged
        assert data["description"] == "Test description"
        assert data["priority_rank"] == 1

    def test_update_campaign_multiple_fields(self, client):
        resp = create_campaign(client)
        campaign_id = resp.json()["id"]

        response = client.put(
            f"/api/v1/campaigns/{campaign_id}",
            json={"name": "New Name", "description": "New desc", "colour": "#ff0000"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New desc"
        assert data["colour"] == "#ff0000"

    def test_update_campaign_status(self, client):
        resp = create_campaign(client)
        campaign_id = resp.json()["id"]

        response = client.put(
            f"/api/v1/campaigns/{campaign_id}",
            json={"status": "paused"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    def test_update_nonexistent_campaign_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(
            f"/api/v1/campaigns/{fake_id}",
            json={"name": "Nope"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 404


class TestDeleteCampaign:
    def test_delete_campaign_soft_deletes(self, client):
        resp = create_campaign(client, name="To Delete")
        campaign_id = resp.json()["id"]

        response = client.delete(
            f"/api/v1/campaigns/{campaign_id}", headers=API_KEY_HEADER
        )
        assert response.status_code == 200

        # Verify it's archived, not gone
        get_resp = client.get(
            f"/api/v1/campaigns/{campaign_id}", headers=API_KEY_HEADER
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "archived"

    def test_delete_nonexistent_campaign_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.delete(
            f"/api/v1/campaigns/{fake_id}", headers=API_KEY_HEADER
        )
        assert response.status_code == 404


class TestRerankCampaigns:
    def test_rerank_updates_priority_ranks(self, client):
        resp_a = create_campaign(client, name="Campaign A", priority_rank=1)
        resp_b = create_campaign(client, name="Campaign B", priority_rank=2)
        id_a = resp_a.json()["id"]
        id_b = resp_b.json()["id"]

        # Swap their ranks
        response = client.put(
            "/api/v1/campaigns/rerank",
            json={"ranks": [{"id": id_a, "rank": 2}, {"id": id_b, "rank": 1}]},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200

        # Verify the ranks changed
        get_a = client.get(f"/api/v1/campaigns/{id_a}", headers=API_KEY_HEADER)
        get_b = client.get(f"/api/v1/campaigns/{id_b}", headers=API_KEY_HEADER)
        assert get_a.json()["priority_rank"] == 2
        assert get_b.json()["priority_rank"] == 1

    def test_rerank_returns_updated_list(self, client):
        resp_a = create_campaign(client, name="Campaign A", priority_rank=1)
        resp_b = create_campaign(client, name="Campaign B", priority_rank=2)
        id_a = resp_a.json()["id"]
        id_b = resp_b.json()["id"]

        response = client.put(
            "/api/v1/campaigns/rerank",
            json={"ranks": [{"id": id_a, "rank": 2}, {"id": id_b, "rank": 1}]},
            headers=API_KEY_HEADER,
        )
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Mission helpers & tests
# ---------------------------------------------------------------------------


def create_mission(client, campaign_id, **overrides):
    """Helper to create a mission via the API."""
    data = {
        "campaign_id": str(campaign_id),
        "name": "Test Mission",
        "description": "Test description",
        "sort_order": 0,
    }
    data.update(overrides)
    return client.post("/api/v1/missions", json=data, headers=API_KEY_HEADER)


class TestCreateMission:
    def test_create_mission_returns_201(self, client):
        camp = create_campaign(client).json()
        response = create_mission(client, camp["id"])
        assert response.status_code == 201

    def test_create_mission_returns_correct_data(self, client):
        camp = create_campaign(client).json()
        response = create_mission(
            client,
            camp["id"],
            name="Recon Alpha",
            description="Scout the perimeter",
        )
        data = response.json()
        assert data["name"] == "Recon Alpha"
        assert data["description"] == "Scout the perimeter"
        assert data["campaign_id"] == camp["id"]
        assert data["status"] == "not_started"
        assert "id" in data
        assert "created_at" in data

    def test_create_mission_with_nonexistent_campaign_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = create_mission(client, fake_id)
        assert response.status_code == 404


class TestListMissions:
    def test_list_missions_for_campaign(self, client):
        camp = create_campaign(client).json()
        create_mission(client, camp["id"], name="Mission A", sort_order=1)
        create_mission(client, camp["id"], name="Mission B", sort_order=0)

        response = client.get(
            f"/api/v1/campaigns/{camp['id']}/missions",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered by sort_order
        assert data[0]["name"] == "Mission B"
        assert data[1]["name"] == "Mission A"

    def test_list_missions_empty_for_campaign_with_no_missions(self, client):
        camp = create_campaign(client).json()
        response = client.get(
            f"/api/v1/campaigns/{camp['id']}/missions",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        assert response.json() == []


class TestUpdateMission:
    def test_update_mission_name_and_description(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()

        response = client.put(
            f"/api/v1/missions/{mission['id']}",
            json={"name": "Updated Name", "description": "Updated desc"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated desc"

    def test_update_mission_status_to_completed_sets_completed_at(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        assert mission["completed_at"] is None

        response = client.put(
            f"/api/v1/missions/{mission['id']}",
            json={"status": "completed"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None


class TestDeleteMission:
    def test_delete_mission_soft_deletes(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()

        response = client.delete(
            f"/api/v1/missions/{mission['id']}",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None


class TestAPIKeyAuth:
    def test_request_without_api_key_returns_401(self, client):
        response = client.get("/api/v1/campaigns")
        assert response.status_code == 401

    def test_request_with_wrong_api_key_returns_401(self, client):
        response = client.get(
            "/api/v1/campaigns", headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401

    def test_request_with_correct_api_key_succeeds(self, client):
        response = client.get("/api/v1/campaigns", headers=API_KEY_HEADER)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Sortie helpers & tests
# ---------------------------------------------------------------------------


def create_sortie(client, mission_id, **overrides):
    """Helper to create a sortie via the API."""
    data = {
        "mission_id": str(mission_id),
        "title": "Test Sortie",
        "cognitive_load": "medium",
        "estimated_blocks": 1,
        "sort_order": 0,
    }
    data.update(overrides)
    return client.post("/api/v1/sorties", json=data, headers=API_KEY_HEADER)


class TestCreateSortie:
    def test_create_sortie_returns_201(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        response = create_sortie(client, mission["id"])
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["title"] == "Test Sortie"
        assert data["mission_id"] == mission["id"]
        assert "id" in data
        assert "created_at" in data

    def test_create_sortie_with_nonexistent_mission_returns_404(self, client):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = create_sortie(client, fake_id)
        assert response.status_code == 404


class TestListSorties:
    def test_list_sorties_for_mission_ordered_by_sort_order(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        create_sortie(client, mission["id"], title="Sortie B", sort_order=2)
        create_sortie(client, mission["id"], title="Sortie A", sort_order=0)
        create_sortie(client, mission["id"], title="Sortie C", sort_order=1)

        response = client.get(
            f"/api/v1/missions/{mission['id']}/sorties",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["title"] == "Sortie A"
        assert data[1]["title"] == "Sortie C"
        assert data[2]["title"] == "Sortie B"

    def test_list_queued_sorties_across_campaigns(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        create_sortie(client, mission["id"], title="Queued One")
        create_sortie(client, mission["id"], title="Queued Two")

        response = client.get("/api/v1/sorties/queued", headers=API_KEY_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = {s["title"] for s in data}
        assert titles == {"Queued One", "Queued Two"}


class TestUpdateSortie:
    def test_update_sortie_title_and_description(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()

        response = client.put(
            f"/api/v1/sorties/{sortie['id']}",
            json={"title": "Updated Title", "description": "New desc"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "New desc"


class TestStartSortie:
    def test_start_sortie_sets_active_and_started_at(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()
        assert sortie["status"] == "queued"
        assert sortie["started_at"] is None

        response = client.put(
            f"/api/v1/sorties/{sortie['id']}/start",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["started_at"] is not None

    def test_start_already_active_sortie_returns_error(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()

        # Start it once
        client.put(
            f"/api/v1/sorties/{sortie['id']}/start",
            headers=API_KEY_HEADER,
        )

        # Try to start again
        response = client.put(
            f"/api/v1/sorties/{sortie['id']}/start",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 400


class TestCompleteSortie:
    def test_complete_sortie_with_aar_data(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()

        # Start the sortie first
        client.put(
            f"/api/v1/sorties/{sortie['id']}/start",
            headers=API_KEY_HEADER,
        )

        # Complete with AAR data
        aar_data = {
            "outcome": "completed",
            "energy_before": "green",
            "energy_after": "yellow",
            "actual_blocks": 2,
            "notes": "Went well",
        }
        response = client.put(
            f"/api/v1/sorties/{sortie['id']}/complete",
            json=aar_data,
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["completed_at"] is not None

    def test_complete_sortie_creates_aar_record(self, client, session):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()

        # Start, then complete
        client.put(
            f"/api/v1/sorties/{sortie['id']}/start",
            headers=API_KEY_HEADER,
        )
        aar_data = {
            "outcome": "partial",
            "energy_before": "green",
            "energy_after": "red",
            "actual_blocks": 1,
            "notes": "Hit a blocker",
        }
        client.put(
            f"/api/v1/sorties/{sortie['id']}/complete",
            json=aar_data,
            headers=API_KEY_HEADER,
        )

        # Verify AAR record was created in the database
        from senryaku.models import AAR
        from sqlmodel import select
        from uuid import UUID

        aar = session.exec(
            select(AAR).where(AAR.sortie_id == UUID(sortie["id"]))
        ).first()
        assert aar is not None
        assert aar.outcome.value == "partial"
        assert aar.energy_before.value == "green"
        assert aar.energy_after.value == "red"
        assert aar.actual_blocks == 1
        assert aar.notes == "Hit a blocker"


class TestDeleteSortie:
    def test_delete_sortie_soft_deletes_to_abandoned(self, client):
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        sortie = create_sortie(client, mission["id"]).json()

        response = client.delete(
            f"/api/v1/sorties/{sortie['id']}",
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "abandoned"


# ---------------------------------------------------------------------------
# Check-in tests
# ---------------------------------------------------------------------------


class TestDailyCheckIn:
    def test_create_checkin_returns_201(self, client):
        checkin_data = {
            "date": "2026-02-26",
            "energy_level": "green",
            "available_blocks": 4,
            "focus_note": "Feeling sharp today",
        }
        response = client.post(
            "/api/v1/checkin", json=checkin_data, headers=API_KEY_HEADER
        )
        assert response.status_code == 201
        data = response.json()
        assert data["date"] == "2026-02-26"
        assert data["energy_level"] == "green"
        assert data["available_blocks"] == 4
        assert data["focus_note"] == "Feeling sharp today"
        assert "id" in data
        assert "created_at" in data

    def test_checkin_same_date_upserts(self, client):
        checkin_data = {
            "date": "2026-02-26",
            "energy_level": "green",
            "available_blocks": 4,
        }
        resp1 = client.post(
            "/api/v1/checkin", json=checkin_data, headers=API_KEY_HEADER
        )
        assert resp1.status_code == 201
        id1 = resp1.json()["id"]

        # Second check-in for same date should upsert (update, not create new)
        checkin_data2 = {
            "date": "2026-02-26",
            "energy_level": "yellow",
            "available_blocks": 2,
        }
        resp2 = client.post(
            "/api/v1/checkin", json=checkin_data2, headers=API_KEY_HEADER
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        # Same record, updated
        assert data2["id"] == id1
        assert data2["energy_level"] == "yellow"
        assert data2["available_blocks"] == 2

    def test_checkin_different_dates_create_separate_records(self, client):
        checkin1 = {
            "date": "2026-02-25",
            "energy_level": "green",
            "available_blocks": 4,
        }
        checkin2 = {
            "date": "2026-02-26",
            "energy_level": "red",
            "available_blocks": 1,
        }
        resp1 = client.post(
            "/api/v1/checkin", json=checkin1, headers=API_KEY_HEADER
        )
        resp2 = client.post(
            "/api/v1/checkin", json=checkin2, headers=API_KEY_HEADER
        )
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        # Different IDs = separate records
        assert resp1.json()["id"] != resp2.json()["id"]


# ---------------------------------------------------------------------------
# Briefing API tests
# ---------------------------------------------------------------------------


class TestBriefingAPI:
    def test_get_briefing_today_returns_200(self, client):
        """GET /api/v1/briefing/today returns a briefing (empty sorties is OK)."""
        response = client.get("/api/v1/briefing/today", headers=API_KEY_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "energy_level" in data
        assert "available_blocks" in data
        assert "sorties" in data
        assert isinstance(data["sorties"], list)

    def test_get_briefing_today_with_energy_param(self, client):
        """GET /api/v1/briefing/today?energy=green uses provided energy."""
        response = client.get(
            "/api/v1/briefing/today",
            params={"energy": "green"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["energy_level"] == "green"

    def test_get_briefing_today_with_yellow_energy(self, client):
        """GET /api/v1/briefing/today?energy=yellow uses yellow energy."""
        response = client.get(
            "/api/v1/briefing/today",
            params={"energy": "yellow"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["energy_level"] == "yellow"

    def test_get_briefing_today_markdown_format(self, client):
        """GET /api/v1/briefing/today?format=markdown returns plain text."""
        response = client.get(
            "/api/v1/briefing/today",
            params={"format": "markdown"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "Daily Briefing" in response.text

    def test_get_briefing_today_uses_checkin_energy(self, client):
        """Briefing uses today's check-in energy when no param provided."""
        from datetime import date

        checkin_data = {
            "date": date.today().isoformat(),
            "energy_level": "red",
            "available_blocks": 2,
        }
        client.post("/api/v1/checkin", json=checkin_data, headers=API_KEY_HEADER)

        response = client.get("/api/v1/briefing/today", headers=API_KEY_HEADER)
        assert response.status_code == 200
        data = response.json()
        assert data["energy_level"] == "red"
        assert data["available_blocks"] == 2

    def test_get_briefing_today_with_sorties(self, client):
        """Briefing returns sorties when campaigns/missions/sorties exist."""
        # Create a campaign, mission, and sortie
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        create_sortie(client, mission["id"], title="Write tests", cognitive_load="light")

        response = client.get(
            "/api/v1/briefing/today",
            params={"energy": "green"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["sorties"]) >= 1
        assert data["sorties"][0]["title"] == "Write tests"


class TestBriefingRouteAPI:
    def test_route_sortie_returns_null_when_empty(self, client):
        """GET /api/v1/briefing/route?energy=green returns null when no sorties."""
        response = client.get(
            "/api/v1/briefing/route",
            params={"energy": "green"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        assert response.json() is None

    def test_route_sortie_returns_single_sortie(self, client):
        """GET /api/v1/briefing/route returns the best sortie."""
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        create_sortie(client, mission["id"], title="Top Priority", cognitive_load="medium")

        response = client.get(
            "/api/v1/briefing/route",
            params={"energy": "green"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["title"] == "Top Priority"

    def test_route_sortie_respects_energy_filter(self, client):
        """Route with red energy should only return light-load sorties."""
        camp = create_campaign(client).json()
        mission = create_mission(client, camp["id"]).json()
        # Create only a deep-load sortie
        create_sortie(client, mission["id"], title="Deep Work", cognitive_load="deep")

        response = client.get(
            "/api/v1/briefing/route",
            params={"energy": "red"},
            headers=API_KEY_HEADER,
        )
        assert response.status_code == 200
        # Red energy only allows light load, so deep sortie should not be returned
        assert response.json() is None
