"""
Export Gmail messages for the discovery window (Jan 1 – Mar 31, 2026).
Outputs one JSON file per message into emails/discovery/.
"""

import os
import json
import base64
import email
import re
import sys
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PROJECT_DIR = Path(__file__).parent
CREDS_FILE = PROJECT_DIR / "credentials.json"
TOKEN_FILE = PROJECT_DIR / "token.json"

QUERY = "after:2026/01/01 before:2026/04/01"
OUT_DIR = PROJECT_DIR / "emails" / "discovery"


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def list_message_ids(service, query):
    """Paginate through messages.list and return all message IDs."""
    ids = []
    page_token = None
    while True:
        resp = service.users().messages().list(
            userId="me", q=query, maxResults=500, pageToken=page_token
        ).execute()
        for msg in resp.get("messages", []):
            ids.append(msg["id"])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        print(f"  Listed {len(ids)} message IDs so far...", file=sys.stderr)
    return ids


SIGNATURE_PATTERNS = [
    re.compile(r"^--\s*$", re.MULTILINE),
    re.compile(r"^Sent from my (iPhone|iPad|Galaxy|Pixel|Android)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Get Outlook for", re.MULTILINE | re.IGNORECASE),
]

QUOTE_PATTERNS = [
    re.compile(r"^On .+ wrote:$", re.MULTILINE),
    re.compile(r"^>", re.MULTILINE),
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^_{3,}\s*$", re.MULTILINE),
    re.compile(r"^From:\s+.+@", re.MULTILINE),
]


def strip_quoted_and_signature(text):
    """Remove quoted reply chains and signatures, keeping only the new content."""
    if not text:
        return text

    lines = text.split("\n")
    cut_at = len(lines)

    for i, line in enumerate(lines):
        for pat in SIGNATURE_PATTERNS:
            if pat.search(line):
                cut_at = min(cut_at, i)
                break
        for pat in QUOTE_PATTERNS:
            if pat.search(line):
                cut_at = min(cut_at, i)
                break
        if cut_at < len(lines):
            break

    cleaned = "\n".join(lines[:cut_at]).rstrip()
    return cleaned


def parse_message(raw_bytes):
    """Parse a raw MIME message into our structured format."""
    msg = email.message_from_bytes(raw_bytes)

    def decode_header(val):
        if not val:
            return ""
        parts = email.header.decode_header(val)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)

    subject = decode_header(msg.get("Subject", ""))
    from_addr = decode_header(msg.get("From", ""))
    to_addr = decode_header(msg.get("To", ""))
    cc_addr = decode_header(msg.get("Cc", ""))
    date_str = decode_header(msg.get("Date", ""))
    message_id = decode_header(msg.get("Message-ID", ""))
    in_reply_to = decode_header(msg.get("In-Reply-To", ""))
    references = decode_header(msg.get("References", ""))

    body_plain = ""
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain" and not part.get("Content-Disposition", "").startswith("attachment"):
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_plain += payload.decode(charset, errors="replace")

    body_cleaned = strip_quoted_and_signature(body_plain)

    return {
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "date": date_str,
        "from": from_addr,
        "to": to_addr,
        "cc": cc_addr,
        "subject": subject,
        "body_raw": body_plain,
        "body_cleaned": body_cleaned,
    }


def export_message(service, gmail_id, out_dir):
    """Fetch one message in raw format, parse it, and save."""
    out_file = out_dir / f"{gmail_id}.json"
    if out_file.exists():
        return "skip"

    resp = service.users().messages().get(
        userId="me", id=gmail_id, format="raw"
    ).execute()

    raw = base64.urlsafe_b64decode(resp["raw"])
    thread_id = resp.get("threadId", "")
    label_ids = resp.get("labelIds", [])

    parsed = parse_message(raw)
    parsed["gmail_id"] = gmail_id
    parsed["thread_id"] = thread_id
    parsed["label_ids"] = label_ids

    out_file.write_text(json.dumps(parsed, indent=2, ensure_ascii=False))
    return "saved"


def main():
    print("Authenticating...", file=sys.stderr)
    service = get_service()

    print(f"Listing messages matching: {QUERY}", file=sys.stderr)
    msg_ids = list_message_ids(service, QUERY)
    print(f"Found {len(msg_ids)} messages total.", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    skipped = 0
    errors = 0
    for i, mid in enumerate(msg_ids):
        try:
            result = export_message(service, mid, OUT_DIR)
            if result == "saved":
                saved += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error on {mid}: {e}", file=sys.stderr)
            errors += 1

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(msg_ids)} (saved={saved}, skipped={skipped}, errors={errors})", file=sys.stderr)

    print(f"\nDone. {saved} saved, {skipped} skipped, {errors} errors.", file=sys.stderr)
    print(f"Output: {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
