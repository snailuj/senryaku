"""Tests for P1 operations endpoints: dashboard health, settings API, notifications, scheduler."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, datetime, timedelta

from senryaku.models import (
    Campaign, CampaignStatus, Mission, MissionStatus,
    Sortie, SortieStatus, CognitiveLoad, AAR, AAROutcome,
    EnergyLevel,
)

API_KEY_HEADER = {"X-API-Key": "test-key"}


def _seed_campaign(session, name="Alpha", rank=1, target=5, colour="#6366f1"):
    """Create a campaign with a mission and some sorties."""
    c = Campaign(
        name=name, description=f"{name} desc", status=CampaignStatus.active,
        priority_rank=rank, weekly_block_target=target, colour=colour, tags="test",
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _seed_full_campaign(session, name="Alpha", rank=1, target=5):
    """Campaign with mission, sorties, and a completed AAR."""
    c = _seed_campaign(session, name=name, rank=rank, target=target)
    m = Mission(campaign_id=c.id, name=f"{name} M1", description="Mission 1", status=MissionStatus.in_progress, sort_order=1)
    session.add(m)
    session.commit()
    session.refresh(m)

    s = Sortie(
        mission_id=m.id, title=f"{name} S1", cognitive_load=CognitiveLoad.medium,
        estimated_blocks=1, sort_order=1,
        status=SortieStatus.completed, completed_at=datetime.utcnow(),
    )
    session.add(s)
    session.commit()
    session.refresh(s)

    aar = AAR(
        sortie_id=s.id, energy_before=EnergyLevel.green, energy_after=EnergyLevel.yellow,
        outcome=AAROutcome.completed, actual_blocks=1,
    )
    session.add(aar)
    session.commit()
    return c


# ---------------------------------------------------------------------------
# Dashboard Health API (/api/v1/dashboard/health)
# ---------------------------------------------------------------------------

class TestDashboardHealthAPI:
    def test_returns_200(self, client, session):
        response = client.get("/api/v1/dashboard/health", headers=API_KEY_HEADER)
        assert response.status_code == 200

    def test_returns_list(self, client, session):
        response = client.get("/api/v1/dashboard/health", headers=API_KEY_HEADER)
        assert isinstance(response.json(), list)

    def test_includes_campaign_data(self, client, session):
        _seed_full_campaign(session, name="TestCamp")
        response = client.get("/api/v1/dashboard/health", headers=API_KEY_HEADER)
        data = response.json()
        assert len(data) >= 1
        camp = data[0]
        assert "name" in camp
        assert camp["name"] == "TestCamp"

    def test_requires_api_key(self, client, session):
        response = client.get("/api/v1/dashboard/health")
        assert response.status_code == 401

    def test_multiple_campaigns(self, client, session):
        _seed_full_campaign(session, name="A", rank=1)
        _seed_full_campaign(session, name="B", rank=2)
        response = client.get("/api/v1/dashboard/health", headers=API_KEY_HEADER)
        data = response.json()
        assert len(data) == 2


# ---------------------------------------------------------------------------
# Settings API (/api/v1/settings)
# ---------------------------------------------------------------------------

class TestSettingsAPI:
    def test_returns_200(self, client):
        response = client.get("/api/v1/settings", headers=API_KEY_HEADER)
        assert response.status_code == 200

    def test_returns_expected_fields(self, client):
        response = client.get("/api/v1/settings", headers=API_KEY_HEADER)
        data = response.json()
        assert "timezone" in data
        assert "webhook_url" in data
        assert "webhook_type" in data
        assert "briefing_cron" in data
        assert "review_cron" in data
        assert "base_url" in data

    def test_default_timezone(self, client):
        response = client.get("/api/v1/settings", headers=API_KEY_HEADER)
        data = response.json()
        assert data["timezone"] == "Pacific/Auckland"

    def test_requires_api_key(self, client):
        response = client.get("/api/v1/settings")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Settings Page (HTML)
# ---------------------------------------------------------------------------

class TestSettingsPage:
    def test_returns_200(self, client):
        response = client.get("/settings")
        assert response.status_code == 200

    def test_contains_settings_heading(self, client):
        response = client.get("/settings")
        assert "Settings" in response.text

    def test_shows_timezone(self, client):
        response = client.get("/settings")
        assert "Pacific/Auckland" in response.text

    def test_shows_env_var_reference(self, client):
        response = client.get("/settings")
        assert "SENRYAKU_" in response.text


# ---------------------------------------------------------------------------
# Notifications service
# ---------------------------------------------------------------------------

class TestNotificationService:
    def test_returns_false_when_no_webhook(self):
        with patch("senryaku.services.notifications.get_settings") as mock:
            mock.return_value = MagicMock(webhook_url="")
            from senryaku.services.notifications import send_notification
            assert send_notification("test message") is False

    def test_ntfy_sends_post(self):
        with patch("senryaku.services.notifications.get_settings") as mock_settings, \
             patch("senryaku.services.notifications.httpx") as mock_httpx:
            mock_settings.return_value = MagicMock(
                webhook_url="https://ntfy.sh/test", webhook_type="ntfy"
            )
            from senryaku.services.notifications import send_notification
            result = send_notification("Hello")
            assert result is True
            mock_httpx.post.assert_called_once()
            args, kwargs = mock_httpx.post.call_args
            assert args[0] == "https://ntfy.sh/test"
            assert kwargs["content"] == b"Hello"

    def test_telegram_sends_json(self):
        with patch("senryaku.services.notifications.get_settings") as mock_settings, \
             patch("senryaku.services.notifications.httpx") as mock_httpx:
            mock_settings.return_value = MagicMock(
                webhook_url="https://api.telegram.org/bot123/sendMessage",
                webhook_type="telegram",
            )
            from senryaku.services.notifications import send_notification
            result = send_notification("Hello Telegram")
            assert result is True
            mock_httpx.post.assert_called_once()
            _, kwargs = mock_httpx.post.call_args
            assert kwargs["json"]["text"] == "Hello Telegram"

    def test_generic_sends_json(self):
        with patch("senryaku.services.notifications.get_settings") as mock_settings, \
             patch("senryaku.services.notifications.httpx") as mock_httpx:
            mock_settings.return_value = MagicMock(
                webhook_url="https://hooks.example.com/webhook",
                webhook_type="generic",
            )
            from senryaku.services.notifications import send_notification
            result = send_notification("Generic msg")
            assert result is True
            _, kwargs = mock_httpx.post.call_args
            assert kwargs["json"]["source"] == "senryaku"

    def test_returns_false_on_exception(self):
        with patch("senryaku.services.notifications.get_settings") as mock_settings, \
             patch("senryaku.services.notifications.httpx") as mock_httpx:
            mock_settings.return_value = MagicMock(
                webhook_url="https://ntfy.sh/test", webhook_type="ntfy"
            )
            mock_httpx.post.side_effect = Exception("Network error")
            from senryaku.services.notifications import send_notification
            assert send_notification("fail") is False


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestScheduler:
    def test_init_scheduler_starts(self):
        with patch("senryaku.services.scheduler.get_settings") as mock_settings, \
             patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_settings.return_value = MagicMock(
                briefing_cron="0 7 * * *",
                review_cron="0 18 * * 0",
            )
            from senryaku.services.scheduler import init_scheduler
            init_scheduler()
            mock_sched.start.assert_called_once()

    def test_init_scheduler_adds_briefing_job(self):
        with patch("senryaku.services.scheduler.get_settings") as mock_settings, \
             patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_settings.return_value = MagicMock(
                briefing_cron="0 7 * * *",
                review_cron="",
            )
            from senryaku.services.scheduler import init_scheduler
            init_scheduler()
            mock_sched.add_job.assert_called_once()
            _, kwargs = mock_sched.add_job.call_args
            assert kwargs["id"] == "morning_briefing"

    def test_init_scheduler_adds_review_job(self):
        with patch("senryaku.services.scheduler.get_settings") as mock_settings, \
             patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_settings.return_value = MagicMock(
                briefing_cron="",
                review_cron="0 18 * * 0",
            )
            from senryaku.services.scheduler import init_scheduler
            init_scheduler()
            mock_sched.add_job.assert_called_once()
            _, kwargs = mock_sched.add_job.call_args
            assert kwargs["id"] == "weekly_review"

    def test_init_scheduler_skips_empty_cron(self):
        with patch("senryaku.services.scheduler.get_settings") as mock_settings, \
             patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_settings.return_value = MagicMock(
                briefing_cron="",
                review_cron="",
            )
            from senryaku.services.scheduler import init_scheduler
            init_scheduler()
            mock_sched.add_job.assert_not_called()

    def test_shutdown_scheduler_when_running(self):
        with patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_sched.running = True
            from senryaku.services.scheduler import shutdown_scheduler
            shutdown_scheduler()
            mock_sched.shutdown.assert_called_once()

    def test_shutdown_scheduler_when_not_running(self):
        with patch("senryaku.services.scheduler.scheduler") as mock_sched:
            mock_sched.running = False
            from senryaku.services.scheduler import shutdown_scheduler
            shutdown_scheduler()
            mock_sched.shutdown.assert_not_called()
