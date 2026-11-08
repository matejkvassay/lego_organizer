"""Google OAuth login; only ALLOWED_EMAIL may use the app."""
from urllib.parse import urlparse

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .config import get_settings

router = APIRouter(prefix="/auth")

oauth = OAuth()
_registered = False


def _client():
    global _registered
    if not _registered:
        s = get_settings()
        oauth.register(
            name="google",
            client_id=s.google_client_id,
            client_secret=s.google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email"},
        )
        _registered = True
    return oauth.google


def current_user(request: Request) -> str:
    s = get_settings()
    email = request.session.get("email")
    if not email or email.lower() != s.allowed_email.lower():
        raise HTTPException(401, "Not signed in")
    return email


@router.get("/me")
def me(user: str = Depends(current_user)):
    return {"email": user}


@router.get("/login")
async def login(request: Request):
    s = get_settings()
    # The login cookie is host-bound: start the flow on the same host Google will redirect back to
    # (BASE_URL), otherwise localhost vs 127.0.0.1 loses the session and the OAuth state check fails.
    if request.url.netloc != urlparse(s.base_url).netloc:
        return RedirectResponse(f"{s.base_url}/auth/login")
    return await _client().authorize_redirect(request, f"{s.base_url}/auth/callback")


@router.get("/callback")
async def callback(request: Request):
    s = get_settings()
    try:
        token = await _client().authorize_access_token(request)
    except OAuthError:
        request.session.clear()
        return RedirectResponse("/?login_error=failed")
    email = (token.get("userinfo") or {}).get("email", "")
    verified = (token.get("userinfo") or {}).get("email_verified", False)
    if not s.allowed_email or email.lower() != s.allowed_email.lower() or not verified:
        request.session.clear()
        return RedirectResponse("/?login_error=not_allowed")
    request.session.clear()  # new session on login (no fixation)
    request.session["email"] = email
    return RedirectResponse("/")


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
