"""Connect GitHub: "Sign in with GitHub", linking app installations, and importing repositories.

Flow
  login    browser -> GET /api/auth/github/login -> github.com/login/oauth/authorize
  connect  dashboard -> POST /api/github/connect -> github.com/apps/<slug>/installations/new
  both     GitHub -> GET /api/auth/github/callback?code&state[&installation_id]
           -> we exchange the code for a user token, read the user's profile and the app installations
              they can access, link them to their Bento account, then redirect back to the frontend.

The user token is used only inside the callback and is never stored. Repositories are listed and cloned
later with short-lived installation tokens (see bento_core.github).
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from bento_core import github, streams
from bento_core.config import settings
from bento_core.net import probe_target_error

from ..security import JWT_SECRET, current_user_id, issue_token
from ..state import state
from .projects import _queue_scan, project_json

log = logging.getLogger(__name__)
router = APIRouter(tags=["github"])

STATE_TTL = timedelta(minutes=10)
STATE_TYPE = "oauth-state"  # session tokens share the signing key; this keeps the two from being swapped


# ---------- helpers ----------


def _require_github() -> None:
    if not (github.app_configured() and github.oauth_configured() and settings.github_app_slug):
        raise HTTPException(503, "GitHub isn't connected on this Bento server yet (GITHUB_APP_* settings are missing)")


async def _make_state(intent: str, user_id: UUID | None = None) -> str:
    nonce = secrets.token_urlsafe(16)
    await state.redis.set(f"oauth-state:{nonce}", "1", ex=int(STATE_TTL.total_seconds()))
    payload = {"typ": STATE_TYPE, "n": nonce, "i": intent, "exp": datetime.now(timezone.utc) + STATE_TTL}
    if user_id:
        payload["u"] = str(user_id)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def _read_state(raw: str | None) -> dict:
    """Verify the signed state and burn its nonce, so a callback URL can't be replayed."""
    try:
        payload = jwt.decode(raw or "", JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(400, "This sign-in link has expired. Please try again.") from None
    if payload.get("typ") != STATE_TYPE or not isinstance(payload.get("n"), str):
        raise HTTPException(400, "This sign-in link isn't valid. Please try again.")
    if not await state.redis.delete(f"oauth-state:{payload['n']}"):
        raise HTTPException(400, "This sign-in link was already used. Please try again.")
    return payload


def _back(path: str, **params: str) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"{settings.public_url}{path}{query}", status_code=302)


async def _sync_installations(user_id: UUID, user_token: str, github_id: int) -> int:
    """Record the Bento app installations this GitHub user can use, and what they may see in each.

    GitHub also lists installations on other people's accounts when this user collaborates on one of their
    repos. Those must not expose the owner's other repos, so for them we keep only the repos this user can
    open themselves (asked with the user's own token).
    """
    data = await github.user_get("/user/installations?per_page=100", user_token, state.http)
    found = []
    for inst in data.get("installations", []):
        own = inst["account"].get("id") == github_id
        repos: list[str] = []
        if not own:
            try:
                for page in range(1, 11):
                    res = await github.user_get(
                        f"/user/installations/{inst['id']}/repositories?per_page=100&page={page}", user_token, state.http
                    )
                    batch = res.get("repositories", [])
                    repos += [r["full_name"].lower() for r in batch]
                    if len(batch) < 100:
                        break
            except github.GitHubError as exc:
                log.warning("installation %s: can't list this user's repos: %s", inst["id"], exc)
                continue
            if not repos:
                continue
        found.append((inst, own, repos))
    async with state.pg.acquire() as conn, conn.transaction():
        await conn.execute("DELETE FROM github_installations WHERE owner_id = $1", user_id)
        for inst, own, repos in found:
            await conn.execute(
                """INSERT INTO github_installations (id, owner_id, account_login, account_type, own, repos)
                   VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING""",
                inst["id"], user_id, inst["account"]["login"], inst["account"].get("type"), own, repos,
            )
    return len(found)


async def _user_for_login(profile: dict, emails: list[dict]) -> tuple[UUID, str]:
    """Find the Bento account for this GitHub user, linking by verified email or creating one."""
    gh_id, login = profile["id"], profile["login"]
    row = await state.pg.fetchrow("SELECT id, email FROM users WHERE github_id = $1", gh_id)
    if row:
        await state.pg.execute("UPDATE users SET github_login = $2 WHERE id = $1", row["id"], login)
        return row["id"], row["email"]

    verified = [e["email"].lower() for e in emails if e.get("verified")]
    primary = next((e["email"].lower() for e in emails if e.get("primary") and e.get("verified")), None)
    if verified:
        row = await state.pg.fetchrow(
            "UPDATE users SET github_id = $2, github_login = $3 WHERE email = ANY($1::text[]) AND github_id IS NULL "
            "RETURNING id, email",
            verified, gh_id, login,
        )
        if row:
            return row["id"], row["email"]

    email = primary or (verified[0] if verified else f"{gh_id}+{login}@users.noreply.github.com")
    row = await state.pg.fetchrow(
        """INSERT INTO users (email, name, github_id, github_login) VALUES ($1, $2, $3, $4)
           ON CONFLICT (email) DO NOTHING RETURNING id, email""",
        email, profile.get("name") or login, gh_id, login,
    )
    if row is None:
        raise HTTPException(409, "A Bento account with this email already exists and is linked to another GitHub user")
    return row["id"], row["email"]


async def _installation_repos(user_id: UUID) -> list[dict]:
    installs = await state.pg.fetch(
        "SELECT id, account_login, own, repos FROM github_installations WHERE owner_id = $1 ORDER BY account_login",
        user_id,
    )
    repos: list[dict] = []
    for inst in installs:
        try:
            headers = await github.as_installation(inst["id"], state.http)
        except github.GitHubError as exc:
            log.warning("installation %s unusable: %s", inst["id"], exc)
            continue
        page = 1
        while page <= 10:  # up to 1000 repos per installation
            res = await state.http.get(
                f"{github.API}/installation/repositories", headers=headers, params={"per_page": 100, "page": page}
            )
            if res.status_code != 200:
                break
            batch = res.json().get("repositories", [])
            for r in batch:
                if not inst["own"] and r["full_name"].lower() not in inst["repos"]:
                    continue  # someone else's repo this user can't open themselves
                repos.append({
                    "installationId": inst["id"],
                    "fullName": r["full_name"],
                    "name": r["name"],
                    "private": r["private"],
                    "description": r.get("description"),
                    "language": r.get("language"),
                    "homepage": r.get("homepage") or None,
                    "url": r["html_url"],
                    "pushedAt": r.get("pushed_at"),
                    "archived": r.get("archived", False),
                })
            if len(batch) < 100:
                break
            page += 1
    repos.sort(key=lambda r: r["pushedAt"] or "", reverse=True)
    return repos


# ---------- sign in ----------


@router.get("/api/auth/providers")
async def providers():
    return {"github": github.app_configured() and github.oauth_configured() and bool(settings.github_app_slug)}


@router.get("/api/auth/github/login")
async def github_login():
    _require_github()
    query = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.public_url}/api/auth/github/callback",
        "state": await _make_state("login"),
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}", status_code=302)


@router.get("/api/auth/github/callback", include_in_schema=False)
async def github_callback(request: Request):
    q = request.query_params  # read directly: "state" would clash with our module-level `state`
    if q.get("error"):
        return _back("/login", error="GitHub sign-in was cancelled.")
    _require_github()
    if not q.get("state") and q.get("setup_action") and q.get("code"):
        # Installed (or its repo access changed) straight from GitHub's app page: GitHub calls back with
        # an authorization code but no state of ours. The code itself proves who the user is: sign them in.
        st: dict = {"i": "login"}
    else:
        try:
            st = await _read_state(q.get("state"))
        except HTTPException as exc:
            return _back("/login", error=exc.detail)
    if not q.get("code"):
        # App installed without the OAuth step: ask GitHub to authorize, which brings us back with a code.
        return _back("/dashboard", github="installed")

    try:
        user_token = await github.exchange_code(q["code"], state.http)
        profile = await github.user_get("/user", user_token, state.http)
        try:
            emails = await github.user_get("/user/emails", user_token, state.http)
        except github.GitHubError:
            emails = []
    except github.GitHubError as exc:
        return _back("/login", error=str(exc))

    if st.get("u"):  # connecting from a signed-in session
        user_id = UUID(st["u"])
        owner = await state.pg.fetchval("SELECT id FROM users WHERE github_id = $1", profile["id"])
        if owner and owner != user_id:
            return _back("/dashboard", github="error", message="That GitHub account is linked to another Bento user.")
        await state.pg.execute(
            "UPDATE users SET github_id = $2, github_login = $3 WHERE id = $1", user_id, profile["id"], profile["login"]
        )
        count = await _sync_installations(user_id, user_token, profile["id"])
        log.info("user %s linked github %s (%d installations)", user_id, profile["login"], count)
        return _back("/dashboard", github="connected")

    try:
        user_id, email = await _user_for_login(profile, emails)
    except HTTPException as exc:
        return _back("/login", error=exc.detail)
    await _sync_installations(user_id, user_token, profile["id"])
    # The token travels in the URL fragment, which browsers never send to a server.
    return RedirectResponse(f"{settings.public_url}/auth/callback#token={issue_token(user_id, email)}", status_code=302)


# ---------- connect + import ----------


@router.get("/api/github/status")
async def github_status(user_id: UUID = Depends(current_user_id)):
    user = await state.pg.fetchrow("SELECT github_login FROM users WHERE id = $1", user_id)
    installs = await state.pg.fetch(
        "SELECT id, account_login, account_type FROM github_installations WHERE owner_id = $1 ORDER BY account_login",
        user_id,
    )
    return {
        "configured": (await providers())["github"],
        "login": user["github_login"] if user else None,
        "installations": [{"id": i["id"], "account": i["account_login"], "type": i["account_type"]} for i in installs],
    }


@router.post("/api/github/connect")
async def github_connect(user_id: UUID = Depends(current_user_id)):
    """URLs the dashboard sends the browser to: install/configure the app, or just re-sync access."""
    _require_github()
    install = f"https://github.com/apps/{settings.github_app_slug}/installations/new?" + urlencode(
        {"state": await _make_state("connect", user_id)}
    )
    authorize = "https://github.com/login/oauth/authorize?" + urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.public_url}/api/auth/github/callback",
        "state": await _make_state("connect", user_id),
    })
    return {"installUrl": install, "authorizeUrl": authorize}


@router.get("/api/github/repos")
async def github_repos(user_id: UUID = Depends(current_user_id)):
    _require_github()
    repos = await _installation_repos(user_id)
    added = {
        r["repo_full_name"]: str(r["id"])
        for r in await state.pg.fetch("SELECT id, repo_full_name FROM projects WHERE owner_id = $1", user_id)
        if r["repo_full_name"]
    }
    for r in repos:
        r["projectId"] = added.get(r["fullName"].lower())
    return {"repos": repos}


class ImportBody(BaseModel):
    repos: list[str] = Field(min_length=1, max_length=50)


@router.post("/api/github/import", status_code=201)
async def github_import(body: ImportBody, user_id: UUID = Depends(current_user_id)):
    _require_github()
    available = {r["fullName"].lower(): r for r in await _installation_repos(user_id)}
    existing = {
        r["repo_full_name"]
        for r in await state.pg.fetch("SELECT repo_full_name FROM projects WHERE owner_id = $1", user_id)
    }
    created = []
    for full in dict.fromkeys(name.lower() for name in body.repos):
        repo = available.get(full)
        if repo is None:
            raise HTTPException(404, f"Bento can't access {full}. Grant the Bento app access to it on GitHub first.")
        if full in existing:
            continue
        homepage = repo["homepage"]
        if homepage and not homepage.startswith(("http://", "https://")):
            homepage = f"https://{homepage}"
        async with state.pg.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """INSERT INTO projects (owner_id, name, repo_url, repo_full_name, installation_id)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                user_id, repo["name"], f"https://github.com/{repo['fullName']}", full, repo["installationId"],
            )
            # The repo's "Website" field on GitHub is usually its live deployment: monitor it straight away.
            if homepage and probe_target_error(homepage) is None:
                await conn.execute(
                    "INSERT INTO endpoints (project_id, url, interval_s) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    row["id"], homepage, settings.default_probe_interval,
                )
        await _queue_scan(row["id"], "github-import")
        await streams.publish(state.redis, streams.ADVICE_REQUESTS, {"project_id": str(row["id"])})
        created.append(project_json(row))
    return {"projects": created}
