from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    body: str
    from_: str | None = Field(default=None, alias="from")

    model_config = {"populate_by_name": True}


class Message(BaseModel):
    id: int
    direction: Literal["to_phone", "from_phone"]
    body: str
    from_: str | None = Field(default=None, serialization_alias="from")
    created_at: datetime

    model_config = {"populate_by_name": True}


class RepliesResponse(BaseModel):
    messages: list[Message]
    next_cursor: int
