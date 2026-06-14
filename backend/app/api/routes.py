from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import current_token, require_admin, require_user
from app.database import get_db
from app.models import User
from app.schemas import ClientCreate, ClientUpdate, FollowUpStatusUpdate, LoginRequest, MeetingProcessRequest, UserCreate, UserUpdate
from app.services.analytics_service import dashboard_analytics
from app.services.auth_service import (
    authenticate_user,
    create_session,
    create_user,
    get_user,
    list_users,
    revoke_session,
    serialize_user,
    update_user,
)
from app.services.client_service import (
    client_detail_payload,
    create_client,
    delete_client,
    get_client,
    list_clients,
    search_clients,
    update_client,
)
from app.services.meeting_service import (
    MeetingProcessingError,
    get_meeting,
    get_meeting_payload,
    list_client_meetings,
    process_meeting,
    reprocess_meeting,
)
from app.services.followup_service import get_followup, list_followups, regenerate_followup_message, update_followup_status
from app.services.pdf_service import generate_meeting_pdf
from app.services.serializers import serialize_client_detail

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "AI Closer"}


@router.post("/auth/login")
def auth_login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token, session = create_session(db, user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": session.expires_at.isoformat(),
        "user": serialize_user(user),
    }


@router.post("/auth/logout")
def auth_logout(token: str = Depends(current_token), db: Session = Depends(get_db)) -> dict:
    revoke_session(db, token)
    return {"status": "ok"}


@router.get("/auth/me")
def auth_me(current_user: User = Depends(require_user)) -> dict:
    return serialize_user(current_user)


@router.get("/users")
def users_index(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return {"items": list_users(db)}


@router.post("/users", status_code=201)
def users_create(payload: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    try:
        user = create_user(
            db,
            username=payload.username,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return serialize_user(user)


@router.put("/users/{user_id}")
def users_update(user_id: int, payload: UserUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        return serialize_user(
            update_user(
                db,
                user,
                username=payload.username,
                password=payload.password,
                full_name=payload.full_name,
                role=payload.role,
                is_active=payload.is_active,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analytics/summary")
def analytics_summary(current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return dashboard_analytics(db, user_id=current_user.id)


@router.get("/clients")
def clients_index(
    search: str | None = None,
    sort_by: str = Query(default="date", pattern="^(date|name|acceptance)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    return list_clients(
        db,
        user_id=current_user.id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.post("/clients", status_code=201)
def clients_create(payload: ClientCreate, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return serialize_client_detail(create_client(db, payload, user_id=current_user.id))


@router.get("/clients/{client_id}/meetings")
def clients_meetings(client_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> list[dict]:
    if get_client(db, client_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return list_client_meetings(db, client_id, user_id=current_user.id)


@router.get("/clients/{client_id}")
def clients_show(client_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    client = get_client(db, client_id, user_id=current_user.id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client_detail_payload(client)


@router.put("/clients/{client_id}")
def clients_update(client_id: int, payload: ClientUpdate, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    client = get_client(db, client_id, user_id=current_user.id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return serialize_client_detail(update_client(db, client, payload))


@router.delete("/clients/{client_id}", status_code=204)
def clients_delete(client_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> None:
    client = get_client(db, client_id, user_id=current_user.id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    delete_client(db, client)


@router.post("/meetings/process", status_code=201)
async def meetings_process(payload: MeetingProcessRequest, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    try:
        return await process_meeting(db, payload, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meetings/{meeting_id}")
def meetings_show(meeting_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    try:
        return get_meeting_payload(db, meeting_id, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/meetings/{meeting_id}/reprocess")
async def meetings_reprocess(meeting_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    try:
        return await reprocess_meeting(db, meeting_id, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/meetings/{meeting_id}/export.pdf")
def meetings_export_pdf(meeting_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> StreamingResponse:
    meeting = get_meeting(db, meeting_id, user_id=current_user.id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    pdf_bytes = generate_meeting_pdf(meeting)
    headers = {"Content-Disposition": f'attachment; filename="ai-closer-meeting-{meeting_id}.pdf"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.get("/search")
def search(q: str = Query(min_length=1), current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    return {"clients": search_clients(db, q, user_id=current_user.id)}


@router.get("/followups")
def followups_list(
    status: str | None = Query(default=None),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    return list_followups(db, user_id=current_user.id, status=status)


@router.get("/followups/{followup_id}")
def followups_show(followup_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    try:
        return get_followup(db, followup_id, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/followups/{followup_id}/status")
def followups_update_status(
    followup_id: int,
    payload: FollowUpStatusUpdate,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return update_followup_status(db, followup_id, payload.status, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/followups/{followup_id}/generate-message")
async def followups_generate_message(followup_id: int, current_user: User = Depends(require_user), db: Session = Depends(get_db)) -> dict:
    try:
        return await regenerate_followup_message(db, followup_id, user_id=current_user.id)
    except MeetingProcessingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
