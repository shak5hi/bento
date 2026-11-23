"""Webhook HMAC verification, OAuth state handling and the GitHub client (GitHub mocked with httpx.MockTransport)."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi import HTTPException

from app.routes import github as gh_routes
from app.routes import webhooks
from app.security import JWT_SECRET, issue_token
from bento_core import github
from bento_core.config import settings


def sign(body: bytes, key: str | None = None) -> str:
    key = key or settings.github_webhook_secret
    return "sha256=" + hmac.new(key.encode(), body, hashlib.sha256).hexdigest()


# ---------- webhook HMAC ----------

def test_valid_signature():
    body = b'{"zen": "Keep it logically awesome."}'
    assert webhooks._valid_signature(body, sign(body))


@pytest.mark.parametrize(
    "header",
    [None, "", "sha1=abc", "sha256=", "sha256=deadbeef", sign(b"other body"), sign(b'{"zen": 1}', key="wrong-key")],
)
def test_invalid_signatures(header):
    assert not webhooks._valid_signature(b'{"zen": 1}', header)


def test_signature_is_over_exact_bytes():
    body = b'{"a": 1}'
    assert not webhooks._valid_signature(b'{"a":1}', sign(body))


# ---------- OAuth state ----------

class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value, ex=None):
        self.data[key] = value

    async def delete(self, key):
        return 1 if self.data.pop(key, None) is not None else 0


@pytest.fixture
def fake_redis(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(gh_routes.state, "redis", r, raising=False)
    return r


async def test_state_round_trip_burns_the_nonce(fake_redis):
    user = uuid4()
    raw = await gh_routes._make_state("connect", user)
    payload = await gh_routes._read_state(raw)
    assert payload["i"] == "connect" and payload["u"] == str(user)
    with pytest.raises(HTTPException, match="already used"):
        await gh_routes._read_state(raw)  # replay


async def test_login_state_has_no_user(fake_redis):
    payload = await gh_routes._read_state(await gh_routes._make_state("login"))
    assert "u" not in payload


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "not-a-jwt",
        jwt.encode({"n": "x", "i": "login", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "another-key-that-is-long-enough-for-hs256", algorithm="HS256"),
        jwt.encode({"n": "x", "i": "login", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, JWT_SECRET, algorithm="HS256"),
    ],
)
async def test_bad_or_expired_state_is_rejected(fake_redis, raw):
    with pytest.raises(HTTPException) as exc:
        await gh_routes._read_state(raw)
    assert exc.value.status_code == 400


async def test_unknown_nonce_is_rejected(fake_redis):
    raw = jwt.encode({"typ": gh_routes.STATE_TYPE, "n": "never-issued", "i": "login", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                     JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException, match="already used"):
        await gh_routes._read_state(raw)


async def test_session_token_is_not_accepted_as_state(fake_redis):
    """A login JWT is signed with the same key; it must be refused cleanly, not crash."""
    with pytest.raises(HTTPException) as exc:
        await gh_routes._read_state(issue_token(uuid4(), "someone@example.com"))
    assert exc.value.status_code == 400


async def test_state_token_is_not_a_session_token(fake_redis):
    from fastapi.security import HTTPAuthorizationCredentials

    from app.security import current_user_id

    raw = await gh_routes._make_state("connect", uuid4())
    with pytest.raises(HTTPException) as exc:
        await current_user_id(HTTPAuthorizationCredentials(scheme="Bearer", credentials=raw))
    assert exc.value.status_code == 401


# ---------- GitHub client ----------

async def test_exchange_code_and_user_get():
    def handler(request: httpx.Request):
        if request.url.path == "/login/oauth/access_token":
            assert b"code=abc" in request.content
            return httpx.Response(200, json={"access_token": "user-token-for-tests"})
        if request.url.path == "/user":
            assert request.headers["Authorization"] == "Bearer user-token-for-tests"
            return httpx.Response(200, json={"id": 1, "login": "octo"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        token = await github.exchange_code("abc", http)
        assert (await github.user_get("/user", token, http))["login"] == "octo"


@pytest.mark.parametrize("response", [httpx.Response(200, json={"error": "bad_verification_code"}), httpx.Response(500)])
async def test_failed_code_exchange(response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as http:
        with pytest.raises(github.GitHubError):
            await github.exchange_code("abc", http)


async def test_user_get_error():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401))) as http:
        with pytest.raises(github.GitHubError, match="401"):
            await github.user_get("/user", "t", http)


def test_git_auth_header_keeps_token_out_of_urls():
    header = github.git_auth_header("tok")
    assert header.startswith("Authorization: Basic ") and "tok" not in header


@pytest.mark.parametrize(
    ("key", "fixable"),
    [("no-ci", True), ("no-readme", True), ("secrets-env-file", True), ("vuln:npm:lodash", True),
     ("vuln:PyPI:requests", True), ("no-tests", False), ("secret:github-token:a.py", False), ("vuln:Go:x", False)],
)
def test_fixable_findings(key, fixable):
    assert github.fixable_finding(key) is fixable
