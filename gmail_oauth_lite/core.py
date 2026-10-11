"""Core Gmail OAuth + message-reading helpers. See package docstring."""
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_TOKEN_URI = "https://oauth2.googleapis.com/token"


def build_credentials(client_id: str, client_secret: str, refresh_token: str) -> Credentials:
    """Build Credentials from OAuth values, refreshing if already expired.

    `token=None` lets the auth library refresh on first use via the
    refresh token — a stored access token has a 1-hour TTL so any value
    carried across restarts is almost always stale anyway.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GMAIL_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def prewarm_credentials(client_id: str, client_secret: str, refresh_token: str) -> Credentials:
    """Build Credentials and force-refresh immediately.

    Use ahead of a latency-critical path (e.g. a scheduled release race)
    to pay the ~100-300ms OAuth refresh cost early rather than during it.
    Cache the returned Credentials and build new Service objects from
    them on demand via `service_from_credentials` — each caller should
    get its own Service (and thus its own httplib2.Http) so concurrent
    `.execute()` calls from different callers don't race on a shared
    SSL socket.
    """
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=GMAIL_TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def service_from_credentials(credentials: Credentials):
    """Build a fresh Gmail Service from existing Credentials.

    Cheap to call — pure Python object construction, no network I/O
    (the discovery document is cached at module level by googleapiclient).
    """
    return build("gmail", "v1", credentials=credentials)


def get_message_html(payload: dict) -> str:
    """Extract raw HTML body from a Gmail message payload (recursive-safe)."""
    if "parts" in payload:
        for part in payload["parts"]:
            mime = part.get("mimeType")
            data = part.get("body", {}).get("data")

            if mime == "text/html" and data:
                return base64.urlsafe_b64decode(data).decode(errors="ignore")

            if part.get("parts"):
                html = get_message_html(part)
                if html:
                    return html

    data = payload.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode(errors="ignore")

    return ""


def fetch_recent_message_bodies(
    service, query: str, hours: float = 24, max_results: int = 10
) -> list[dict]:
    """Run a Gmail query, return messages newer than `hours` ago as
    [{id, subject, html, internal_ts, delivered_to}, ...].

    One list() + N get() calls per invocation, no caching or background
    thread — fine for a one-off read (a login-code lookup, a diagnostic
    endpoint). For a high-frequency, long-running poll loop, build your
    own loop around `service.users().messages()` directly instead.

    `delivered_to` lets callers that share one inbox across multiple
    forwarded accounts disambiguate whose message this is, via
    `resolve_delivered_to_alias`.
    """
    results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = results.get("messages", [])
    if not messages:
        return []

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    bodies = []

    for msg in messages:
        msg_data = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        internal_ts = int(msg_data.get("internalDate", 0)) / 1000.0
        msg_time = datetime.fromtimestamp(internal_ts, tz=timezone.utc)
        if msg_time < cutoff_time:
            continue

        payload = msg_data.get("payload", {})
        headers = payload.get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        delivered_to = next(
            (h["value"] for h in headers if h["name"].lower() == "delivered-to"), ""
        )

        bodies.append({
            "id": msg["id"],
            "subject": subject,
            "html": get_message_html(payload),
            "internal_ts": internal_ts,
            "delivered_to": delivered_to,
        })

    return bodies


_inbox_address_cache: dict[int, str] = {}


def resolve_inbox_address(service) -> Optional[str]:
    """Return the Gmail address behind `service`, caching per service instance."""
    key = id(service)
    if key in _inbox_address_cache:
        return _inbox_address_cache[key]
    profile = service.users().getProfile(userId="me").execute()
    address = profile.get("emailAddress")
    if address:
        _inbox_address_cache[key] = address
    return address


# Sentinel distinguishing "this address doesn't belong to our inbox at all"
# from a valid-but-bare address (alias=None, i.e. the owner). A sentinel
# rather than overloading None lets resolve_delivered_to_alias return a
# clean ternary without a wrapper type.
NOT_THIS_INBOX = object()


def resolve_delivered_to_alias(delivered_to_value: str, inbox: str):
    """Parse a Delivered-To header value against `inbox`.

    Generic across any plus-alias forwarding setup — this is just
    address parsing, with no roster/user-lookup. Examples
    (inbox="me@gmail.com"):
      - "me@gmail.com" -> None (bare inbox — the owner)
      - "me+cc@gmail.com" -> "cc"
      - "elsewhere@example.com" -> NOT_THIS_INBOX (different domain)
      - "elsewhere+cc@gmail.com" -> NOT_THIS_INBOX (same domain, wrong local prefix)

    Returns the lowercased alias, None for the bare inbox, or
    NOT_THIS_INBOX if the address doesn't belong to this inbox at all.
    """
    local, _, domain = inbox.partition("@")
    if not delivered_to_value.lower().endswith(f"@{domain.lower()}"):
        return NOT_THIS_INBOX
    delivered_local = delivered_to_value.split("@", 1)[0]
    # Defense-in-depth: reject anything whose local prefix doesn't match the
    # inbox owner. Without this, "elsewhere+cc@gmail.com" would resolve to
    # alias "cc" despite not actually being a forward of this inbox.
    if delivered_local.split("+", 1)[0].lower() != local.lower():
        return NOT_THIS_INBOX
    if "+" in delivered_local:
        return delivered_local.split("+", 1)[1].lower()
    return None  # bare inbox = owner
