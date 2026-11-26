"""Sign in with GitHub, repository import, webhooks and fix requests, with GitHub mocked."""

import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from bento_core import github
from bento_core.config import settings

pytestmark = pytest.mark.integration

REPOS = [
    {"full_name": "Acme/Shop", "name": "Shop", "private": True, "description": "store", "language": "TypeScript",
     "homepage": "shop.example.com", "html_url": "https://github.com/Acme/Shop", "pushed_at": "2026-01-02T00:00:00Z"},
    {"full_name": "Acme/Docs", "name": "Docs", "private": False, "description": None, "language": None,
     "homepage": "", "html_url": "https://github.com/Acme/Docs", "pushed_at": "2026-01-01T00:00:00Z"},
]


class FakeGitHub:
    """Just enough of github.com and api.github.com for the sign-in and import flows."""

    def __init__(self):
        self.profile = {"id": 4242, "login": "octo", "name": "Octo Cat"}
        self.emails = [{"email": "octo@example.com", "primary": True, "verified": True}]
        self.installations = [{"id": 99, "account": {"id": 7, "login": "Acme", "type": "Organization"}}]
        self.user_repos = REPOS  # what this user can open themselves in installation 99

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "user-token-for-tests"})
        if path == "/user":
            return httpx.Response(200, json=self.profile)
        if path == "/user/emails":
            return httpx.Response(200, json=self.emails)
        if path == "/user/installations":
            return httpx.Response(200, json={"installations": self.installations})
        if path == "/user/installations/99/repositories":
            return httpx.Response(200, json={"repositories": self.user_repos})
        if path == "/installation/repositories":
            return httpx.Response(200, json={"repositories": REPOS})
        return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def fake_github(client, monkeypatch):
    from app.state import state

    fake = FakeGitHub()
    monkeypatch.setattr(settings, "github_app_id", "1")
    monkeypatch.setattr(settings, "github_app_slug", "bento-test")
    monkeypatch.setattr(settings, "github_app_private_key", "placeholder-never-used")  # signing is mocked below
    monkeypatch.setattr(settings, "github_client_id", "client-id-for-tests")
    monkeypatch.setattr(settings, "github_client_secret", "client-value-for-tests")

    async def fake_headers(installation_id, http):
        return github.HEADERS | {"Authorization": f"token installation-{installation_id}"}

    monkeypatch.setattr(github, "as_installation", fake_headers)
    real_http = state.http
    state.http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    yield fake
    client.portal.call(state.http.aclose)
    state.http = real_http


def location(res) -> tuple[str, dict]:
    url = urlsplit(res.headers["location"])
    return url.path, {k: v[0] for k, v in parse_qs(url.query).items()} | ({"#": url.fragment} if url.fragment else {})


def test_providers_reflect_configuration(client, fake_github):
    assert client.get("/api/auth/providers").json() == {"github": True}


def test_github_disabled_without_configuration(client):
    assert client.get("/api/auth/providers").json() == {"github": False}
    assert client.get("/api/auth/github/login", follow_redirects=False).status_code == 503


def test_sign_in_with_github_creates_account_and_links_installations(client, fake_github):
    res = client.get("/api/auth/github/login", follow_redirects=False)
    assert res.status_code == 302
    url = urlsplit(res.headers["location"])
    assert url.netloc == "github.com"
    state = parse_qs(url.query)["state"][0]

    cb = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    path, params = location(cb)
    assert path == "/auth/callback" and params["#"].startswith("token=")
    token = params["#"].removeprefix("token=")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    assert me["email"] == "octo@example.com"

    status = client.get("/api/github/status", headers={"Authorization": f"Bearer {token}"}).json()
    assert status["login"] == "octo" and status["installations"] == [{"id": 99, "account": "Acme", "type": "Organization"}]

    replay = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    path, params = location(replay)
    assert path == "/login" and "already used" in params["error"]


def test_github_sign_in_links_existing_account_by_verified_email(client, fake_github, user):
    headers, me = user("octo@example.com")
    state = parse_qs(urlsplit(client.get("/api/auth/github/login", follow_redirects=False).headers["location"]).query)["state"][0]
    cb = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    token = location(cb)[1]["#"].removeprefix("token=")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["id"] == me["id"]


def test_unverified_email_does_not_take_over_an_account(client, fake_github, user):
    user("octo@example.com")
    fake_github.emails = [{"email": "octo@example.com", "primary": True, "verified": False}]
    state = parse_qs(urlsplit(client.get("/api/auth/github/login", follow_redirects=False).headers["location"]).query)["state"][0]
    cb = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    token = location(cb)[1]["#"].removeprefix("token=")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    assert me["email"] != "octo@example.com"  # a separate account, not the existing one


@pytest.mark.parametrize("params", [{"code": "abc", "state": "forged"}, {"code": "abc"}, {"error": "access_denied"}])
def test_bad_callbacks_go_back_to_login(client, fake_github, params):
    res = client.get("/api/auth/github/callback", params=params, follow_redirects=False)
    path, query = location(res)
    assert res.status_code == 302 and path == "/login" and query["error"]


def _sign_in(client) -> dict:
    state = parse_qs(urlsplit(client.get("/api/auth/github/login", follow_redirects=False).headers["location"]).query)["state"][0]
    cb = client.get("/api/auth/github/callback", params={"code": "abc", "state": state}, follow_redirects=False)
    return {"Authorization": f"Bearer {location(cb)[1]['#'].removeprefix('token=')}"}


def test_collaborator_only_sees_the_repos_they_can_open(client, fake_github):
    # The installation belongs to someone else; this user collaborates on just one of its repos.
    fake_github.installations = [{"id": 99, "account": {"id": 1, "login": "friend", "type": "User"}}]
    fake_github.user_repos = [REPOS[1]]
    headers = _sign_in(client)
    repos = client.get("/api/github/repos", headers=headers).json()["repos"]
    assert [r["fullName"] for r in repos] == ["Acme/Docs"]
    res = client.post("/api/github/import", headers=headers, json={"repos": ["Acme/Shop"]})
    assert res.status_code == 404


def test_own_installation_shows_every_repo(client, fake_github):
    fake_github.installations = [{"id": 99, "account": {"id": 4242, "login": "octo", "type": "User"}}]
    fake_github.user_repos = []  # never asked: the whole installation is theirs
    headers = _sign_in(client)
    assert len(client.get("/api/github/repos", headers=headers).json()["repos"]) == 2


def test_installing_from_github_without_our_state_signs_in(client, fake_github):
    cb = client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "installation_id": "99", "setup_action": "install"},
        follow_redirects=False,
    )
    path, params = location(cb)
    assert path == "/auth/callback" and params["#"].startswith("token=")


def test_list_and_import_repositories(client, fake_github, user, db):
    headers, me = user()

    async def link(state):
        from uuid import UUID
        await state.pg.execute(
            "INSERT INTO github_installations (id, owner_id, account_login, own) VALUES (99, $1, 'Acme', true)", UUID(me["id"])
        )

    db(link)
    repos = client.get("/api/github/repos", headers=headers).json()["repos"]
    assert [r["fullName"] for r in repos] == ["Acme/Shop", "Acme/Docs"] and repos[0]["projectId"] is None

    res = client.post("/api/github/import", headers=headers, json={"repos": ["acme/shop", "Acme/Shop"]})
    assert res.status_code == 201
    (project,) = res.json()["projects"]
    detail = client.get(f"/api/projects/{project['id']}", headers=headers).json()
    assert detail["project"]["repoUrl"] == "https://github.com/Acme/Shop"
    assert [e["url"] for e in detail["endpoints"]] == ["https://shop.example.com"]  # the repo's Website, monitored

    async def imported(state):
        return await state.pg.fetchval("SELECT installation_id FROM projects WHERE id = $1::uuid", project["id"])

    assert db(imported) == 99
    assert client.post("/api/github/import", headers=headers, json={"repos": ["acme/shop"]}).json()["projects"] == []
    assert client.get("/api/github/repos", headers=headers).json()["repos"][0]["projectId"] == project["id"]
    assert client.post("/api/github/import", headers=headers, json={"repos": ["someone/else"]}).status_code == 404


# ---------- webhooks ----------

def signed(client, event: str, payload: dict, key: str | None = None):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new((key or settings.github_webhook_secret).encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/github", content=body,
                       headers={"X-GitHub-Event": event, "X-Hub-Signature-256": sig, "Content-Type": "application/json"})


def test_push_webhook_queues_scans(client, user, db):
    headers, _ = user()
    client.post("/api/projects", headers=headers, json={"name": "Shop", "repo_url": "https://github.com/acme/shop"})
    push = {"repository": {"full_name": "Acme/Shop"}, "after": "a" * 40}
    res = signed(client, "push", push)
    assert res.status_code == 202 and res.json()["queued"] == 1

    async def last_job(state):
        _, fields = (await state.redis.xrevrange("scan.jobs", count=1))[0]
        return json.loads(fields["data"])

    assert db(last_job)["sha"] == "a" * 40
    assert signed(client, "push", {**push, "after": "0" * 40}).json()["ignored"] == "no commit"  # branch deleted
    assert signed(client, "ping", {}).json()["pong"] is True


def test_webhook_rejects_bad_signatures(client):
    assert signed(client, "push", {"after": "a"}, key="the-wrong-key-entirely-000000000000").status_code == 401
    unsigned = client.post("/api/webhooks/github", content=b"{}", headers={"X-GitHub-Event": "push"})
    assert unsigned.status_code == 401


def test_pull_request_webhook_tracks_fix_prs(client, user, db):
    headers, _ = user()
    p = client.post("/api/projects", headers=headers, json={"name": "Shop", "repo_url": "https://github.com/acme/shop"}).json()["project"]

    async def add_fix(state):
        await state.pg.execute(
            "INSERT INTO fix_prs (project_id, finding_key, status, branch, pr_number) VALUES ($1::uuid, 'no-ci', 'open', 'bento/fix-no-ci', 7)",
            p["id"],
        )

    async def fix_status(state):
        return await state.pg.fetchval("SELECT status FROM fix_prs WHERE project_id = $1::uuid", p["id"])

    db(add_fix)
    other = {"action": "closed", "repository": {"full_name": "Acme/Shop"},
             "pull_request": {"number": 7, "merged": True, "head": {"ref": "feature/not-bento"}}}
    assert signed(client, "pull_request", other).json()["ignored"] == "pull_request"
    assert db(fix_status) == "open"
    merged = {**other, "pull_request": {**other["pull_request"], "head": {"ref": "bento/fix-no-ci"}}}
    assert signed(client, "pull_request", merged).json()["status"] == "merged"
    assert db(fix_status) == "merged"


# ---------- fix requests ----------

def test_fix_requests(client, user, db):
    headers, _ = user()
    p = client.post("/api/projects", headers=headers, json={"name": "Shop", "repo_url": "https://github.com/acme/shop"}).json()["project"]

    async def seed(state, installation):
        await state.pg.execute("UPDATE projects SET installation_id = $2 WHERE id = $1::uuid", p["id"], installation)
        await state.pg.execute(
            """INSERT INTO findings (project_id, key, severity, title) VALUES ($1::uuid, 'no-ci', 'low', 'No CI'),
                                                                            ($1::uuid, 'no-tests', 'medium', 'No tests')
               ON CONFLICT DO NOTHING""",
            p["id"],
        )

    db(seed, None)
    findings = {f["technical"]["title"]: f for f in client.get(f"/api/projects/{p['id']}", headers=headers).json()["findings"]}
    assert findings["No CI"]["fixable"] is False  # not imported through the app
    assert client.post(f"/api/projects/{p['id']}/findings/{findings['No CI']['id']}/fix", headers=headers).status_code == 422

    db(seed, 99)
    findings = {f["technical"]["title"]: f for f in client.get(f"/api/projects/{p['id']}", headers=headers).json()["findings"]}
    assert findings["No CI"]["fixable"] is True and findings["No tests"]["fixable"] is False
    url = f"/api/projects/{p['id']}/findings/{findings['No CI']['id']}/fix"
    assert client.post(url, headers=headers).status_code == 202
    assert client.post(url, headers=headers).status_code == 409  # one PR per finding
    after = {f["technical"]["title"]: f for f in client.get(f"/api/projects/{p['id']}", headers=headers).json()["findings"]}
    assert after["No CI"]["fix"]["status"] == "queued"
    assert client.post(f"/api/projects/{p['id']}/findings/{findings['No tests']['id']}/fix", headers=headers).status_code == 422

    async def fix_jobs(state):
        return await state.redis.xlen("fix.jobs")

    assert db(fix_jobs) == 1


# ---------- PR checks ----------

def pr_event(action="opened", repo="Acme/Shop", head="h" * 40, inst=99):
    return {"action": action, "installation": {"id": inst}, "repository": {"full_name": repo},
            "pull_request": {"number": 12, "head": {"sha": head, "ref": "feature/x"}, "base": {"sha": "b" * 40, "ref": "main"}}}


def test_pull_request_webhook_queues_one_check_per_commit(client, user, db):
    headers, _ = user()
    p = client.post("/api/projects", headers=headers, json={"name": "Shop", "repo_url": "https://github.com/acme/shop"}).json()["project"]

    assert signed(client, "pull_request", pr_event()).json()["ignored"] == "repository not imported in Bento"

    async def link(state):
        await state.pg.execute("UPDATE projects SET installation_id = 99 WHERE id = $1::uuid", p["id"])

    async def pr_jobs(state):
        return [json.loads(f["data"]) for _, f in await state.redis.xrange("scan.jobs") if '"pr"' in f["data"]]

    db(link)
    assert signed(client, "pull_request", pr_event()).json()["queued"] == "pr-check"
    assert signed(client, "pull_request", pr_event()).json()["ignored"] == "already checking this commit"
    assert signed(client, "pull_request", pr_event("synchronize", head="c" * 40)).json()["queued"] == "pr-check"
    assert signed(client, "pull_request", pr_event("labeled", head="d" * 40)).json()["ignored"] == "pull_request"
    jobs = db(pr_jobs)
    assert [(j["head_sha"][0], j["base_sha"][0], j["installation_id"], j["repo"]) for j in jobs] == [
        ("h", "b", 99, "acme/shop"), ("c", "b", 99, "acme/shop")]
