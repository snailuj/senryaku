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
