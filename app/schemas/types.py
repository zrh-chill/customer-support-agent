from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class IntentCategory(str, Enum):
    account_issue = "account_issue"
    billing_issue = "billing_issue"
    refund_request = "refund_request"
    technical_problem = "technical_problem"
    general_faq = "general_faq"
    human_support = "human_support"


class TicketPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TicketStatus(str, Enum):
    open = "open"
    handed_off = "handed_off"
    resolved = "resolved"


class SessionStatus(str, Enum):
    active = "active"
    needs_handoff = "needs_handoff"
    handed_off = "handed_off"
    resolved = "resolved"


class FeedbackRating(str, Enum):
    up = "up"
    down = "down"


class FAQEntry(BaseModel):
    question: str
    answer: str


class FAQMatch(BaseModel):
    matched: bool
    question: str | None = None
    answer: str | None = None
    score: float = 0.0


class TicketCreateRequest(BaseModel):
    user_email: EmailStr
    category: IntentCategory
    priority: TicketPriority
    summary: str
    conversation: str


class TicketCreateResult(BaseModel):
    ticket_id: int
    status: TicketStatus
    priority: TicketPriority
    category: IntentCategory
    summary: str
    created_at: datetime


class AgentDecision(BaseModel):
    intent: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    faq_match: FAQMatch
    needs_tool: bool
    tool_calls: list[str] = Field(default_factory=list)
    needs_human: bool
    risk_level: RiskLevel
    final_action: str
    user_visible_reply: str
    ticket_id: int | None = None


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class SessionSummary(BaseModel):
    id: int
    user_email: EmailStr
    user_name: str
    status: SessionStatus
    latest_message: str | None = None
    updated_at: datetime
    feedback: FeedbackRating | None = None


class UserProfile(BaseModel):
    id: int
    name: str
    email: EmailStr
    company: str
    plan: str
    locale: str
    created_at: datetime


class OrderRecord(BaseModel):
    id: int
    user_id: int
    order_number: str
    status: str
    amount: float
    currency: str
    created_at: datetime


class SubscriptionRecord(BaseModel):
    id: int
    user_id: int
    plan_name: str
    status: str
    renewal_date: datetime


class TicketRecord(BaseModel):
    id: int
    user_email: EmailStr
    category: IntentCategory
    priority: TicketPriority
    status: TicketStatus
    summary: str
    conversation: str
    created_at: datetime


class SessionContext(BaseModel):
    user: UserProfile | None = None
    orders: list[OrderRecord] = Field(default_factory=list)
    subscription: SubscriptionRecord | None = None
    latest_ticket: TicketRecord | None = None


class SessionDetailResponse(BaseModel):
    session: SessionSummary
    messages: list[ChatMessage]
    context: SessionContext
    decision: AgentDecision | None = None
    ticket: TicketRecord | None = None


class CreateSessionRequest(BaseModel):
    user_email: EmailStr


class CreateSessionResponse(BaseModel):
    session: SessionSummary


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    session: SessionSummary
    messages: list[ChatMessage]
    context: SessionContext
    decision: AgentDecision
    ticket: TicketRecord | None = None


class FeedbackRequest(BaseModel):
    rating: FeedbackRating


class HandoffResponse(BaseModel):
    ticket: TicketRecord
    session: SessionSummary
