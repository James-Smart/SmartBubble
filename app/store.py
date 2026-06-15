import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models import Message


@dataclass
class Session:
    messages: list[Message] = field(default_factory=list)
    next_id: int = 1
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._global_lock = asyncio.Lock()

    async def get_or_create(self, session_id: str) -> Session:
        async with self._global_lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = Session()
            return self._sessions[session_id]

    async def add_to_phone(
        self, session_id: str, body: str, from_: str | None = None
    ) -> Message:
        session = await self.get_or_create(session_id)
        async with session.lock:
            message = Message(
                id=session.next_id,
                direction="to_phone",
                body=body,
                from_=from_,
                created_at=datetime.now(timezone.utc),
            )
            session.next_id += 1
            session.messages.append(message)
            return message

    async def add_from_phone(self, session_id: str, body: str) -> Message:
        session = await self.get_or_create(session_id)
        async with session.lock:
            message = Message(
                id=session.next_id,
                direction="from_phone",
                body=body,
                from_=None,
                created_at=datetime.now(timezone.utc),
            )
            session.next_id += 1
            session.messages.append(message)
            return message

    async def list_all(self, session_id: str) -> list[Message]:
        session = await self.get_or_create(session_id)
        async with session.lock:
            return list(session.messages)

    async def list_replies_since(
        self, session_id: str, since: int
    ) -> tuple[list[Message], int]:
        session = await self.get_or_create(session_id)
        async with session.lock:
            replies = [
                m
                for m in session.messages
                if m.direction == "from_phone" and m.id > since
            ]
            next_cursor = max((m.id for m in session.messages), default=since)
            return replies, next_cursor


store = SessionStore()
