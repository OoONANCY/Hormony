import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..agents.llm import LLMConfigError, provider_name, resolve_vision_llm
from ..auth import check_secret
from ..config import settings
from ..db import db_ok, init_db
from .routes_analyses import router as analyses_router
from .routes_auth import router as auth_router
from .routes_events import router as events_router
from .routes_profiles import router as profiles_router
from .routes_reports import router as reports_router

log = logging.getLogger("hormony.api")


class ErrorsAsJson:
    """Turn unhandled exceptions into a JSON 500 *inside* the CORS layer, so browsers can read the error."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def _send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)
        try:
            await self.app(scope, receive, _send)
        except Exception:
            log.exception("unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            await JSONResponse({"detail": "Internal server error"}, status_code=500)(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        log.warning("Hormony LLM provider: %s", provider_name(settings))
    except LLMConfigError as e:
        log.error("LLM misconfigured: %s", e)
    yield


def create_app() -> FastAPI:
    check_secret()  # refuse to start with a missing or guessable token secret: anyone could sign in as anyone
    app = FastAPI(title="Hormony API", lifespan=lifespan)
    app.add_middleware(ErrorsAsJson)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # outermost
    app.include_router(auth_router)
    app.include_router(events_router)
    app.include_router(analyses_router)
    app.include_router(profiles_router)
    app.include_router(reports_router)

    @app.get("/health")
    def health():
        ok = db_ok()
        try:
            llm = provider_name(settings)
        except LLMConfigError as e:
            llm = f"misconfigured: {e}"
        vision = resolve_vision_llm(settings)
        return {"ok": ok, "db": "ok" if ok else "unavailable", "llm": llm, "vision": vision.name if vision else None}

    return app


app = create_app()
