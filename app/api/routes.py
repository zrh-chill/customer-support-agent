from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter

from app.schemas.types import (
    CreateSessionRequest,
    CreateSessionResponse,
    FeedbackRequest,
    HandoffResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionDetailResponse,
    SessionSummary,
)
from app.services.faq_service import FAQService
from app.services.support_service import SupportService

router = APIRouter(prefix="/api")


@lru_cache
def get_faq_service() -> FAQService:
    return FAQService()


@lru_cache
def get_support_service() -> SupportService:
    return SupportService(faq_service=get_faq_service())


@router.post("/chat/sessions", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest) -> CreateSessionResponse:
    return get_support_service().create_or_get_session(payload.user_email)


@router.get("/chat/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    return get_support_service().list_sessions()


@router.get("/chat/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: int) -> SessionDetailResponse:
    return get_support_service().get_session_detail(session_id)


@router.post("/chat/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: int, payload: SendMessageRequest) -> SendMessageResponse:
    return await get_support_service().send_message(session_id, payload.message)


@router.post("/tickets/{ticket_id}/handoff", response_model=HandoffResponse)
def handoff_ticket(ticket_id: int) -> HandoffResponse:
    return get_support_service().handoff_ticket(ticket_id)


@router.post("/chat/sessions/{session_id}/feedback", response_model=SessionDetailResponse)
def save_feedback(session_id: int, payload: FeedbackRequest) -> SessionDetailResponse:
    return get_support_service().save_feedback(session_id, payload.rating)


@router.get("/faqs")
def get_faqs():
    return get_faq_service().list_entries()
