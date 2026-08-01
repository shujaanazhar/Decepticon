"""
Attendee REST API client.

Docs: https://docs.attendee.dev
"""

import requests

import config

TIMEOUT_SEC = 30


def _headers() -> dict:
    if not config.ATTENDEE_API_KEY:
        raise config.ConfigError("ATTENDEE is not set — cannot call the Attendee API.")
    return {
        "Authorization": f"Token {config.ATTENDEE_API_KEY}",
        "Content-Type": "application/json",
    }


def _url(path: str) -> str:
    return f"{config.ATTENDEE_BASE_URL}{path}"


def create_bot(meeting_url: str, bot_name: str = None, webhook_url: str = None) -> dict:
    """Send a bot into a meeting. Returns the bot object, which contains 'id'."""
    payload = {
        "meeting_url": meeting_url,
        "bot_name": bot_name or config.BOT_NAME,
    }
    if webhook_url:
        payload["webhooks"] = [
            {
                "url": webhook_url,
                "triggers": ["transcript.update", "bot.state_change"],
            }
        ]

    resp = requests.post(_url("/bots"), json=payload, headers=_headers(), timeout=TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def stop_bot(bot_id: str) -> dict:
    """Tell the bot to leave the meeting."""
    resp = requests.post(_url(f"/bots/{bot_id}/leave"), headers=_headers(), timeout=TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def get_bot(bot_id: str) -> dict:
    """Fetch current bot state."""
    resp = requests.get(_url(f"/bots/{bot_id}"), headers=_headers(), timeout=TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def get_transcript(bot_id: str) -> list:
    """Fetch the full transcript for a finished bot."""
    resp = requests.get(_url(f"/bots/{bot_id}/transcript"), headers=_headers(), timeout=TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()
