from math import ceil

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models import Client, Meeting
from app.schemas import ClientCreate, ClientUpdate
from app.services.serializers import latest_meeting, serialize_client_detail, serialize_client_summary


def create_client(db: Session, payload: ClientCreate, user_id: int) -> Client:
    client = Client(name=payload.name.strip(), phone=payload.phone.strip(), user_id=user_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def get_client(db: Session, client_id: int, user_id: int | None = None) -> Client | None:
    query = (
        db.query(Client)
        .options(
            selectinload(Client.meetings).selectinload(Meeting.objections),
            selectinload(Client.meetings).selectinload(Meeting.pain_points),
            selectinload(Client.meetings).selectinload(Meeting.recommendations),
            selectinload(Client.meetings).selectinload(Meeting.buying_signals),
            selectinload(Client.meetings).selectinload(Meeting.next_actions),
        )
        .filter(Client.id == client_id)
    )
    if user_id is not None:
        query = query.filter(Client.user_id == user_id)
    return (
        query
        .first()
    )


def update_client(db: Session, client: Client, payload: ClientUpdate) -> Client:
    if payload.name is not None:
        client.name = payload.name.strip()
    if payload.phone is not None:
        client.phone = payload.phone.strip()
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client) -> None:
    db.delete(client)
    db.commit()


def list_clients(
    db: Session,
    user_id: int,
    search: str | None = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    query = db.query(Client).options(
        selectinload(Client.meetings).selectinload(Meeting.objections),
        selectinload(Client.meetings).selectinload(Meeting.pain_points),
        selectinload(Client.meetings).selectinload(Meeting.recommendations),
        selectinload(Client.meetings).selectinload(Meeting.buying_signals),
        selectinload(Client.meetings).selectinload(Meeting.next_actions),
    )
    query = query.filter(Client.user_id == user_id)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(or_(Client.name.ilike(token), Client.phone.ilike(token)))

    clients = [serialize_client_summary(client) for client in query.all()]

    reverse = sort_order.lower() != "asc"
    if sort_by == "name":
        clients.sort(key=lambda item: item["name"].lower(), reverse=reverse)
    elif sort_by == "acceptance":
        clients.sort(key=lambda item: item["acceptance_probability"] if item["acceptance_probability"] is not None else -1, reverse=reverse)
    else:
        clients.sort(key=lambda item: item["last_meeting_date"] or "", reverse=reverse)

    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    total = len(clients)
    start = (page - 1) * page_size
    return {
        "items": clients[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)) if total else 1,
    }


def search_clients(db: Session, query: str, user_id: int) -> list[dict]:
    return list_clients(db, user_id=user_id, search=query, page=1, page_size=20)["items"]


def client_detail_payload(client: Client) -> dict:
    detail = serialize_client_detail(client)
    latest = latest_meeting(client)
    detail["latest_meeting"] = detail["meetings"][0] if latest else None
    return detail
