"""Webhook notification service."""

import httpx
from senryaku.config import get_settings


def send_notification(message: str) -> bool:
    """Send notification via configured webhook.

    Supports ntfy, telegram, and generic webhook formats.
    Returns True on success, False on failure or if no webhook is configured.
    """
    settings = get_settings()

    if not settings.webhook_url:
        return False

    try:
        if settings.webhook_type == "ntfy":
            httpx.post(
                settings.webhook_url,
                content=message.encode(),
                headers={"Title": "Senryaku"},
            )
        elif settings.webhook_type == "telegram":
            # Telegram bot API format
            httpx.post(
                settings.webhook_url,
                json={
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
        elif settings.webhook_type == "generic":
            httpx.post(
                settings.webhook_url,
                json={
                    "text": message,
                    "source": "senryaku",
                },
            )
        return True
    except Exception:
        return False
