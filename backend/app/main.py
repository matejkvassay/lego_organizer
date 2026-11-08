from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import api, auth
from .config import get_settings
from .db import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: data:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'")


def check_secrets(s) -> None:
    """Refuse to start with a guessable session secret: anyone who knows it can forge a login cookie."""
    if len(s.session_secret) < 32 or s.session_secret.lower().startswith("change-me"):
        raise RuntimeError(
            "SESSION_SECRET is missing, too short (<32 chars) or still the placeholder. "
            "Generate one with: openssl rand -hex 32")


def create_app() -> FastAPI:
    s = get_settings()
    check_secrets(s)
    # No public /docs or /openapi.json: they would describe the API to anyone on the internet.
    app = FastAPI(title="Lego Organizer", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.update({
            "Content-Security-Policy": CSP,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
            "Cache-Control": resp.headers.get("Cache-Control", "no-store") if request.url.path.startswith(("/api", "/auth")) else resp.headers.get("Cache-Control", "no-cache"),
        })
        if s.base_url.startswith("https"):
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    app.add_middleware(
        SessionMiddleware, secret_key=s.session_secret, max_age=60 * 60 * 24 * 30,
        https_only=s.base_url.startswith("https"), same_site="lax",
    )
    app.include_router(auth.router)
    app.include_router(api.router)

    dist = Path(s.frontend_dist).resolve()
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.split("/", 1)[0] in ("api", "auth"):
                raise HTTPException(404)  # unknown API routes must not fall through to the SPA
            f = (dist / path).resolve()
            # Only serve real files that live inside the dist folder (blocks ../ and encoded variants).
            if path and f.is_file() and f.is_relative_to(dist):
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
