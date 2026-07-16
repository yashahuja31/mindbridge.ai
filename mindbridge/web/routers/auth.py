"""Authentication routes.

Two ways in, one token out — both paths end in the same HS256 JWT, so everything downstream
(`get_current_user`, history, profiles) is auth-method-agnostic:

* Password: `POST /auth/register`, `POST /auth/login` (OAuth2 password grant, form-encoded).
* OAuth (Google/GitHub): browser hits `GET /auth/oauth/{provider}/start`, provider redirects to
  `GET /auth/oauth/{provider}/callback`, and we bounce the browser back to the SPA with the token
  in the URL fragment (`#token=...` — fragments never reach servers or logs).

`GET /auth/providers` tells the client which OAuth buttons to render; a provider appears only when
its client id + secret are configured, so a keyless dev setup degrades to password-only.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from mindbridge.config import settings
from mindbridge.web.db import get_db
from mindbridge.web.dto import ProviderOut, RegisterRequest, Token, UserOut
from mindbridge.web.models import User
from mindbridge.web.oauth import enabled_providers, get_provider
from mindbridge.web.security import (
    create_access_token,
    create_state_token,
    get_current_user,
    hash_password,
    verify_password,
    verify_state_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> Token:
    """Create an account and return an access token so the client is logged in immediately."""
    if db.query(User).filter(User.email == body.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password), role=body.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    """OAuth2 password grant: `username` is the email. Returns a bearer token on success."""
    email = (form.username or "").strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is not None and user.hashed_password is None:
        # OAuth-created account with no local password; a clear message beats a generic 401.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This account signs in with {user.auth_provider.title()} — use that button",
        )
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    """Return the signed-in user — a quick way for a client to validate its token."""
    return user


# ---- OAuth (Google / GitHub) -------------------------------------------------------------------


@router.get("/providers", response_model=list[ProviderOut])
def providers() -> list[ProviderOut]:
    """Which OAuth providers are configured — the SPA renders one button per entry."""
    return [ProviderOut(name=p.name) for p in enabled_providers()]


@router.get("/oauth/{provider_name}/start")
def oauth_start(provider_name: str, role: str = "hiree") -> RedirectResponse:
    """Kick off the flow: redirect the browser to the provider's consent screen. `role` (for
    first-time sign-ups) rides along inside the signed `state` token."""
    provider = get_provider(provider_name)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider_name}' is not configured",
        )
    if role not in ("hiree", "hirer"):
        role = "hiree"
    state = create_state_token(provider.name, role=role)
    return RedirectResponse(provider.build_authorize_url(state))


def _frontend_redirect(fragment_params: dict[str, str]) -> RedirectResponse:
    """Send the browser back to the SPA with the outcome in the URL *fragment* — fragments are
    never sent to servers, so the token can't leak into access logs or referrers."""
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/login#{urlencode(fragment_params)}")


@router.get("/oauth/{provider_name}/callback")
def oauth_callback(
    provider_name: str,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The provider redirects here after consent. Every failure path lands the user back on the
    SPA's login page with a readable `#error=...` instead of a bare JSON error."""
    provider = get_provider(provider_name)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider_name}' is not configured",
        )
    if error:  # user hit "cancel" on the consent screen
        return _frontend_redirect({"error": "Sign-in was cancelled"})

    role = verify_state_token(state, provider.name)
    if role is None:
        return _frontend_redirect({"error": "Sign-in expired or was tampered with — try again"})

    access_token = provider.exchange_code(code) if code else None
    if access_token is None:
        return _frontend_redirect({"error": f"Could not complete {provider.name.title()} sign-in"})

    email = provider.fetch_email(access_token)
    if not email:
        return _frontend_redirect(
            {"error": f"{provider.name.title()} did not share a verified email"}
        )

    # Find-or-create by email. An existing password account just logs in — same person, same
    # inbox — but keeps its password and original auth_provider label.
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, hashed_password=None, auth_provider=provider.name, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)

    return _frontend_redirect({"token": create_access_token(user.id)})
