"""GitHub App client: app JWTs, cached installation tokens and the OAuth code exchange.

Bento acts as a GitHub App. The app's private key signs a short-lived JWT, which is exchanged for an
installation token scoped to the repositories the user granted. Tokens are never logged or stored in
the database; they live in process memory until shortly before they expire.
"""

import base64
import time

import httpx
import jwt

from .config import settings

API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "bento"}

_tokens: dict[int, tuple[str, float]] = {}


class GitHubError(Exception):
    pass


def app_configured() -> bool:
    return bool(settings.github_app_id and settings.github_app_private_key)


def oauth_configured() -> bool:
    return bool(settings.github_client_id and settings.github_client_secret)


def app_jwt() -> str:
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": str(settings.github_app_id)}
    return jwt.encode(payload, settings.github_app_private_key, algorithm="RS256")


async def installation_token(installation_id: int, http: httpx.AsyncClient) -> str:
    cached = _tokens.get(installation_id)
    if cached and cached[1] > time.time() + 300:
        return cached[0]
    res = await http.post(
        f"{API}/app/installations/{installation_id}/access_tokens",
        headers=HEADERS | {"Authorization": f"Bearer {app_jwt()}"},
    )
    if res.status_code != 201:
        raise GitHubError(f"GitHub refused an installation token ({res.status_code}); is the Bento app still installed?")
    token = res.json()["token"]
    _tokens[installation_id] = (token, time.time() + 3300)  # GitHub tokens last 60 min
    return token


def git_auth_header(token: str) -> str:
    """HTTP header for git over https; keeps the token out of URLs (and so out of error messages)."""
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return f"Authorization: Basic {basic}"


async def as_installation(installation_id: int, http: httpx.AsyncClient) -> dict:
    return HEADERS | {"Authorization": f"token {await installation_token(installation_id, http)}"}


async def exchange_code(code: str, http: httpx.AsyncClient) -> str:
    res = await http.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={"client_id": settings.github_client_id, "client_secret": settings.github_client_secret, "code": code},
    )
    token = res.json().get("access_token") if res.status_code == 200 else None
    if not token:
        raise GitHubError("GitHub sign-in failed or was cancelled")
    return token


async def user_get(path: str, user_token: str, http: httpx.AsyncClient):
    res = await http.get(f"{API}{path}", headers=HEADERS | {"Authorization": f"Bearer {user_token}"})
    if res.status_code != 200:
        raise GitHubError(f"GitHub API {path} returned {res.status_code}")
    return res.json()
