from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import feedback, health, tickets
from app.config import Settings, get_settings
from app.container import build_container
from app.errors import NoDraftToReview, TicketNotFound

# The Docker build copies the compiled React app (frontend/dist) here.
STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = build_container(settings)
        yield

    app = FastAPI(title="Customer Support Triage Co-pilot", version="1.0.0", lifespan=lifespan)

    # Needed only for `npm run dev` (UI on :5173, API on :8000). Same-origin deployments never hit it.
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(tickets.router)
    app.include_router(feedback.router)

    @app.exception_handler(TicketNotFound)
    async def _not_found(_: Request, exc: TicketNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"ticket {exc} not found or not yet triaged"})

    @app.exception_handler(NoDraftToReview)
    async def _no_draft(_: Request, exc: NoDraftToReview) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "this ticket has no draft to give feedback on"})

    # Mounted last so every API route above wins; "/" then serves index.html and the hashed assets.
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")

    return app


app = create_app()
