from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, selectinload

from app.models import AuthSession, Client, User

PASSWORD_ITERATIONS = 210_000
SESSION_DAYS = 7

DEFAULT_USERS = [
    ("admin", "admin123", "System Admin", "admin"),
    ("samy", "samy123", "Mr. Samy", "staff"),
    ("ahmed", "ahmed123", "Ahmed", "staff"),
    ("sales1", "sales123", "Sales Rep 1", "staff"),
    ("sales2", "sales223", "Sales Rep 2", "staff"),
    ("closer1", "closer123", "Closer 1", "staff"),
    ("closer2", "closer223", "Closer 2", "staff"),
    ("manager", "manager123", "Sales Manager", "admin"),
    ("ops", "ops123", "Operations User", "staff"),
    ("demo", "demo123", "Demo User", "staff"),
]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def seed_default_users(db: Session) -> None:
    for username, password, full_name, role in DEFAULT_USERS:
        existing = db.query(User).filter(User.username == username).first()
        if existing is None:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
            )
    db.flush()

    admin = db.query(User).filter(User.username == "admin").first()
    if admin is not None:
        db.query(Client).filter(Client.user_id.is_(None)).update({Client.user_id: admin.id})
    db.commit()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username.strip()).first()
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user: User) -> tuple[str, AuthSession]:
    raw_token = secrets.token_urlsafe(40)
    session = AuthSession(
        user_id=user.id,
        token_hash=token_digest(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, session


def get_user_by_token(db: Session, token: str) -> User | None:
    digest = token_digest(token)
    session = (
        db.query(AuthSession)
        .options(selectinload(AuthSession.user))
        .filter(AuthSession.token_hash == digest)
        .first()
    )
    if session is None or session.revoked_at is not None:
        return None
    if _utc(session.expires_at) <= datetime.now(UTC):
        return None
    if session.user is None or not session.user.is_active:
        return None
    return session.user


def revoke_session(db: Session, token: str) -> None:
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_digest(token)).first()
    if session is not None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def list_users(db: Session) -> list[dict]:
    users = db.query(User).order_by(User.username.asc()).all()
    return [serialize_user(user) for user in users]


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    full_name: str | None,
    role: str,
    is_active: bool,
) -> User:
    existing = db.query(User).filter(User.username == username.strip()).first()
    if existing is not None:
        raise ValueError("Username already exists")
    user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        full_name=full_name.strip() if full_name else None,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    username: str | None = None,
    password: str | None = None,
    full_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User:
    if username is not None and username.strip() != user.username:
        existing = db.query(User).filter(User.username == username.strip(), User.id != user.id).first()
        if existing is not None:
            raise ValueError("Username already exists")
        user.username = username.strip()
    if password:
        user.password_hash = hash_password(password)
    if full_name is not None:
        user.full_name = full_name.strip() or None
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
