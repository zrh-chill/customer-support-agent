from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import get_faq_service, get_support_service, router
from app.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_faq_service.cache_clear()
    get_support_service.cache_clear()
    yield


app = FastAPI(title="Customer Support Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/")
    def serve_frontend() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")

else:
    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "message": "Customer Support Agent API is running. Build the React frontend in ./frontend to serve the dashboard here."
        }
