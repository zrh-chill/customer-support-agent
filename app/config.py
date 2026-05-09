from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: str = ".env") -> None:
    env_file = Path(dotenv_path)
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Customer Support Agent"
    database_url: str = os.getenv("DATABASE_URL", "customer_support.db")
    faq_path: Path = Path(os.getenv("FAQ_PATH", "seed/faq.json"))
    llm_model: str = os.getenv("LLM_MODEL", "openai:gpt-4o-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL")
    frontend_dir: Path = Path("frontend")


settings = Settings()
