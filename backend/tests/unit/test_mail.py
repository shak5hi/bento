"""Email: unsubscribe tokens, sending through Resend (mocked), templates, incident emails and the digest schedule."""

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest

from app.security import issue_token
from bento_core import mail
from bento_core.config import settings
from helpers import load_service

notifier = load_service("notifier")
digest = load_service("notifier", "digest")


# ---------- unsubscribe tokens ----------

def test_unsubscribe_token_round_trip():
    user = uuid4()
    assert mail.read_unsubscribe_token(mail.unsubscribe_token(user, "digest")) == (user, "digest")
    assert mail.unsubscribe_url(user, "incidents").startswith(f"{settings.public_url}/api/email/unsubscribe?token=")


@pytest.mark.parametrize("token", [None, "", "garbage", issue_token(uuid4(), "a@example.com")])
def test_other_tokens_are_not_unsubscribe_tokens(token):
    assert mail.read_unsubscribe_token(token) is None


def test_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        mail.unsubscribe_token(uuid4(), "everything")


# ---------- sending ----------

@pytest.fixture
def resend(monkeypatch):
    sent = []

    def handler(request):
        sent.append({"auth": request.headers["Authorization"], **json.loads(request.content)})
        return httpx.Response(200, json={"id": "email-1"})

    monkeypatch.setattr(settings, "resend_api_key", "resend-key-for-tests")
    return sent, httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_without_an_api_key_emails_are_skipped(monkeypatch, caplog):
    monkeypatch.setattr(settings, "resend_api_key", None)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("must not call Resend"))) as http:
        with caplog.at_level("INFO"):
            assert await mail.send(http, "a@example.com", "Hi", "<p>hi</p>", "hi", "https://x/unsub") is False
    assert "RESEND_API_KEY set" in caplog.text


async def test_send_through_gmail_smtp_when_configured(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context):
            sent.append(("tls",))

        def login(self, user, password):
            sent.append(("login", user))

        def send_message(self, msg):
            sent.append(("send", msg["From"], msg["To"], msg["Subject"], msg["List-Unsubscribe"]))

    monkeypatch.setattr(settings, "smtp_user", "bento.alerts@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password-for-tests")
    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("must not call Resend"))) as http:
        assert await mail.send(http, "friend@example.com", "Hi", "<p>hi</p>", "hi", "https://x/unsub") is True
    assert sent[0] == ("connect", "smtp.gmail.com", 587) and ("tls",) in sent
    assert sent[-1] == ("send", "Bento <bento.alerts@gmail.com>", "friend@example.com", "Hi", "<https://x/unsub>")


async def test_send_through_resend_with_one_click_unsubscribe(resend):
    sent, http = resend
    assert await mail.send(http, "a@example.com", "Hi", "<p>hi</p>", "hi", "https://bento.test/u?t=1") is True
    (msg,) = sent
    assert msg["auth"] == "Bearer resend-key-for-tests" and msg["to"] == ["a@example.com"]
    assert msg["from"] == settings.email_from and msg["text"] == "hi"
    assert msg["headers"] == {"List-Unsubscribe": "<https://bento.test/u?t=1>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


async def test_github_noreply_addresses_are_skipped(resend):
    sent, http = resend
    assert await mail.send(http, "123+octo@users.noreply.github.com", "Hi", "", "", "u") is False
    assert sent == []


@pytest.mark.parametrize("response", [httpx.Response(422, json={"message": "bad"}), httpx.ConnectError("down")])
async def test_delivery_problems_never_raise(monkeypatch, response):
    monkeypatch.setattr(settings, "resend_api_key", "k")

    def handler(request):
        if isinstance(response, Exception):
            raise response
        return response

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await mail.send(http, "a@example.com", "Hi", "", "", "u") is False


# ---------- templates ----------

def test_incident_email_escapes_user_content():
    subject, html_body, text = mail.incident_email("<script>x</script>", "Latency incident", "slow & sad", True, "https://u")
    assert subject.startswith("🔴") and "<script>" not in html_body and "&lt;script&gt;" in html_body
    assert "slow &amp; sad" in html_body and 'href="https://u"' in html_body and "Unsubscribe: https://u" in text


def test_digest_email():
    d = {"health": 82, "change": 4, "projects": [{"name": "Shop", "health": 82, "grade": "B", "change": 4}],
         "new": [{"title": "No CI", "project": "Shop", "severity": "low"}], "resolved": [],
         "top": [{"title": "Add CI", "why": "Catch breakages", "project": "Shop", "severity": "low"}]}
    subject, html_body, text = mail.digest_email(d, "https://u")
    assert subject == "Your week in Bento: health 82 (▲ 4 this week)"
    assert "Pickle's top 3" in html_body and "Add CI" in html_body and "No CI" in html_body and "Nothing fixed" in html_body
    assert "1. Add CI (Shop)" in text


# ---------- incident emails from the notifier ----------

class FakeRedis:
    def __init__(self):
        self.kv, self.counts = {}, {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def delete(self, key):
        self.kv.pop(key, None)

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1


class FakePg:
    def __init__(self, wants_email=True):
        self.wants_email = wants_email

    async def fetchval(self, sql, *args):
        return "Shop"

    async def fetchrow(self, sql, *args):
        return {"email": "owner@example.com", "email_incidents": self.wants_email}

    async def execute(self, sql, *args):
        pass


ALERT = {"type": "open", "kind": "latency", "endpoint_id": "e1", "project_id": "p1", "owner_id": str(uuid4()),
         "incident_id": "i1", "url": "https://shop.example.com", "value": 900, "baseline": 120}


async def test_incident_emails_respect_the_cooldown(resend):
    sent, http = resend
    n = notifier.Notifier(FakePg(), FakeRedis(), http)
    await n.deliver(ALERT)
    await n.deliver(ALERT)  # repeat within the cooldown: suppressed, no second email
    await n.deliver({**ALERT, "type": "resolved"})
    assert [m["subject"][0] for m in sent] == ["🔴", "🟢"]
    assert "Shop" in sent[0]["subject"] and "unsubscribe?token=" in sent[0]["headers"]["List-Unsubscribe"]


async def test_no_incident_email_when_switched_off(resend):
    sent, http = resend
    await notifier.Notifier(FakePg(wants_email=False), FakeRedis(), http).deliver(ALERT)
    assert sent == []


# ---------- digest schedule ----------

@pytest.mark.parametrize(
    ("now", "tz", "expected"),
    [
        (datetime(2026, 11, 30, 8, 0, tzinfo=timezone.utc), "UTC", "2026-W49"),   # Monday 08:00
        (datetime(2026, 11, 30, 7, 59, tzinfo=timezone.utc), "UTC", None),        # too early
        (datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc), "UTC", None),          # Tuesday
        (datetime(2026, 11, 30, 2, 40, tzinfo=timezone.utc), "Asia/Kolkata", "2026-W49"),  # 08:10 in India
        (datetime(2026, 11, 30, 8, 0, tzinfo=timezone.utc), "Not/AZone", "2026-W49"),      # bad zone: UTC
    ],
)
def test_digest_is_due_monday_morning(now, tz, expected):
    assert digest.due_week(now, tz, 8) == expected
