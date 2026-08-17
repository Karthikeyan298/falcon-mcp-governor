"""SMTP/IMAP access layer for the email MCP server."""

from __future__ import annotations

import imaplib
import os
import smtplib
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as default_policy
from typing import Any


@dataclass
class EmailSettings:
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    imap_host: str
    imap_port: int
    user: str
    password: str
    imap_mock: bool = False

    @classmethod
    def from_env(cls) -> "EmailSettings":
        missing = [
            name
            for name in ("EMAIL_USER", "EMAIL_PASSWORD", "EMAIL_SMTP_HOST", "EMAIL_IMAP_HOST")
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required email settings: {', '.join(missing)}. "
                "Copy .env.example to .env and fill them in."
            )
        return cls(
            smtp_host=os.environ["EMAIL_SMTP_HOST"],
            smtp_port=int(os.environ.get("EMAIL_SMTP_PORT", "587")),
            smtp_use_tls=os.environ.get("EMAIL_SMTP_USE_TLS", "true").lower() == "true",
            imap_host=os.environ["EMAIL_IMAP_HOST"],
            imap_port=int(os.environ.get("EMAIL_IMAP_PORT", "993")),
            user=os.environ["EMAIL_USER"],
            password=os.environ["EMAIL_PASSWORD"],
            imap_mock=os.environ.get("EMAIL_IMAP_MOCK", "false").lower() == "true",
        )


_MOCK_FOLDERS = ["INBOX", "Sent", "Drafts", "Trash"]

_MOCK_MESSAGES = [
    {
        "id": "1",
        "from": "alice@example.com",
        "to": "you@example.com",
        "subject": "Welcome to the mock inbox",
        "date": "Mon, 17 Aug 2026 09:00:00 +0000",
    },
    {
        "id": "2",
        "from": "bob@example.com",
        "to": "you@example.com",
        "subject": "Dummy message for testing",
        "date": "Mon, 17 Aug 2026 10:30:00 +0000",
    },
]


def send_email(
    settings: EmailSettings,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html: bool = False,
) -> dict[str, Any]:
    if not to:
        raise ValueError("'to' must contain at least one recipient")

    msg = EmailMessage()
    msg["From"] = settings.user
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    if html:
        msg.set_content(body, subtype="html")
    else:
        msg.set_content(body)

    all_recipients = list(to) + list(cc or []) + list(bcc or [])

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as client:
        if settings.smtp_use_tls:
            client.starttls()
        client.login(settings.user, settings.password)
        client.send_message(msg, from_addr=settings.user, to_addrs=all_recipients)

    return {"status": "sent", "to": to, "cc": cc or [], "bcc": bcc or [], "subject": subject}


def _decode(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _imap_connect(settings: EmailSettings) -> imaplib.IMAP4_SSL:
    client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    client.login(settings.user, settings.password)
    return client


def list_folders(settings: EmailSettings) -> list[str]:
    if settings.imap_mock:
        return list(_MOCK_FOLDERS)
    client = _imap_connect(settings)
    try:
        status, folders = client.list()
        if status != "OK":
            raise RuntimeError(f"IMAP LIST failed: {status}")
        names = []
        for entry in folders or []:
            decoded = entry.decode(errors="replace") if isinstance(entry, bytes) else str(entry)
            # Format: (\Flags) "/" "Folder Name"
            name = decoded.rsplit('"', 2)[-2] if '"' in decoded else decoded.split()[-1]
            names.append(name)
        return names
    finally:
        client.logout()


def list_messages(
    settings: EmailSettings,
    folder: str = "INBOX",
    limit: int = 20,
    unseen_only: bool = False,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    if settings.imap_mock:
        return list(_MOCK_MESSAGES)[:limit]
    client = _imap_connect(settings)
    try:
        status, _ = client.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"Cannot open folder '{folder}'")

        criterion = "UNSEEN" if unseen_only else "ALL"
        status, data = client.search(None, criterion)
        if status != "OK":
            raise RuntimeError(f"IMAP SEARCH failed: {status}")

        ids = data[0].split()
        ids = ids[-limit:]
        ids.reverse()

        results = []
        for msg_id in ids:
            status, msg_data = client.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            header_bytes = msg_data[0][1]
            parsed = BytesParser(policy=default_policy).parsebytes(header_bytes)
            results.append(
                {
                    "id": msg_id.decode(),
                    "from": _decode(parsed.get("From")),
                    "to": _decode(parsed.get("To")),
                    "subject": _decode(parsed.get("Subject")),
                    "date": parsed.get("Date", ""),
                }
            )
        return results
    finally:
        client.logout()


def read_message(settings: EmailSettings, message_id: str, folder: str = "INBOX") -> dict[str, Any]:
    if settings.imap_mock:
        match = next((m for m in _MOCK_MESSAGES if m["id"] == message_id), _MOCK_MESSAGES[0])
        return {**match, "body": f"This is a dummy body for mock message {match['id']}."}
    client = _imap_connect(settings)
    try:
        status, _ = client.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"Cannot open folder '{folder}'")

        status, msg_data = client.fetch(message_id.encode(), "(RFC822)")
        if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            raise ValueError(f"Message '{message_id}' not found in '{folder}'")

        raw = msg_data[0][1]
        parsed = BytesParser(policy=default_policy).parsebytes(raw)

        body = ""
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    body = part.get_content()
                    break
            if not body:
                for part in parsed.walk():
                    if part.get_content_type() == "text/html" and not part.get_filename():
                        body = part.get_content()
                        break
        else:
            body = parsed.get_content()

        return {
            "id": message_id,
            "from": _decode(parsed.get("From")),
            "to": _decode(parsed.get("To")),
            "subject": _decode(parsed.get("Subject")),
            "date": parsed.get("Date", ""),
            "body": body,
        }
    finally:
        client.logout()


def search_messages(
    settings: EmailSettings,
    query: str,
    folder: str = "INBOX",
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))
    if settings.imap_mock:
        matched = [m for m in _MOCK_MESSAGES if query.lower() in m["subject"].lower()]
        return matched[:limit]
    client = _imap_connect(settings)
    try:
        status, _ = client.select(folder, readonly=True)
        if status != "OK":
            raise ValueError(f"Cannot open folder '{folder}'")

        status, data = client.search(None, "TEXT", f'"{query}"')
        if status != "OK":
            raise RuntimeError(f"IMAP SEARCH failed: {status}")

        ids = data[0].split()
        ids = ids[-limit:]
        ids.reverse()

        results = []
        for msg_id in ids:
            status, msg_data = client.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            header_bytes = msg_data[0][1]
            parsed = BytesParser(policy=default_policy).parsebytes(header_bytes)
            results.append(
                {
                    "id": msg_id.decode(),
                    "from": _decode(parsed.get("From")),
                    "to": _decode(parsed.get("To")),
                    "subject": _decode(parsed.get("Subject")),
                    "date": parsed.get("Date", ""),
                }
            )
        return results
    finally:
        client.logout()
