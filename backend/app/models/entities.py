from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(260), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="staff", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    clients: Mapped[list[Client]] = relationship(
        "Client",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[AuthSession]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(96), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship("User", back_populates="sessions")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped[User | None] = relationship("User", back_populates="clients")
    meetings: Mapped[list[Meeting]] = relationship(
        "Meeting",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="desc(Meeting.meeting_date), desc(Meeting.created_at)",
    )
    followups: Mapped[list[FollowUp]] = relationship(
        "FollowUp",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="asc(FollowUp.scheduled_at)",
    )


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_transcript: Mapped[str | None] = mapped_column(Text)
    speaker_notes: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(40), index=True)
    emotional_tone: Mapped[str | None] = mapped_column(String(80))
    urgency_level: Mapped[str | None] = mapped_column(String(40))
    confidence_score: Mapped[int | None] = mapped_column(Integer)
    acceptance_probability: Mapped[int | None] = mapped_column(Integer, index=True)
    acceptance_label: Mapped[str | None] = mapped_column(String(20), index=True)
    communication_style: Mapped[str | None] = mapped_column(Text)
    sales_strategy: Mapped[str | None] = mapped_column(Text)
    lead_stage: Mapped[str | None] = mapped_column(String(40), index=True)
    follow_up_strategy: Mapped[str | None] = mapped_column(Text)
    stakeholders: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    opportunities: Mapped[str | None] = mapped_column(Text)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    client: Mapped[Client] = relationship("Client", back_populates="meetings")
    objections: Mapped[list[Objection]] = relationship(
        "Objection",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    pain_points: Mapped[list[PainPoint]] = relationship(
        "PainPoint",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        "Recommendation",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    buying_signals: Mapped[list[BuyingSignal]] = relationship(
        "BuyingSignal",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    next_actions: Mapped[list[NextAction]] = relationship(
        "NextAction",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )
    followups: Mapped[list[FollowUp]] = relationship(
        "FollowUp",
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="asc(FollowUp.scheduled_at)",
    )


class Objection(Base):
    __tablename__ = "objections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    objection_text: Mapped[str] = mapped_column(Text, nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="objections")


class PainPoint(Base):
    __tablename__ = "pain_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    pain_point_text: Mapped[str] = mapped_column(Text, nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="pain_points")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_text: Mapped[str] = mapped_column(Text, nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="recommendations")


class BuyingSignal(Base):
    __tablename__ = "buying_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_text: Mapped[str] = mapped_column(Text, nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="buying_signals")


class NextAction(Base):
    __tablename__ = "next_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="next_actions")


class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    follow_up_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Upcoming", index=True)
    priority_level: Mapped[str] = mapped_column(String(20), nullable=False, default="Medium", index=True)
    objective: Mapped[str | None] = mapped_column(Text)
    communication_tone: Mapped[str | None] = mapped_column(String(80))
    whatsapp_message: Mapped[str | None] = mapped_column(Text)
    transcript_evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="followups")
    client: Mapped[Client] = relationship("Client", back_populates="followups")
