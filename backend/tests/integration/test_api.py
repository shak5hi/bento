"""Accounts, projects, dashboard, public status page and badge, against real databases."""

import json
import re
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


# ---------- accounts ----------

def test_register_login_me(client, user):
    headers, me = user("Alice@Example.com")
    assert me["email"] == "alice@example.com"  # normalised
    assert client.get("/api/auth/me", headers=headers).json()["user"]["id"] == me["id"]

    ok = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct-horse-9"})
    assert ok.status_code == 200 and ok.json()["token"]
    bad = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong-password"})
    assert bad.status_code == 401
    nobody = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-1"})
    assert nobody.status_code == 401 and nobody.json()["detail"] == bad.json()["detail"]  # no account enumeration


def test_register_validation_and_duplicates(client, user):
    user("bob@example.com")
    assert client.post("/api/auth/register", json={"email": "BOB@example.com", "password": "another-pass-1"}).status_code == 409
    short = client.post("/api/auth/register", json={"email": "c@example.com", "password": "short"})
    assert short.status_code == 422 and short.json()["errors"][0]["field"] == "password"
    assert client.post("/api/auth/register", json={"email": "not-an-email", "password": "long-enough-1"}).status_code == 422


@pytest.mark.parametrize("auth", [None, "Bearer nonsense", "Basic abc"])
def test_protected_routes_need_a_valid_token(client, auth):
    headers = {"Authorization": auth} if auth else {}
    for path in ("/api/auth/me", "/api/dashboard", "/api/projects"):
        assert client.get(path, headers=headers).status_code == 401


def test_login_is_rate_limited(client):
    codes = [client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope-nope"}).status_code for _ in range(21)]
    assert codes[:20] == [401] * 20 and codes[20] == 429


# ---------- projects ----------

def create(client, headers, **body):
    res = client.post("/api/projects", headers=headers, json={"name": "Shop", **body})
    assert res.status_code == 201, res.text
    return res.json()["project"]


def test_project_crud(client, user, db):
    headers, _ = user()
    p = create(client, headers, repo_url="https://github.com/Acme/Shop/", endpoints=["https://shop.example.com/health"])
    assert p["repoUrl"] == "https://github.com/Acme/Shop" and p["status"] == "unknown" and p["isPublic"] is False

    listed = client.get("/api/projects", headers=headers).json()["projects"]
    assert [x["id"] for x in listed] == [p["id"]]

    detail = client.get(f"/api/projects/{p['id']}", headers=headers).json()
    assert [e["url"] for e in detail["endpoints"]] == ["https://shop.example.com/health"]
    assert detail["endpoints"][0]["state"] == "pending"

    renamed = client.patch(f"/api/projects/{p['id']}", headers=headers, json={"name": "  Storefront "}).json()["project"]
    assert renamed["name"] == "Storefront" and renamed["repoUrl"] == p["repoUrl"]

    dup = client.post(f"/api/projects/{p['id']}/endpoints", headers=headers, json={"url": "https://shop.example.com/health"})
    assert dup.status_code == 409
    ep = client.post(f"/api/projects/{p['id']}/endpoints", headers=headers, json={"url": "https://api.example.com"}).json()["endpoint"]
    assert client.delete(f"/api/endpoints/{ep['id']}", headers=headers).status_code == 204
    assert client.delete(f"/api/endpoints/{ep['id']}", headers=headers).status_code == 404

    assert client.delete(f"/api/projects/{p['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/projects/{p['id']}", headers=headers).status_code == 404


def test_creating_a_project_queues_a_scan_and_scan_now_forces_one(client, user, db):
    headers, _ = user()
    p = create(client, headers, repo_url="https://github.com/acme/shop")
    assert client.post(f"/api/projects/{p['id']}/scan", headers=headers).status_code == 202

    async def jobs(state):
        return [json.loads(f["data"]) for _, f in await state.redis.xrange("scan.jobs")]

    queued = db(jobs)
    assert [(j["delivery"], j.get("force", False)) for j in queued] == [("project-created", False), ("manual", True)]


def test_scan_needs_a_repository(client, user):
    headers, _ = user()
    p = create(client, headers)
    assert client.post(f"/api/projects/{p['id']}/scan", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"repo_url": "http://github.com/a/b"}, {"repo_url": "https://evil.com/a/b"}, {"endpoints": ["ftp://x.example.com"]},
     {"name": ""}],
)
def test_invalid_projects_are_rejected(client, user, body):
    headers, _ = user()
    assert client.post("/api/projects", headers=headers, json={"name": "X", **body}).status_code == 422


def test_projects_are_private_to_their_owner(client, user):
    alice, _ = user()
    mallory, _ = user()
    p = create(client, alice)
    assert client.get(f"/api/projects/{p['id']}", headers=mallory).status_code == 404
    assert client.patch(f"/api/projects/{p['id']}", headers=mallory, json={"name": "pwned"}).status_code == 404
    assert client.delete(f"/api/projects/{p['id']}", headers=mallory).status_code == 404
    assert client.put(f"/api/projects/{p['id']}/public", headers=mallory, json={"enabled": True}).status_code == 404
    assert client.get("/api/projects", headers=mallory).json()["projects"] == []


# ---------- dashboard ----------

async def seed_scores(state, project_id, total, findings=()):
    await state.pg.execute(
        """INSERT INTO project_scores (project_id, total, uptime, latency, errors, code, basis)
           VALUES ($1, $2, 40, 20, 20, 20, 'full')""",
        project_id, total,
    )
    for i, (sev, title) in enumerate(findings):
        await state.pg.execute(
            "INSERT INTO findings (project_id, key, severity, title, detail) VALUES ($1, $2, $3, $4, $5)",
            project_id, f"k{i}", sev, title, "secret detail",
        )


def test_dashboard(client, user, db):
    headers, _ = user()
    good = create(client, headers, name="Good")
    bad = create(client, headers, name="Bad")
    from uuid import UUID
    db(seed_scores, UUID(good["id"]), 95)
    db(seed_scores, UUID(bad["id"]), 40, [("critical", "Leaked key"), ("low", "No README")])

    d = client.get("/api/dashboard", headers=headers).json()
    assert d["user"]["email"].endswith("@example.com")
    assert [p["name"] for p in d["projects"]] == ["Bad", "Good"]  # worst first
    assert d["portfolio"]["needsAttention"] == 1 and d["portfolio"]["openFindings"] == 2
    assert d["biggestRisk"]["title"] == "Leaked key"
    assert len(d["today"]) <= 3 and isinstance(d["brief"], str)


def test_empty_dashboard(client, user):
    headers, _ = user()
    d = client.get("/api/dashboard", headers=headers).json()
    assert d["projects"] == [] and d["portfolio"]["health"] is None and d["biggestRisk"] is None


# ---------- public status page and badge ----------

async def seed_probes(state, project_id):
    now = datetime.now(timezone.utc)
    rows = [(now - timedelta(minutes=i), project_id, project_id, 200 if i % 10 else 503, 120.0 + i, i % 10 != 0) for i in range(60)]
    await state.ts.executemany(
        "INSERT INTO probe_results (time, endpoint_id, project_id, status, latency_ms, ok) VALUES ($1, $2, $3, $4, $5, $6)",
        rows,
    )
    await state.pg.execute(
        """INSERT INTO incidents (project_id, url, kind, status, opened_at, closed_at)
           VALUES ($1, 'https://shop.example.com/admin?token=abc', 'latency', 'closed', now() - interval '2 hours', now() - interval '1 hour'),
                  ($1, 'https://api.example.com/v1', 'errors', 'open', now() - interval '5 minutes', NULL)""",
        project_id,
    )


def test_status_page_and_badge(client, user, db):
    from uuid import UUID

    headers, _ = user()
    p = create(client, headers, name="My Shop!")
    pid = UUID(p["id"])
    db(seed_scores, pid, 94, [("critical", "AWS key in config.py")])
    db(seed_probes, pid)

    on = client.put(f"/api/projects/{p['id']}/public", headers=headers, json={"enabled": True}).json()["project"]
    slug = on["publicSlug"]
    assert on["isPublic"] and re.fullmatch(r"my-shop-[0-9a-f]{6}", slug)

    res = client.get(f"/api/public/status/{slug}")  # no auth
    assert res.status_code == 200 and "public" in res.headers["cache-control"]
    page = res.json()
    assert page["name"] == "My Shop!" and page["health"] == 94 and page["status"] == "healthy"
    assert page["uptime"]["24h"] == pytest.approx(90.0)
    assert [i["host"] for i in page["openIncidents"]] == ["api.example.com"]
    assert [i["host"] for i in page["resolvedIncidents"]] == ["shop.example.com"]  # no path or query
    text = res.text
    for leak in ("AWS key", "findings", "secret detail", "token=abc", "/admin"):
        assert leak not in text, f"public page leaked {leak!r}"

    badge = client.get(f"/api/badge/{slug}.svg")
    assert badge.status_code == 200 and badge.headers["content-type"].startswith("image/svg+xml")
    assert "max-age=300" in badge.headers["cache-control"]
    assert "bento health: 94" in badge.text and "#4a7a5c" in badge.text

    # private again: page gone, badge grey (never a 404), slug kept for next time
    client.put(f"/api/projects/{p['id']}/public", headers=headers, json={"enabled": False})
    assert client.get(f"/api/public/status/{slug}").status_code == 404
    grey = client.get(f"/api/badge/{slug}.svg")
    assert grey.status_code == 200 and "bento health: unknown" in grey.text and "max-age=60" in grey.headers["cache-control"]
    again = client.put(f"/api/projects/{p['id']}/public", headers=headers, json={"enabled": True}).json()["project"]
    assert again["publicSlug"] == slug


def test_unknown_slugs(client):
    assert client.get("/api/public/status/nope-123456").status_code == 404
    assert "unknown" in client.get("/api/badge/nope-123456.svg").text
    assert client.get(f"/api/public/status/{'x' * 200}").status_code == 404


def test_public_status_is_rate_limited(client):
    codes = {client.get("/api/public/status/nope").status_code for _ in range(61)}
    assert codes == {404, 429}


def test_badge_colours(client, user, db):
    from uuid import UUID

    headers, _ = user()
    for total, colour in ((90, "#4a7a5c"), (60, "#a8701c"), (20, "#b8422f")):
        p = create(client, headers, name=f"P{total}")
        db(seed_scores, UUID(p["id"]), total)
        slug = client.put(f"/api/projects/{p['id']}/public", headers=headers, json={"enabled": True}).json()["project"]["publicSlug"]
        assert colour in client.get(f"/api/badge/{slug}.svg").text


# ---------- report cards (analyzer scoring against the real database) ----------

def test_report_cards_history_and_week_change(client, user, db):
    from uuid import UUID

    from helpers import load_service

    analyzer = load_service("analyzer")
    headers, _ = user()
    p = create(client, headers, repo_url="https://github.com/acme/cards")
    pid = UUID(p["id"])

    async def scanned_with(state, findings):
        await state.pg.execute(
            "UPDATE projects SET last_scan_at = now(), scan_facts = $2 WHERE id = $1", pid, {"deps_checked": {"npm": 20}}
        )
        await state.pg.execute("UPDATE findings SET status = 'resolved' WHERE project_id = $1", pid)
        for key, sev, title in findings:
            await state.pg.execute(
                """INSERT INTO findings (project_id, key, severity, title) VALUES ($1, $2, $3, $4)
                   ON CONFLICT (project_id, key) DO UPDATE SET status = 'open'""",
                pid, key, sev, title,
            )
        await analyzer.Analyzer(state.pg, state.ts, state.redis).score_all()

    db(scanned_with, [("secret:aws-access-key:config.js", "critical", "AWS key in config.js"), ("no-tests", "medium", "No tests")])
    detail = client.get(f"/api/projects/{p['id']}", headers=headers).json()
    proj = detail["project"]
    assert proj["grade"] == "F" and proj["health"] <= 49 and "Security" in proj["capped"]
    assert set(proj["cards"]) == {"security", "website", "basics", "upkeep"}
    assert proj["cards"]["website"]["state"] == "not_monitored"
    assert proj["nextAction"]["key"] == "secret:aws-access-key:config.js" and proj["nextAction"]["gain"] > 0
    assert [h["reason"] for h in detail["history"]] == ["First score"]

    db(scanned_with, [("no-tests", "medium", "No tests")])  # the key was removed
    detail = client.get(f"/api/projects/{p['id']}", headers=headers).json()
    assert detail["history"][0]["reason"] == "Fixed: AWS key in config.js"
    assert detail["history"][0]["total"] > detail["history"][0]["previous"]
    assert detail["project"]["weekChange"] == detail["history"][0]["total"] - detail["history"][1]["total"]

    listed = client.get("/api/dashboard", headers=headers).json()["projects"][0]
    assert listed["grade"] == detail["project"]["grade"] and listed["weekChange"] == detail["project"]["weekChange"]


def test_same_repository_cannot_be_added_twice(client, user):
    headers, _ = user()
    first = create(client, headers, name="Shop", repo_url="https://github.com/acme/shop")
    dup = client.post("/api/projects", headers=headers, json={"name": "Shop again", "repo_url": "https://github.com/Acme/Shop.git"})
    assert dup.status_code == 409 and '"Shop"' in dup.json()["detail"]
    other = create(client, headers, name="Other", repo_url="https://github.com/acme/other")
    moved = client.patch(f"/api/projects/{other['id']}", headers=headers, json={"repo_url": "https://github.com/acme/shop"})
    assert moved.status_code == 409
    assert client.patch(f"/api/projects/{first['id']}", headers=headers, json={"name": "Renamed"}).status_code == 200
    # someone else may add the same repository to their own account
    theirs, _ = user()
    assert client.post("/api/projects", headers=theirs, json={"name": "Shop", "repo_url": "https://github.com/acme/shop"}).status_code == 201
