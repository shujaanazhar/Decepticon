"""
Receives Attendee's transcript.update and bot.state_change callbacks.

Attendee needs a public HTTPS URL to reach this, so it only runs when
WEBHOOK_PUBLIC_URL is set — typically an ngrok tunnel:

    ngrok http 8765
    WEBHOOK_PUBLIC_URL=https://<id>.ngrok-free.app

Without it the attendee backend still works; transcripts are just fetched in
one go after the meeting instead of streaming in live.
"""

import threading

from flask import Flask, jsonify, request

import config
from transcripts import Transcript, stamp_from_ms

app = Flask(__name__)

# bot_id -> Transcript. Written by the Flask thread, read by the event loop.
_sessions: dict[str, Transcript] = {}
_lock = threading.Lock()

ENDED_STATES = {"ended", "fatal_error", "post_processing_complete"}


def register_session(bot_id: str, meeting_title: str) -> Transcript:
    """Open a transcript for a bot before its first utterance arrives."""
    with _lock:
        existing = _sessions.get(bot_id)
        if existing:
            return existing
        transcript = Transcript(meeting_title, bot_id, backend="attendee")
        _sessions[bot_id] = transcript
        return transcript


def close_session(bot_id: str, reason: str = "ended") -> None:
    with _lock:
        transcript = _sessions.pop(bot_id, None)
    if transcript:
        transcript.close(reason)


def session_for(bot_id: str) -> Transcript | None:
    with _lock:
        return _sessions.get(bot_id)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    trigger = data.get("trigger")
    bot_id = data.get("bot_id")

    if not bot_id:
        return jsonify({"ok": True}), 200

    if trigger == "transcript.update":
        utterance = data.get("data", {})
        text = utterance.get("transcription", {}).get("transcript", "").strip()
        if text:
            transcript = session_for(bot_id) or register_session(bot_id, f"meeting_{bot_id[:8]}")
            transcript.line(
                speaker=utterance.get("speaker_name", "Unknown"),
                text=text,
                timestamp=stamp_from_ms(utterance.get("timestamp_ms", 0)),
            )

    elif trigger == "bot.state_change":
        payload = data.get("data", {})
        state = payload.get("bot_state") or payload.get("state", "")
        if state in ENDED_STATES:
            close_session(bot_id, state)

    return jsonify({"ok": True}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "sessions": len(_sessions)}), 200


def run_server(host: str = "0.0.0.0", port: int = None) -> None:
    app.run(host=host, port=port or config.WEBHOOK_PORT, debug=False)


def start_in_background(port: int = None) -> threading.Thread:
    """Run the webhook server on a daemon thread and return it."""
    thread = threading.Thread(target=run_server, kwargs={"port": port}, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    run_server()
