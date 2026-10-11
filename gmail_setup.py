"""One-time Gmail API setup for the demo inbox (animalprotectiveservices2026@gmail.com).

Usage:
  python3 gmail_setup.py auth   # browser OAuth; SIGN IN AS THE DEMO ACCOUNT; saves token_apsdemo.json
  python3 gmail_setup.py smoke  # insert a test email into the inbox + create a draft, verify via API

Uses the APS-owned project's OAuth client (aps_credentials.json — download from that
project's console). foster@'s token.json + dps_credentials.json are untouched.
Scope gmail.modify covers everything the prototype needs (read, messages.insert,
drafts.create) without requesting full mail.google.com access.
"""
import base64
import sys
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN = Path("token_apsdemo.json")
CLIENT = "aps_credentials.json"
EXPECTED = "animalprotectiveservices2026@gmail.com"


def service():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def cmd_auth():
    svc = service()
    email = svc.users().getProfile(userId="me").execute()["emailAddress"]
    print(f"authorized as: {email}")
    if email.lower() != EXPECTED:
        print(f"WRONG ACCOUNT — expected {EXPECTED}.")
        print(f"Delete {TOKEN} and re-run `auth`, picking the demo account in the browser.")
        sys.exit(1)
    print(f"token saved to {TOKEN} (gitignored)")


def cmd_smoke():
    svc = service()

    msg = EmailMessage()
    msg["From"] = "Jane Doe <jane.doe@example.com>"
    msg["To"] = EXPECTED
    msg["Subject"] = "Smoke test: hello from the simulator"
    msg.set_content("If you can read this in the inbox, messages.insert works.")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    ins = svc.users().messages().insert(
        userId="me",
        body={"raw": raw, "labelIds": ["INBOX", "UNREAD"]},
        internalDateSource="receivedTime",
    ).execute()
    print("inserted inbox message:", ins["id"])

    reply = EmailMessage()
    reply["To"] = "jane.doe@example.com"
    reply["Subject"] = "Re: Smoke test"
    reply.set_content("Draft created by the API — check the Drafts folder.")
    draw = base64.urlsafe_b64encode(reply.as_bytes()).decode()
    d = svc.users().drafts().create(userId="me", body={"message": {"raw": draw}}).execute()
    print("created draft:", d["id"])

    prof = svc.users().getProfile(userId="me").execute()
    print(f"verified {prof['emailAddress']}: {prof['messagesTotal']} messages total")
    print("open Gmail — the test email is in Inbox (unread), the draft in Drafts.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "auth":
        cmd_auth()
    elif cmd == "smoke":
        cmd_smoke()
    else:
        print(__doc__)
