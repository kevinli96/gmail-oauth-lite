"""gmail-oauth-lite — minimal Gmail OAuth + message-reading helpers.

Framework-agnostic: takes plain OAuth strings (client_id/client_secret/
refresh_token), not a Flask app or any other framework object. A caller
in a Flask app typically wraps `build_credentials` in a one-line adapter
that reads its own config and passes the three strings through.

Extracted from ultrahand (github.com/kevinli96/ultrahand)'s util/gmail.py
— specifically the generic subset with no booking-platform coupling.
ultrahand's own ForeUp-specific SharedGmailPoller (multi-tenant,
tee-time-matching dispatch) was deliberately NOT generalized into this
library; it's tightly coupled to ForeUp's exact email format and wasn't
worth abstracting speculatively for a single second consumer (ultraspoon),
which doesn't need that machinery — see ultraspoon's own README for why.
"""
from .core import (
    GMAIL_TOKEN_URI,
    SCOPES,
    NOT_THIS_INBOX,
    build_credentials,
    fetch_recent_message_bodies,
    get_message_html,
    prewarm_credentials,
    resolve_delivered_to_alias,
    resolve_inbox_address,
    service_from_credentials,
)

__all__ = [
    "GMAIL_TOKEN_URI",
    "SCOPES",
    "NOT_THIS_INBOX",
    "build_credentials",
    "fetch_recent_message_bodies",
    "get_message_html",
    "prewarm_credentials",
    "resolve_delivered_to_alias",
    "resolve_inbox_address",
    "service_from_credentials",
]
