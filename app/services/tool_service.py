from __future__ import annotations

from app.repositories.support_repository import SupportRepository
from app.schemas.types import TicketCreateRequest, TicketCreateResult


class ToolService:
    def __init__(self, repository: SupportRepository):
        self.repository = repository

    def get_user_profile(self, user_email: str):
        return self.repository.get_user_by_email(user_email)

    def get_user_orders(self, user_email: str):
        user = self.repository.get_user_by_email(user_email)
        if user is None:
            return []
        return self.repository.get_orders_by_user_id(user.id)

    def get_subscription_status(self, user_email: str):
        user = self.repository.get_user_by_email(user_email)
        if user is None:
            return None
        return self.repository.get_subscription_by_user_id(user.id)

    def create_ticket(self, payload: TicketCreateRequest) -> TicketCreateResult:
        ticket = self.repository.create_ticket(
            user_email=payload.user_email,
            category=payload.category.value,
            priority=payload.priority.value,
            summary=payload.summary,
            conversation=payload.conversation,
        )
        return TicketCreateResult(
            ticket_id=ticket.id,
            status=ticket.status,
            priority=ticket.priority,
            category=ticket.category,
            summary=ticket.summary,
            created_at=ticket.created_at,
        )
