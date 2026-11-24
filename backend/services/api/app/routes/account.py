"""Email settings and one-click unsubscribe.

GET /api/email/unsubscribe shows a page with a single button rather than unsubscribing straight away:
mail security scanners open every link in an email, and they must not unsubscribe people by accident.
POST to the same URL (the button, or a mail app's own one-click "Unsubscribe", RFC 8058) does it.
"""

import html
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from bento_core import mail
from bento_core.config import settings

from ..security import current_user_id, rate_limit
from ..state import state

router = APIRouter(prefix="/api", tags=["account"])
COLUMN = {"incidents": "email_incidents", "digest": "email_digest"}


class EmailSettings(BaseModel):
    incidentEmails: bool | None = None
    weeklyDigest: bool | None = None


async def _settings_json(user_id: UUID) -> dict:
    row = await state.pg.fetchrow("SELECT email, email_incidents, email_digest FROM users WHERE id = $1", user_id)
    if row is None:
        raise HTTPException(401, "Account no longer exists")
    return {
        "email": row["email"],
        "deliverable": mail.deliverable(row["email"]),
        "incidentEmails": row["email_incidents"],
        "weeklyDigest": row["email_digest"],
        "emailConfigured": mail.configured(),
    }


@router.get("/me/email")
async def get_email_settings(user_id: UUID = Depends(current_user_id)):
    return await _settings_json(user_id)


@router.put("/me/email")
async def put_email_settings(body: EmailSettings, user_id: UUID = Depends(current_user_id)):
    await state.pg.execute(
        """UPDATE users SET email_incidents = coalesce($2, email_incidents), email_digest = coalesce($3, email_digest)
            WHERE id = $1""",
        user_id, body.incidentEmails, body.weeklyDigest,
    )
    return await _settings_json(user_id)


def _page(title: str, message: str, form: str = "") -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Bento</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#fbfaf8;color:#17130f;
font-family:Inter,-apple-system,'Segoe UI',sans-serif}}main{{max-width:420px;padding:32px}}
h1{{font-weight:300;font-size:28px;letter-spacing:-.02em;margin:0 0 12px}}p{{color:#55524c;line-height:1.6}}
button{{font:inherit;padding:10px 18px;border:0;border-radius:8px;background:#17130f;color:#fbfaf8;cursor:pointer}}
a{{color:#55524c}}</style></head><body><main><p style="font-weight:700;letter-spacing:.08em;font-size:13px">BENTO</p>
<h1>{html.escape(title)}</h1><p>{message}</p>{form}</main></body></html>""")


@router.get("/email/unsubscribe", response_class=HTMLResponse, include_in_schema=False,
            dependencies=[Depends(rate_limit("unsubscribe", 30, 60))])
async def unsubscribe_page(token: str = Query(default="")):
    parsed = mail.read_unsubscribe_token(token)
    if parsed is None:
        return _page("This link isn't valid", "It may have been copied incompletely. You can change your email settings "
                     f'in <a href="{html.escape(settings.public_url)}/dashboard">Bento</a>.')
    _, kind = parsed
    form = (f'<form method="post"><input type="hidden" name="token" value="{html.escape(token)}">'
            f'<button type="submit">Unsubscribe</button></form>')
    return _page(f"Stop {mail.KINDS[kind]}?", f"You won't get {mail.KINDS[kind]} from Bento any more. "
                 "You can turn them back on any time in your email settings.", form)


@router.post("/email/unsubscribe", response_class=HTMLResponse, include_in_schema=False,
             dependencies=[Depends(rate_limit("unsubscribe", 30, 60))])
async def unsubscribe(request: Request, token: str | None = Query(default=None)):
    # the button posts the token as a form field; mail apps' one-click posts to the URL that already has it
    if not token:
        form = parse_qs((await request.body())[:4096].decode("utf-8", errors="ignore"))
        token = (form.get("token") or [None])[0]
    parsed = mail.read_unsubscribe_token(token)
    if parsed is None:
        raise HTTPException(400, "This unsubscribe link isn't valid")
    user_id, kind = parsed
    await state.pg.execute(f"UPDATE users SET {COLUMN[kind]} = false WHERE id = $1", user_id)
    return _page("You're unsubscribed", f"You won't get {mail.KINDS[kind]} any more. Changed your mind? Turn them back on in "
                 f'<a href="{html.escape(settings.public_url)}/dashboard">your email settings</a>.')
