from datetime import datetime

from pydantic import BaseModel, Field


class FollowUpStatusUpdate(BaseModel):
    status: str = Field(pattern="^(Upcoming|Due Today|Completed)$")


class FollowUpGenerateMessageRequest(BaseModel):
    regenerate: bool = True
    scheduled_at: datetime | None = None

