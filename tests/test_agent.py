from __future__ import annotations

import asyncio
import logging

from app.agent.engine import AgentContext, SupportAgentEngine
from app.schemas.types import FAQMatch, IntentCategory


def test_rule_based_intent_detection():
    cases = [
        ("我的账号登录不了", IntentCategory.account_issue),
        ("为什么这次扣费失败了", IntentCategory.billing_issue),
        ("我想申请退款", IntentCategory.refund_request),
        ("系统一直报错无法使用", IntentCategory.technical_problem),
        ("如何修改套餐？", IntentCategory.billing_issue),
        ("帮我转人工客服", IntentCategory.human_support),
    ]
    engine = SupportAgentEngine("mock", None)

    for message, expected_intent in cases:
        decision = asyncio.run(
            engine.decide(
                message=message,
                faq_match=FAQMatch(matched=False, score=0.0),
                context=AgentContext(
                    user_email="alex@example.com",
                    user_name="Alex Chen",
                    has_profile=True,
                    has_orders=True,
                    has_subscription=True,
                ),
            )
        )
        assert decision.intent == expected_intent


def test_llm_fallback_logs_warning(caplog):
    class BrokenAgent:
        async def run(self, prompt):
            raise RuntimeError("provider boom")

    engine = SupportAgentEngine("mock-model", None)
    engine._agent = BrokenAgent()

    with caplog.at_level(logging.WARNING):
        decision = asyncio.run(
            engine.decide(
                message="帮我转人工客服",
                faq_match=FAQMatch(matched=False, score=0.0),
                context=AgentContext(
                    user_email="alex@example.com",
                    user_name="Alex Chen",
                    has_profile=True,
                    has_orders=True,
                    has_subscription=True,
                ),
            )
        )

    assert decision.intent == IntentCategory.human_support
    assert "falling back to rule-based decision" in caplog.text
    assert "provider boom" in caplog.text
