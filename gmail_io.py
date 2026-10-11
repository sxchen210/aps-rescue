"""Shared Gmail access for the simulation pipeline.

Two accounts:
  ref — the reference rescue inbox. Read-only by OAuth scope; consulted
        transiently for structure distillation and leak checking.
  aps — the demo inbox (animalprotectiveservices2026@gmail.com). The only
        writable account: messages.insert for seeding, drafts.create for
        output. Nothing is ever sent.
"""
import base64
import re
import time
from email.message import EmailMessage
from functools import lru_cache
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent
ACCOUNTS = {
    "ref": ROOT / "token.json",           # created read-only; do not re-auth wider
    "aps": ROOT / "token_apsdemo.json",   # gmail.modify (read + insert + drafts)
}


@lru_cache(maxsize=None)
def service(account):
    token_path = Path(ACCOUNTS[account])
    if not token_path.exists():
        raise RuntimeError(f"{token_path} missing — run the auth flow for '{account}' first")
    creds = Credentials.from_authorized_user_file(str(token_path))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def profile(account):
    return service(account).users().getProfile(userId="me").execute()


def search_threads(account, query, limit=10):
    """Thread ids + snippets for a Gmail search query, newest first."""
    resp = service(account).users().threads().list(
        userId="me", q=query, maxResults=limit).execute()
    return resp.get("threads", [])


def _header(payload, name):
    for h in payload.get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _body_text(payload):
    """Prefer text/plain anywhere in the MIME tree; fall back to stripped HTML."""
    stack, plain, html = [payload], [], []
    while stack:
        p = stack.pop()
        stack.extend(p.get("parts", []))
        data = p.get("body", {}).get("data")
        if not data:
            continue
        text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        (plain if p.get("mimeType", "").startswith("text/plain") else html).append(text)
    if plain:
        return "\n".join(plain)
    joined = "\n".join(html)
    joined = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", joined, flags=re.S | re.I)
    joined = re.sub(r"<br\s*/?>|</p>", "\n", joined, flags=re.I)
    return re.sub(r"<[^>]+>", " ", joined)


def _trim_quoted(body):
    """Drop quoted tails ('>' blocks and 'On ... wrote:' onward) for readability."""
    lines, out = body.splitlines(), []
    for ln in lines:
        if re.match(r"\s*On .{5,80} wrote:\s*$", ln):
            break
        if ln.lstrip().startswith(">"):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def _retry_quota(fn, tries=6):
    from googleapiclient.errors import HttpError
    for attempt in range(tries):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status in (403, 429) and attempt < tries - 1:
                time.sleep(15 * (attempt + 1))
            else:
                raise


def get_thread(account, thread_id, trim_quotes=True):
    """Thread as a list of {date, from, to, cc, subject, body}, oldest first."""
    t = _retry_quota(lambda: service(account).users().threads().get(
        userId="me", id=thread_id, format="full").execute())
    msgs = []
    for m in t.get("messages", []):
        p = m["payload"]
        body = _body_text(p)
        if trim_quotes:
            body = _trim_quoted(body)
        msgs.append({
            "gmail_id": m["id"],
            "date": _header(p, "Date"),
            "from": _header(p, "From"),
            "to": _header(p, "To"),
            "cc": _header(p, "Cc"),
            "subject": _header(p, "Subject"),
            "body": body.strip(),
        })
    return msgs


def render_thread(msgs, max_body=1200):
    """Readable text block for a distillation session."""
    out = []
    for i, m in enumerate(msgs, 1):
        out.append(f"--- message {i}/{len(msgs)} ---")
        out.append(f"Date: {m['date']}\nFrom: {m['from']}\nTo: {m['to']}")
        if m["cc"]:
            out.append(f"Cc: {m['cc']}")
        out.append(f"Subject: {m['subject']}\n")
        body = m["body"]
        out.append(body[:max_body] + (" […]" if len(body) > max_body else ""))
        out.append("")
    return "\n".join(out)


def insert_message(account, *, from_addr, to, subject, body, date,
                   cc=None, in_reply_to=None, references=None,
                   message_id=None, label_ids=("INBOX", "UNREAD"),
                   thread_id=None):
    """Place a fully-formed message in the mailbox (no delivery, no sending).

    `date` is an RFC 2822 string; internalDateSource=dateHeader makes Gmail
    display it as the receive time, so historical seeding looks right."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = date
    if message_id:
        msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw, "labelIds": list(label_ids)}
    if thread_id:
        payload["threadId"] = thread_id
    return service(account).users().messages().insert(
        userId="me", body=payload, internalDateSource="dateHeader",
    ).execute()


def create_draft(account, *, to, subject, body, thread_id=None,
                 in_reply_to=None, references=None):
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id
    return service(account).users().drafts().create(userId="me", body=payload).execute()
