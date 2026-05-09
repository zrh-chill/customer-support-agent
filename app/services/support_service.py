from __future__ import annotations

from fastapi import HTTPException

from app.agent.engine import AgentContext, SupportAgentEngine
from app.config import settings
from app.database import get_connection
from app.repositories.support_repository import SupportRepository
from app.schemas.types import (
    CreateSessionResponse,
    FeedbackRating,
    HandoffResponse,
    IntentCategory,
    RiskLevel,
    SendMessageResponse,
    SessionContext,
    SessionDetailResponse,
    SessionStatus,
    TicketCreateRequest,
    TicketPriority,
)
from app.services.faq_service import FAQService
from app.services.tool_service import ToolService


class SupportService:
    def __init__(self, faq_service: FAQService):
        self.faq_service = faq_service
        self.agent_engine = SupportAgentEngine(
            settings.llm_model,
            settings.openai_api_key,
            settings.openai_base_url,
        )

    def _repo(self) -> SupportRepository:
        conn = get_connection()
        return SupportRepository(conn)

    def create_or_get_session(self, user_email: str) -> CreateSessionResponse:
        repo = self._repo()
        try:
            session = repo.create_or_get_session(user_email)
            return CreateSessionResponse(session=session)
        finally:
            repo.conn.close()

    def list_sessions(self):
        repo = self._repo()
        try:
            return repo.list_sessions()
        finally:
            repo.conn.close()

    def get_session_detail(self, session_id: int) -> SessionDetailResponse:
        repo = self._repo()
        try:
            session = repo.get_session(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            context = self._build_context(repo, session.user_email)
            messages = repo.get_messages(session_id)
            decision = repo.get_latest_decision(session_id)
            ticket = repo.get_latest_ticket_for_user(session.user_email)
            return SessionDetailResponse(
                session=session,
                messages=messages,
                context=context,
                decision=decision,
                ticket=ticket,
            )
        finally:
            repo.conn.close()

    async def send_message(self, session_id: int, message: str) -> SendMessageResponse:
        repo = self._repo()
        try:
            session = repo.get_session(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            repo.add_message(session_id, "user", message)
            context = self._build_context(repo, session.user_email)
            faq_match = self.faq_service.match(message)
            decision = await self.agent_engine.decide(
                message=message,
                faq_match=faq_match,
                context=AgentContext(
                    user_email=session.user_email,
                    user_name=session.user_name,
                    has_profile=context.user is not None,
                    has_orders=bool(context.orders),
                    has_subscription=context.subscription is not None,
                ),
            )

            ticket = None
            tool_service = ToolService(repo)
            if "get_user_profile" in decision.tool_calls:
                context.user = tool_service.get_user_profile(session.user_email)
            if "get_user_orders" in decision.tool_calls:
                context.orders = tool_service.get_user_orders(session.user_email)
            if "get_subscription_status" in decision.tool_calls:
                context.subscription = tool_service.get_subscription_status(session.user_email)

            repo.add_message(session_id, "assistant", decision.user_visible_reply)
            if decision.final_action == "create_ticket" or decision.needs_human:
                conversation_messages = repo.get_messages(session_id)
                payload = TicketCreateRequest(
                    user_email=session.user_email,
                    category=decision.intent,
                    priority=self._priority_for(decision.intent, decision.risk_level),
                    summary=message[:120],
                    conversation=self._conversation_text(conversation_messages),
                )
                created = tool_service.create_ticket(payload)
                ticket = repo.get_ticket(created.ticket_id)
                decision.ticket_id = created.ticket_id
                repo.update_session_status(session_id, SessionStatus.needs_handoff if decision.needs_human else SessionStatus.active)
            repo.save_decision(session_id, decision)

            session = repo.get_session(session_id)
            messages = repo.get_messages(session_id)
            latest_ticket = ticket or repo.get_latest_ticket_for_user(session.user_email)
            return SendMessageResponse(
                session=session,
                messages=messages,
                context=self._build_context(repo, session.user_email),
                decision=decision,
                ticket=latest_ticket,
            )
        finally:
            repo.conn.close()

    def handoff_ticket(self, ticket_id: int) -> HandoffResponse:
        repo = self._repo()
        try:
            ticket = repo.mark_ticket_handoff(ticket_id)
            rows = repo.conn.execute(
                "SELECT id FROM conversations WHERE user_email = ? ORDER BY updated_at DESC LIMIT 1",
                (ticket.user_email,),
            ).fetchone()
            if rows:
                repo.update_session_status(rows["id"], SessionStatus.handed_off)
                session = repo.get_session(rows["id"])
            else:
                raise HTTPException(status_code=404, detail="Linked session not found")
            return HandoffResponse(ticket=ticket, session=session)
        finally:
            repo.conn.close()

    def save_feedback(self, session_id: int, rating: FeedbackRating) -> SessionDetailResponse:
        repo = self._repo()
        try:
            repo.save_feedback(session_id, rating)
            session = repo.get_session(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="Session not found")
            return SessionDetailResponse(
                session=session,
                messages=repo.get_messages(session_id),
                context=self._build_context(repo, session.user_email),
                decision=repo.get_latest_decision(session_id),
                ticket=repo.get_latest_ticket_for_user(session.user_email),
            )
        finally:
            repo.conn.close()

    def _build_context(self, repo: SupportRepository, user_email: str) -> SessionContext:
        user = repo.get_user_by_email(user_email)
        if user is None:
            return SessionContext()
        return SessionContext(
            user=user,
            orders=repo.get_orders_by_user_id(user.id),
            subscription=repo.get_subscription_by_user_id(user.id),
            latest_ticket=repo.get_latest_ticket_for_user(user_email),
        )

    def _priority_for(self, intent: IntentCategory, risk: RiskLevel) -> TicketPriority:
        if intent == IntentCategory.refund_request or risk == RiskLevel.high:
            return TicketPriority.high
        if intent in {IntentCategory.technical_problem, IntentCategory.human_support}:
            return TicketPriority.medium
        return TicketPriority.low

    def _conversation_text(self, messages) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in messages)
