from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.types import AgentDecision, FAQMatch, IntentCategory, RiskLevel

try:
    from pydantic_ai import Agent
except ImportError:  # pragma: no cover - optional runtime dependency
    Agent = None


INTENT_RULES: list[tuple[IntentCategory, tuple[str, ...]]] = [
    (IntentCategory.refund_request, ("退款", "refund", "chargeback")),
    (IntentCategory.billing_issue, ("账单", "扣费", "付款", "发票", "invoice", "payment", "billing")),
    (IntentCategory.account_issue, ("密码", "登录", "账号", "账户", "reset password", "account")),
    (IntentCategory.technical_problem, ("报错", "bug", "失败", "异常", "error", "technical", "无法使用")),
    (IntentCategory.human_support, ("人工", "客服", "转人工", "human", "agent")),
]


@dataclass
class AgentContext:
    user_email: str
    user_name: str
    has_profile: bool
    has_orders: bool
    has_subscription: bool


class SupportAgentEngine:
    def __init__(self, model_name: str, api_key: str | None = None) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self._agent = self._build_agent()

    def _build_agent(self) -> Any | None:
        if Agent is None or not self.api_key:
            return None
        return Agent(
            self.model_name,
            output_type=AgentDecision,
            system_prompt=(
                "You are a SaaS customer support agent. "
                "Classify the request, be conservative with risky operations, "
                "use FAQ answers when available, and escalate refunds to human support."
            ),
        )

    async def decide(
        self,
        message: str,
        faq_match: FAQMatch,
        context: AgentContext,
    ) -> AgentDecision:
        if self._agent is not None:
            prompt = (
                f"User email: {context.user_email}\n"
                f"User name: {context.user_name}\n"
                f"Message: {message}\n"
                f"FAQ matched: {faq_match.matched}\n"
                f"FAQ question: {faq_match.question}\n"
                f"FAQ answer: {faq_match.answer}\n"
                "Return a structured support decision."
            )
            try:
                result = await self._agent.run(prompt)
                return result.output
            except Exception:
                pass
        return self._rule_based_decision(message=message, faq_match=faq_match, context=context)

    def _rule_based_decision(
        self,
        message: str,
        faq_match: FAQMatch,
        context: AgentContext,
    ) -> AgentDecision:
        intent = self._detect_intent(message)
        lower_message = message.lower()
        tool_calls: list[str] = []
        needs_tool = False
        needs_human = False
        risk = RiskLevel.low
        final_action = "reply_with_faq" if faq_match.matched else "reply"

        if faq_match.matched:
            reply = faq_match.answer or "我已经找到了相关帮助文档。"
            return AgentDecision(
                intent=intent if intent != IntentCategory.human_support else IntentCategory.general_faq,
                confidence=0.91,
                faq_match=faq_match,
                needs_tool=False,
                tool_calls=[],
                needs_human=False,
                risk_level=RiskLevel.low,
                final_action=final_action,
                user_visible_reply=reply,
            )

        if intent == IntentCategory.refund_request:
            needs_human = True
            risk = RiskLevel.high
            final_action = "create_ticket"
            reply = (
                "退款属于敏感操作，我不能直接为你执行。"
                "我会为你创建高优先级工单，并交由人工客服进一步确认。"
            )
            return AgentDecision(
                intent=intent,
                confidence=0.95,
                faq_match=faq_match,
                needs_tool=True,
                tool_calls=["create_ticket"],
                needs_human=True,
                risk_level=risk,
                final_action=final_action,
                user_visible_reply=reply,
            )

        if intent == IntentCategory.account_issue:
            needs_tool = context.has_profile
            if needs_tool:
                tool_calls.append("get_user_profile")
            reply = (
                f"{context.user_name}，我已检查到你的账户信息。"
                "如果你当前无法登录，建议先尝试重置密码；如果仍失败，我可以继续帮你转人工。"
            )
        elif intent == IntentCategory.billing_issue:
            needs_tool = True
            tool_calls.extend(["get_user_orders", "get_subscription_status"])
            final_action = "reply_with_context"
            if "发票" in message or "invoice" in lower_message:
                reply = "我已经定位到你的账单上下文。你可以在账单中心选择对应订单申请发票。"
            else:
                reply = "我已经检查到你的订单和订阅状态，稍后会在右侧面板展示相关账单上下文供客服跟进。"
        elif intent == IntentCategory.technical_problem:
            needs_tool = context.has_profile
            if needs_tool:
                tool_calls.append("get_user_profile")
            needs_human = True
            risk = RiskLevel.medium
            final_action = "create_ticket"
            reply = "这看起来像一个技术问题。我会先记录你的问题并创建工单，方便技术支持继续排查。"
        elif intent == IntentCategory.human_support:
            needs_tool = True
            tool_calls.append("create_ticket")
            needs_human = True
            risk = RiskLevel.medium
            final_action = "create_ticket"
            reply = "我会马上帮你转交人工支持，并附上当前对话上下文。"
        else:
            if "套餐" in message or "subscription" in lower_message or "plan" in lower_message:
                needs_tool = True
                tool_calls.append("get_subscription_status")
                final_action = "reply_with_context"
                reply = "我已经读取了你的订阅状态，可以帮你查看当前套餐和续费信息。"
            else:
                reply = "我已经理解了你的问题。若你愿意，可以再补充一点细节，我会继续帮你定位。"

        return AgentDecision(
            intent=intent,
            confidence=0.82 if needs_tool else 0.74,
            faq_match=faq_match,
            needs_tool=needs_tool,
            tool_calls=tool_calls,
            needs_human=needs_human,
            risk_level=risk,
            final_action=final_action,
            user_visible_reply=reply,
        )

    def _detect_intent(self, message: str) -> IntentCategory:
        lower_message = message.lower()
        for intent, keywords in INTENT_RULES:
            if any(keyword in lower_message for keyword in keywords):
                return intent
        if "套餐" in message or "订阅" in message or "faq" in lower_message:
            return IntentCategory.general_faq
        return IntentCategory.general_faq
