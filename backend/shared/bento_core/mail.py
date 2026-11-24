"""Email through Resend: incident alerts and the weekly digest, each with a one-click unsubscribe.

Without RESEND_API_KEY every send is skipped with a log line and returns False; nothing else changes.
Unsubscribe links carry a signed token (same signing key as logins, but typ=unsubscribe, so neither can
be used as the other). They never expire: an unsubscribe link must keep working.
"""

from __future__ import annotations

import html
import logging
from uuid import UUID

import httpx
import jwt

from .config import settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
KINDS = {"incidents": "incident alerts", "digest": "the weekly digest"}
TOKEN_TYPE = "unsubscribe"
UNDELIVERABLE = ("@users.noreply.github.com",)  # GitHub accounts without a public email


def configured() -> bool:
    return bool(settings.resend_api_key)


def deliverable(address: str | None) -> bool:
    return bool(address) and "@" in address and not address.lower().endswith(UNDELIVERABLE)


# ---------- unsubscribe ----------

def unsubscribe_token(user_id: UUID | str, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(kind)
    return jwt.encode({"typ": TOKEN_TYPE, "u": str(user_id), "k": kind}, settings.jwt_secret, algorithm="HS256")


def read_unsubscribe_token(token: str | None) -> tuple[UUID, str] | None:
    try:
        payload = jwt.decode(token or "", settings.jwt_secret, algorithms=["HS256"])
        if payload.get("typ") != TOKEN_TYPE or payload.get("k") not in KINDS:
            return None
        return UUID(payload["u"]), payload["k"]
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def unsubscribe_url(user_id: UUID | str, kind: str) -> str:
    return f"{settings.public_url}/api/email/unsubscribe?token={unsubscribe_token(user_id, kind)}"


# ---------- sending ----------

async def send(http: httpx.AsyncClient, to: str, subject: str, html_body: str, text: str, unsubscribe: str) -> bool:
    """Send one email. Returns False (and logs why) when it wasn't sent; never raises for delivery problems."""
    if not configured():
        log.info("email skipped (RESEND_API_KEY not set): %s", subject)
        return False
    if not deliverable(to):
        log.info("email skipped (no deliverable address): %s", subject)
        return False
    try:
        res = await http.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html_body,
                "text": text,
                # Gmail/Apple Mail show their own one-click "Unsubscribe" button for these (RFC 8058)
                "headers": {"List-Unsubscribe": f"<{unsubscribe}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
            },
            timeout=15,
        )
    except httpx.HTTPError as exc:
        log.warning("email not sent (%s): %s", type(exc).__name__, subject)
        return False
    if res.status_code >= 300:
        log.warning("email not sent (Resend %s): %s", res.status_code, subject)
        return False
    return True


# ---------- templates (simple HTML, inline styles: email clients ignore stylesheets) ----------

INK, MUTED, LINE, OK, WARN, CRIT = "#17130f", "#8a8680", "#ece9e3", "#4a7a5c", "#a8701c", "#b8422f"
GRADE_COLOUR = {"A": OK, "B": OK, "C": WARN, "D": WARN, "F": CRIT}
e = html.escape


def _layout(heading: str, body: str, unsubscribe: str, what: str) -> str:
    return f"""<!doctype html><html><body style="margin:0;padding:0;background:#fbfaf8">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#fbfaf8"><tr><td align="center" style="padding:32px 16px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;font-family:Inter,-apple-system,'Segoe UI',Arial,sans-serif;color:{INK}">
<tr><td style="font-size:13px;font-weight:700;letter-spacing:.08em;padding-bottom:24px">BENTO</td></tr>
<tr><td style="font-size:24px;font-weight:300;letter-spacing:-.02em;padding-bottom:16px">{heading}</td></tr>
<tr><td style="font-size:15px;line-height:1.6">{body}</td></tr>
<tr><td style="padding-top:32px;border-top:1px solid {LINE};font-size:12px;color:{MUTED};line-height:1.6">
You're getting this because {e(what)} are on for your Bento account.
<a href="{e(unsubscribe)}" style="color:{MUTED}">Unsubscribe</a> ·
<a href="{e(settings.public_url)}/dashboard" style="color:{MUTED}">Email settings</a></td></tr>
</table></td></tr></table></body></html>"""


def _button(label: str, url: str) -> str:
    return (f'<p style="margin:24px 0 0"><a href="{e(url)}" style="display:inline-block;padding:10px 18px;background:{INK};'
            f'color:#fbfaf8;text-decoration:none;border-radius:8px;font-size:14px">{e(label)}</a></p>')


def incident_email(project: str, title: str, detail: str, opened: bool, unsubscribe: str) -> tuple[str, str, str]:
    """(subject, html, text) for an incident opening or resolving."""
    subject = f"{'🔴' if opened else '🟢'} {project}: {title}"
    lead = ("Bento noticed something wrong and opened an incident." if opened
            else "Good news: things are back to normal and the incident is closed.")
    body = (f'<p style="margin:0 0 12px">{e(lead)}</p>'
            f'<p style="margin:0;padding:14px 16px;border:1px solid {LINE};border-radius:8px;background:#fff">'
            f'<strong>{e(project)}</strong><br><span style="color:{MUTED}">{e(detail)}</span></p>'
            + _button("Open Bento", f"{settings.public_url}/dashboard"))
    text = f"{lead}\n\n{project}: {title}\n{detail}\n\nOpen Bento: {settings.public_url}/dashboard\nUnsubscribe: {unsubscribe}"
    return subject, _layout(e(title), body, unsubscribe, KINDS["incidents"]), text


def digest_email(d: dict, unsubscribe: str) -> tuple[str, str, str]:
    """(subject, html, text) for the weekly digest. d: health, change, projects, new, resolved, top."""
    health, change = d.get("health"), d.get("change")
    trend = "" if change in (None, 0) else (f" (▲ {change} this week)" if change > 0 else f" (▼ {-change} this week)")
    subject = f"Your week in Bento: health {health if health is not None else '—'}{trend}"

    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid {LINE}">{e(p["name"])}</td>'
        f'<td align="right" style="padding:8px 0;border-bottom:1px solid {LINE};color:{GRADE_COLOUR.get(p.get("grade") or "", MUTED)};'
        f'font-weight:600">{e(p.get("grade") or "—")} {p["health"] if p.get("health") is not None else ""}</td>'
        f'<td align="right" style="padding:8px 0 8px 12px;border-bottom:1px solid {LINE};color:{MUTED};font-size:13px">'
        f'{"" if not p.get("change") else ("▲ " if p["change"] > 0 else "▼ ") + str(abs(p["change"]))}</td></tr>'
        for p in d.get("projects", [])
    )

    def items(title: str, lst: list[dict], empty: str) -> str:
        if not lst:
            return f'<p style="margin:24px 0 4px;font-weight:600">{e(title)}</p><p style="margin:0;color:{MUTED}">{e(empty)}</p>'
        lis = "".join(f'<li style="margin:4px 0">{e(i["title"])} <span style="color:{MUTED}">· {e(i["project"])}</span></li>'
                      for i in lst[:8])
        more = f'<li style="color:{MUTED}">…and {len(lst) - 8} more</li>' if len(lst) > 8 else ""
        return f'<p style="margin:24px 0 4px;font-weight:600">{e(title)}</p><ul style="margin:0;padding-left:20px">{lis}{more}</ul>'

    top = "".join(
        f'<li style="margin:8px 0"><strong>{e(t["title"])}</strong><br><span style="color:{MUTED};font-size:14px">'
        f'{e(t["project"])}{" · " + e(t["why"]) if t.get("why") else ""}</span></li>'
        for t in d.get("top", [])[:3]
    )
    body = (
        f'<p style="margin:0">Portfolio health: <strong style="font-size:20px">{health if health is not None else "—"}</strong>'
        f'<span style="color:{MUTED}">{e(trend)}</span></p>'
        + (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;font-size:14px">{rows}</table>' if rows else "")
        + (f'<p style="margin:28px 0 4px;font-weight:600">Pickle\'s top 3 for this week</p><ol style="margin:0;padding-left:20px">{top}</ol>' if top else "")
        + items("New this week", d.get("new", []), "No new problems. Nice.")
        + items("Fixed this week", d.get("resolved", []), "Nothing fixed this week.")
        + _button("Open Bento", f"{settings.public_url}/dashboard")
    )
    text_lines = [subject, ""]
    text_lines += [f"- {p['name']}: {p.get('grade') or '-'} {p.get('health') if p.get('health') is not None else ''}" for p in d.get("projects", [])]
    if d.get("top"):
        text_lines += ["", "Pickle's top 3:"] + [f"{i}. {t['title']} ({t['project']})" for i, t in enumerate(d["top"][:3], 1)]
    text_lines += ["", f"New this week: {len(d.get('new', []))} · Fixed: {len(d.get('resolved', []))}",
                   f"Open Bento: {settings.public_url}/dashboard", f"Unsubscribe: {unsubscribe}"]
    return subject, _layout("Your week in Bento", body, unsubscribe, KINDS["digest"]), "\n".join(text_lines)
