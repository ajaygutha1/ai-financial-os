from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.exceptions import UnauthorizedError, ValidationError
from app.core.oauth import SUPPORTED_PROVIDERS, oauth
from app.core.security import REFRESH_COOKIE_NAME, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        max_age=int(timedelta(days=settings.refresh_token_ttl_days).total_seconds()),
        path="/",
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    service = AuthService(db)
    user = service.register(
        email=payload.email, password=payload.password, full_name=payload.full_name
    )
    access_token, refresh_token = service.issue_tokens(user.id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, response: Response, db: Session = Depends(get_db)
) -> TokenResponse:
    service = AuthService(db)
    user = service.authenticate(email=payload.email, password=payload.password)
    access_token, refresh_token = service.issue_tokens(user.id)
    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> None:
    # True server-side revocation, not just clearing the cookie -- a copy of
    # this token (another device, a thief) can never be exchanged again.
    if refresh_token is not None:
        AuthService(db).revoke_refresh_token(refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> TokenResponse:
    if refresh_token is None:
        raise UnauthorizedError("Missing refresh token.")

    service = AuthService(db)
    new_access_token, new_refresh_token = service.rotate_refresh_token(refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
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
    _set_refresh_cookie(redirect_response, refresh_token)
    return redirect_response
