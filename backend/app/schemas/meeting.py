from datetime import date

from pydantic import BaseModel, Field, model_validator


class MeetingProcessRequest(BaseModel):
    client_id: int | None = None
    client_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=50)
    meeting_date: date | None = None
    transcript: str = Field(min_length=10)

    @model_validator(mode="after")
    def validate_client_reference(self) -> "MeetingProcessRequest":
        if self.client_id is None and not self.client_name:
            raise ValueError("client_id or client_name is required")
        return self

