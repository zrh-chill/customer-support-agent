from __future__ import annotations


def test_create_and_list_sessions(client):
    create_response = client.post("/api/chat/sessions", json={"user_email": "taylor@example.com"})
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["session"]["user_email"] == "taylor@example.com"

    list_response = client.get("/api/chat/sessions")
    assert list_response.status_code == 200
    sessions = list_response.json()
    assert any(session["user_email"] == "taylor@example.com" for session in sessions)


def test_faq_answer_is_prioritized(client):
    session_id = client.post("/api/chat/sessions", json={"user_email": "alex@example.com"}).json()["session"]["id"]
    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "如何重置密码？"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"]["faq_match"]["matched"] is True
    assert payload["decision"]["ticket_id"] is None
    assert "忘记密码" in payload["decision"]["user_visible_reply"]


def test_billing_message_calls_business_tools(client):
    session_id = client.post("/api/chat/sessions", json={"user_email": "alex@example.com"}).json()["session"]["id"]
    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "我的账单有问题，帮我看看最近订单和订阅状态"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"]["intent"] == "billing_issue"
    assert "get_user_orders" in payload["decision"]["tool_calls"]
    assert "get_subscription_status" in payload["decision"]["tool_calls"]
    assert payload["context"]["orders"]
    assert payload["context"]["subscription"]["plan_name"]


def test_refund_request_creates_high_risk_ticket(client):
    session_id = client.post("/api/chat/sessions", json={"user_email": "jordan@example.com"}).json()["session"]["id"]
    response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "我想退款，请尽快处理"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["decision"]["intent"] == "refund_request"
    assert payload["decision"]["risk_level"] == "high"
    assert payload["ticket"]["priority"] == "high"
    assert payload["ticket"]["status"] == "open"


def test_handoff_and_feedback_flow(client):
    session_id = client.post("/api/chat/sessions", json={"user_email": "jordan@example.com"}).json()["session"]["id"]
    message_response = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        json={"message": "帮我转人工客服"},
    )
    ticket_id = message_response.json()["ticket"]["id"]

    handoff_response = client.post(f"/api/tickets/{ticket_id}/handoff")
    assert handoff_response.status_code == 200
    assert handoff_response.json()["ticket"]["status"] == "handed_off"

    feedback_response = client.post(
        f"/api/chat/sessions/{session_id}/feedback",
        json={"rating": "up"},
    )
    assert feedback_response.status_code == 200
    assert feedback_response.json()["session"]["feedback"] == "up"
