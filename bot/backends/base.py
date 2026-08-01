"""The contract every meeting backend implements."""

from abc import ABC, abstractmethod


class MeetingBackend(ABC):
    """
    Attends meetings on the user's behalf.

    The orchestrator in main.py owns the calendar polling and scheduling; a
    backend only has to know how to sit in one meeting and come back when it
    is over.
    """

    #: Short name used in logs and transcript headers.
    name: str = "unnamed"

    #: Whether this backend can talk back. Purely informational — main.py
    #: prints it at startup so the difference isn't a surprise mid-meeting.
    can_speak: bool = False

    async def startup(self) -> None:
        """Prepare anything expensive or long-lived. Called once, before any meeting."""

    @abstractmethod
    async def attend(self, event: dict) -> None:
        """
        Join `event`, stay for the meeting, and return once it has ended.

        `event` carries the keys produced by gcalendar.get_upcoming_meets():
        `event_id`, `title`, `url`, and `start`.
        """

    async def shutdown(self) -> None:
        """Release anything startup() acquired. Called once, on the way out."""
