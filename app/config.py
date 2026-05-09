from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "Customer Support Agent"
    database_url: str = os.getenv("DATABASE_URL", "customer_support.db")
    faq_path: Path = Path(os.getenv("FAQ_PATH", "seed/faq.json"))
    llm_model: str = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    frontend_dir: Path = Path("frontend")


settings = Settings()
