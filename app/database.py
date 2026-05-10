from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.database_url, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_connection() -> sqlite3.Connection:
    return _connect()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  company TEXT NOT NULL,
  plan TEXT NOT NULL,
  locale TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  order_number TEXT NOT NULL,
  status TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  plan_name TEXT NOT NULL,
  status TEXT NOT NULL,
  renewal_date TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_email TEXT NOT NULL,
  category TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  summary TEXT NOT NULL,
  conversation TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_email TEXT NOT NULL,
  status TEXT NOT NULL,
  feedback TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS agent_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  intent TEXT NOT NULL,
  confidence REAL NOT NULL,
  faq_match_question TEXT,
  faq_match_answer TEXT,
  faq_match_score REAL NOT NULL,
  needs_tool INTEGER NOT NULL,
  tool_calls TEXT NOT NULL,
  needs_human INTEGER NOT NULL,
  risk_level TEXT NOT NULL,
  final_action TEXT NOT NULL,
  user_visible_reply TEXT NOT NULL,
  ticket_id INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
  FOREIGN KEY(ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  tool_name TEXT NOT NULL,
  tool_input TEXT NOT NULL,
  tool_output TEXT,
  success INTEGER NOT NULL,
  error_message TEXT,
  duration_ms REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
"""


def init_db() -> None:
    conn = _connect()
    try:
        conn.executescript(SCHEMA_SQL)
        _seed_if_empty(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    has_users = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    if has_users:
        return

    now = datetime.now(timezone.utc)
    users = [
        ("Alex Chen", "alex@example.com", "Northwind Labs", "Pro", "zh-CN", now.isoformat()),
        ("Taylor Smith", "taylor@example.com", "OrbitWorks", "Starter", "en-US", now.isoformat()),
        ("Jordan Lee", "jordan@example.com", "Maple Cloud", "Business", "en-US", now.isoformat()),
    ]
    conn.executemany(
        "INSERT INTO users (name, email, company, plan, locale, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        users,
    )

    user_rows = conn.execute("SELECT id, email FROM users").fetchall()
    user_by_email = {row["email"]: row["id"] for row in user_rows}
    orders = [
        (user_by_email["alex@example.com"], "ORD-1001", "paid", 99.0, "USD", (now - timedelta(days=25)).isoformat()),
        (user_by_email["alex@example.com"], "ORD-1002", "payment_failed", 199.0, "USD", (now - timedelta(days=2)).isoformat()),
        (user_by_email["taylor@example.com"], "ORD-1003", "paid", 29.0, "USD", (now - timedelta(days=14)).isoformat()),
        (user_by_email["jordan@example.com"], "ORD-1004", "paid", 499.0, "USD", (now - timedelta(days=35)).isoformat()),
    ]
    conn.executemany(
        "INSERT INTO orders (user_id, order_number, status, amount, currency, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        orders,
    )

    subscriptions = [
        (user_by_email["alex@example.com"], "Pro", "active", (now + timedelta(days=5)).isoformat()),
        (user_by_email["taylor@example.com"], "Starter", "trialing", (now + timedelta(days=7)).isoformat()),
        (user_by_email["jordan@example.com"], "Business", "past_due", (now + timedelta(days=1)).isoformat()),
    ]
    conn.executemany(
        "INSERT INTO subscriptions (user_id, plan_name, status, renewal_date) VALUES (?, ?, ?, ?)",
        subscriptions,
    )

    demo_conv_time = now.isoformat()
    conn.execute(
        "INSERT INTO conversations (user_email, status, feedback, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("alex@example.com", "active", None, demo_conv_time, demo_conv_time),
    )
    conversation_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.executemany(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        [
            (conversation_id, "user", "如何重置密码？", demo_conv_time),
            (conversation_id, "assistant", "你可以在登录页点击“忘记密码”，输入注册邮箱后按照邮件指引完成重置。", demo_conv_time),
        ],
    )


def load_faq_entries() -> list[dict[str, str]]:
    faq_path = Path(settings.faq_path)
    with faq_path.open("r", encoding="utf-8") as file:
        return json.load(file)
