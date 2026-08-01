"""
Transcript files, shared by both backends.

One file per meeting, appended to as lines arrive, so a transcript survives a
crash mid-meeting instead of only existing at the end.
"""

import datetime
from pathlib import Path

import config

_SEPARATOR = "-" * 60


def _safe(title: str) -> str:
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in title)


class Transcript:
    """An open transcript file for one meeting."""

    def __init__(self, title: str, session_id: str, backend: str):
        directory = Path(config.TRANSCRIPTS_DIR)
        directory.mkdir(parents=True, exist_ok=True)

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        self.path = directory / f"{_safe(title)}_{date_str}_{session_id[:8]}.txt"
        self.title = title
        self.closed = False

        with open(self.path, "w") as fh:
            fh.write(f"Meeting: {title}\n")
            fh.write(f"Backend: {backend}\n")
            fh.write(f"Started: {datetime.datetime.now().isoformat()}\n")
            fh.write(_SEPARATOR + "\n\n")

        print(f"[transcript] Writing to {self.path}")

    def line(self, speaker: str, text: str, timestamp: str = None):
        """Append one utterance. Ignored once the transcript is closed."""
        if self.closed or not text.strip():
            return
        stamp = timestamp or datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{stamp}] {speaker}: {text.strip()}\n"
        with open(self.path, "a") as fh:
            fh.write(entry)
        print(f"[transcript] {entry.strip()}")

    def close(self, reason: str = "ended"):
        if self.closed:
            return
        self.closed = True
        with open(self.path, "a") as fh:
            fh.write(f"\n{_SEPARATOR}\n")
            fh.write(f"Ended: {datetime.datetime.now().isoformat()} ({reason})\n")
        print(f"[transcript] Saved {self.path}")


def stamp_from_ms(timestamp_ms: int) -> str:
    """Format an Attendee millisecond offset as H:MM:SS since meeting start."""
    return str(datetime.timedelta(milliseconds=timestamp_ms)).split(".")[0]
