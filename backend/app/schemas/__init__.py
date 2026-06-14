from app.schemas.auth import LoginRequest, UserCreate, UserUpdate
from app.schemas.client import ClientCreate, ClientUpdate
from app.schemas.followup import FollowUpGenerateMessageRequest, FollowUpStatusUpdate
from app.schemas.meeting import MeetingProcessRequest

__all__ = [
    "ClientCreate",
    "ClientUpdate",
    "FollowUpGenerateMessageRequest",
    "FollowUpStatusUpdate",
    "LoginRequest",
    "MeetingProcessRequest",
    "UserCreate",
    "UserUpdate",
]
