"""OAuth 2.0 sign-in (Google / GitHub) — the provider abstraction.

Why hand-rolled instead of a library (authlib) or a hosted service (Clerk): the flow we need is
one page of standards-compliant code (authorization-code grant, no refresh tokens, no scopes
beyond email), a library would be the project's heaviest web dependency, and a hosted service
would make local/offline development — a design rule of this repo — impossible. The same
`OAuthProvider` shape accommodates any additional provider as a dict entry, mirroring the
ingestion registry pattern.

Security notes:
- `state` is a short-lived signed JWT (purpose-tagged), so the callback can verify the round-trip
  without server-side session storage — the API stays stateless.
- Providers are enabled purely by configuration: a provider with no client id/secret is invisible
  to `GET /auth/providers` and its routes 404. No keys, no attack surface.
- We only ever request the user's email (plus GitHub's fallback email endpoint); no other scopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode

import requests

from mindbridge.config import settings

# Exchange timeout: OAuth token endpoints answer in well under a second; anything longer is an
# outage and the user should get an error page, not a hung redirect.
_TIMEOUT = 10


@dataclass(frozen=True)
class OAuthProvider:
    """Everything provider-specific for the authorization-code flow."""

    name: str
    authorize_url: str
    token_url: str
    scope: str
    client_id_getter: Callable[[], str]
    client_secret_getter: Callable[[], str]
    # Given a provider access token, return the user's verified email (or None).
    fetch_email: Callable[[str], Optional[str]]

    @property
    def client_id(self) -> str:
        return self.client_id_getter()

    @property
    def client_secret(self) -> str:
        return self.client_secret_getter()

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def redirect_uri(self) -> str:
        # Must exactly match the URI registered with the provider.
        return f"{settings.api_base_url.rstrip('/')}/auth/oauth/{self.name}/callback"

    def build_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri(),
            "response_type": "code",
            "scope": self.scope,
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> Optional[str]:
        """Trade the authorization code for the provider's access token. None on any failure —
        the caller turns that into a clean error redirect (graceful degradation, as everywhere)."""
        try:
            resp = requests.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri(),
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("access_token") or None
        except (requests.RequestException, ValueError):
            return None


def _google_email(access_token: str) -> Optional[str]:
    try:
        resp = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Only trust verified addresses — an unverified email could hijack an existing account.
        if data.get("email") and data.get("email_verified", False):
            return str(data["email"]).strip().lower()
        return None
    except (requests.RequestException, ValueError):
        return None


def _github_email(access_token: str) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        # GitHub's /user "email" is often null (private); /user/emails lists them all.
        resp = requests.get("https://api.github.com/user/emails", headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        emails = resp.json()
        verified = [e for e in emails if e.get("verified")]
        primary = [e for e in verified if e.get("primary")]
        pick = (primary or verified or [{}])[0].get("email")
        return str(pick).strip().lower() if pick else None
    except (requests.RequestException, ValueError):
        return None


PROVIDERS: dict[str, OAuthProvider] = {
    "google": OAuthProvider(
        name="google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scope="openid email",
        client_id_getter=lambda: settings.google_client_id,
        client_secret_getter=lambda: settings.google_client_secret,
        fetch_email=_google_email,
    ),
    "github": OAuthProvider(
        name="github",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scope="read:user user:email",
        client_id_getter=lambda: settings.github_client_id,
        client_secret_getter=lambda: settings.github_client_secret,
        fetch_email=_github_email,
    ),
}


def enabled_providers() -> list[OAuthProvider]:
    return [p for p in PROVIDERS.values() if p.enabled]


def get_provider(name: str) -> Optional[OAuthProvider]:
    """The provider if it exists *and* is configured; None otherwise (route turns this into 404,
    so unconfigured providers are indistinguishable from unknown ones)."""
    provider = PROVIDERS.get(name.lower())
    return provider if provider is not None and provider.enabled else None
