from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.schemas.types import (
    AgentDecision,
    ChatMessage,
    FeedbackRating,
    OrderRecord,
    SessionStatus,
    SessionSummary,
    SubscriptionRecord,
    TicketRecord,
    TicketStatus,
    UserProfile,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupportRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_user_by_email(self, email: str) -> UserProfile | None:
        row = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return UserProfile.model_validate(dict(row)) if row else None

    def get_orders_by_user_id(self, user_id: int) -> list[OrderRecord]:
        rows = self.conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [OrderRecord.model_validate(dict(row)) for row in rows]

    def get_subscription_by_user_id(self, user_id: int) -> SubscriptionRecord | None:
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY renewal_date DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        return SubscriptionRecord.model_validate(dict(row)) if row else None

    def create_or_get_session(self, user_email: str) -> SessionSummary:
        user = self.get_user_by_email(user_email)
        if user is None:
            raise ValueError(f"Unknown user email: {user_email}")

        row = self.conn.execute(
            "SELECT * FROM conversations WHERE user_email = ? ORDER BY updated_at DESC LIMIT 1",
            (user_email,),
        ).fetchone()
        if row is None:
            now = utc_now()
            self.conn.execute(
                "INSERT INTO conversations (user_email, status, feedback, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_email, SessionStatus.active.value, None, now, now),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM conversations WHERE id = last_insert_rowid()").fetchone()
        return self._session_summary_from_row(row, user.name)

    def list_sessions(self) -> list[SessionSummary]:
        rows = self.conn.execute(
            """
            SELECT c.*, u.name AS user_name,
                   (
                     SELECT m.content FROM messages m
                     WHERE m.conversation_id = c.id
                     ORDER BY m.created_at DESC, m.id DESC
                     LIMIT 1
                   ) AS latest_message
            FROM conversations c
            JOIN users u ON u.email = c.user_email
            ORDER BY c.updated_at DESC
            """
        ).fetchall()
        return [self._session_summary_from_row(row, row["user_name"], row["latest_message"]) for row in rows]

    def get_session(self, session_id: int) -> SessionSummary | None:
        row = self.conn.execute(
            """
            SELECT c.*, u.name AS user_name,
                   (
                     SELECT m.content FROM messages m
                     WHERE m.conversation_id = c.id
                     ORDER BY m.created_at DESC, m.id DESC
                     LIMIT 1
                   ) AS latest_message
            FROM conversations c
            JOIN users u ON u.email = c.user_email
            WHERE c.id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._session_summary_from_row(row, row["user_name"], row["latest_message"])

    def add_message(self, session_id: int, role: str, content: str) -> ChatMessage:
        now = utc_now()
        self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        self.conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self.conn.commit()
        return ChatMessage(role=role, content=content, created_at=datetime.fromisoformat(now))

    def get_messages(self, session_id: int) -> list[ChatMessage]:
        rows = self.conn.execute(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        ).fetchall()
        return [ChatMessage.model_validate(dict(row)) for row in rows]

    def save_decision(self, session_id: int, decision: AgentDecision) -> None:
        self.conn.execute(
            """
            INSERT INTO agent_decisions (
              conversation_id, intent, confidence, faq_match_question, faq_match_answer,
              faq_match_score, needs_tool, tool_calls, needs_human, risk_level, final_action,
              user_visible_reply, ticket_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                decision.intent.value,
                decision.confidence,
                decision.faq_match.question,
                decision.faq_match.answer,
                decision.faq_match.score,
                int(decision.needs_tool),
                json.dumps(decision.tool_calls, ensure_ascii=False),
                int(decision.needs_human),
                decision.risk_level.value,
                decision.final_action,
                decision.user_visible_reply,
                decision.ticket_id,
                utc_now(),
            ),
        )
        self.conn.commit()

    def get_latest_decision(self, session_id: int) -> AgentDecision | None:
        row = self.conn.execute(
            "SELECT * FROM agent_decisions WHERE conversation_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return AgentDecision(
            intent=row["intent"],
            confidence=row["confidence"],
            faq_match={
                "matched": bool(row["faq_match_question"]),
                "question": row["faq_match_question"],
                "answer": row["faq_match_answer"],
                "score": row["faq_match_score"],
            },
            needs_tool=bool(row["needs_tool"]),
            tool_calls=json.loads(row["tool_calls"]),
            needs_human=bool(row["needs_human"]),
            risk_level=row["risk_level"],
            final_action=row["final_action"],
            user_visible_reply=row["user_visible_reply"],
            ticket_id=row["ticket_id"],
        )

    def create_ticket(
        self,
        user_email: str,
        category: str,
        priority: str,
        summary: str,
        conversation: str,
    ) -> TicketRecord:
        created_at = utc_now()
        self.conn.execute(
            """
            INSERT INTO tickets (user_email, category, priority, status, summary, conversation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_email, category, priority, TicketStatus.open.value, summary, conversation, created_at),
        )
        ticket_id = self.conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.conn.commit()
        return self.get_ticket(ticket_id)

    def get_ticket(self, ticket_id: int) -> TicketRecord | None:
        row = self.conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return TicketRecord.model_validate(dict(row)) if row else None

    def get_latest_ticket_for_user(self, user_email: str) -> TicketRecord | None:
        row = self.conn.execute(
            "SELECT * FROM tickets WHERE user_email = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (user_email,),
        ).fetchone()
        return TicketRecord.model_validate(dict(row)) if row else None

    def mark_ticket_handoff(self, ticket_id: int) -> TicketRecord:
        self.conn.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (TicketStatus.handed_off.value, ticket_id),
        )
        self.conn.commit()
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise ValueError("Ticket not found")
        return ticket

    def update_session_status(self, session_id: int, status: SessionStatus) -> None:
        self.conn.execute(
            "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, utc_now(), session_id),
        )
        self.conn.commit()

    def save_feedback(self, session_id: int, rating: FeedbackRating) -> None:
        self.conn.execute(
            "UPDATE conversations SET feedback = ?, updated_at = ? WHERE id = ?",
            (rating.value, utc_now(), session_id),
        )
        self.conn.commit()

    def save_tool_call_audit(
        self,
        conversation_id: int,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        success: bool,
        duration_ms: float,
        error_message: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO tool_calls (
              conversation_id, tool_name, tool_input, tool_output,
              success, error_message, duration_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                tool_name,
                json.dumps(tool_input, ensure_ascii=False),
                None if tool_output is None else json.dumps(tool_output, ensure_ascii=False),
                int(success),
                error_message,
                duration_ms,
                utc_now(),
            ),
        )
        self.conn.commit()

    def get_tool_call_audits(self, conversation_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM tool_calls WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _session_summary_from_row(
        self,
        row: sqlite3.Row,
        user_name: str,
        latest_message: str | None = None,
    ) -> SessionSummary:
        return SessionSummary(
            id=row["id"],
            user_email=row["user_email"],
            user_name=user_name,
            status=row["status"],
            latest_message=latest_message,
            updated_at=row["updated_at"],
            feedback=row["feedback"],
        )
