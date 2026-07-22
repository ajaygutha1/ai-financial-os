from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.oauth import SUPPORTED_PROVIDERS, oauth
from app.core.rate_limit import rate_limit
from app.core.security import (
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    generate_csrf_token,
    get_current_user,
    verify_csrf,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# Tighter than the global default (app/main.py) -- these are exactly the
# endpoints brute-force/credential-stuffing targets, so they get their own,
# much smaller per-IP budget rather than sharing the generic one.
_login_rate_limit = rate_limit(scope="login", times=10, seconds=60)
_register_rate_limit = rate_limit(scope="register", times=5, seconds=60)
_refresh_rate_limit = rate_limit(scope="refresh", times=30, seconds=60)


def _set_auth_cookies(response: Response, refresh_token: str) -> None:
    max_age = int(timedelta(days=settings.refresh_token_ttl_days).total_seconds())
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    # Not httponly -- the frontend reads this and echoes it back as the
    # X-CSRF-Token header on /refresh and /logout (see verify_csrf).
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        httponly=False,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=max_age,
        path="/",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_register_rate_limit)],
)
def register(
    payload: RegisterRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    service = AuthService(db)
    user = service.register(
        email=payload.email, password=payload.password, full_name=payload.full_name
    )
    access_token, refresh_token = service.issue_tokens(user.id)
    _set_auth_cookies(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post(
    "/login", response_model=TokenResponse, dependencies=[Depends(_login_rate_limit)]
)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    service = AuthService(db)
    user = service.authenticate(email=payload.email, password=payload.password)
    access_token, refresh_token = service.issue_tokens(user.id)
    _set_auth_cookies(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> None:
    # CSRF is only checked when there's actually a session to revoke -- an
    # already-logged-out client just gets its (already absent) cookies
    # cleared, no state change to protect.
    if refresh_token is not None:
        verify_csrf(request)
        # True server-side revocation, not just clearing the cookie -- a
        # copy of this token (another device, a thief) can never be
        # exchanged again.
        AuthService(db).revoke_refresh_token(refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(_refresh_rate_limit)],
)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> TokenResponse:
    if refresh_token is None:
        raise UnauthorizedError("Missing refresh token.")
    # Checked only once we know there's a real cookie-based session in play,
    # so a fully logged-out client still gets a clean 401 rather than a
    # confusing 403.
    verify_csrf(request)

    service = AuthService(db)
    new_access_token, new_refresh_token = service.rotate_refresh_token(refresh_token)
    _set_auth_cookies(response, new_refresh_token)
    return TokenResponse(access_token=new_access_token)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/oauth/{provider}")
async def oauth_login(provider: str, request: Request) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(f"Unsupported OAuth provider: {provider}")

    client = oauth.create_client(provider)
    redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/{provider}/callback"
    result: RedirectResponse = await client.authorize_redirect(request, redirect_uri)
    return result


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(f"Unsupported OAuth provider: {provider}")

    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)

    if provider == "google":
        profile = token.get("userinfo") or await client.userinfo(token=token)
        provider_account_id = profile["sub"]
        email = profile["email"]
        full_name = profile.get("name")
    else:
        profile = (await client.get("user", token=token)).json()
        provider_account_id = str(profile["id"])
        email = profile.get("email")
        full_name = profile.get("name") or profile.get("login")
        if not email:
            emails = (await client.get("user/emails", token=token)).json()
            primary = next((e for e in emails if e.get("primary")), emails[0] if emails else None)
            email = primary["email"] if primary else None

    if not email:
        raise ValidationError("OAuth provider did not return an email address.")

    service = AuthService(db)
    user = service.handle_oauth_login(
        provider=provider,
        provider_account_id=provider_account_id,
        email=email,
        full_name=full_name,
    )
    _, refresh_token = service.issue_tokens(user.id)

    redirect_response = RedirectResponse(url=f"{settings.web_base_url}/callback/{provider}")
    _set_auth_cookies(redirect_response, refresh_token)
    return redirect_response
