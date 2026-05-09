from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app.config import Settings
    import app.api.routes as routes
    import app.config as config
    import app.database as database
    import app.main as main
    import app.services.support_service as support_service_module

    test_settings = Settings(
        database_url=str(tmp_path / "test.db"),
        faq_path=Path(__file__).resolve().parent.parent / "seed/faq.json",
        llm_model="mock-model",
        openai_api_key=None,
    )

    monkeypatch.setattr(config, "settings", test_settings)
    monkeypatch.setattr(database, "settings", test_settings)
    monkeypatch.setattr(support_service_module, "settings", test_settings)
    routes.get_faq_service.cache_clear()
    routes.get_support_service.cache_clear()
    database.init_db()

    with TestClient(main.app) as test_client:
        yield test_client
