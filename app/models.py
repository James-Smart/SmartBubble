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


class LocationReport(BaseModel):
    """What the phone UI posts when the customer answers the permission prompt."""

    status: Literal["granted", "denied"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    label: str | None = None


class LocationState(BaseModel):
    """What integrations read back. `none` until the customer answers."""

    status: Literal["none", "granted", "denied"]
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    label: str | None = None
    shared_at: datetime | None = None
