# gmail-oauth-lite

Minimal, framework-agnostic Gmail OAuth + message-reading helpers. Takes
plain OAuth strings (`client_id`/`client_secret`/`refresh_token`), not a
Flask app or any other framework object — wrap it in a one-line adapter
if your app wants to read those from its own config.

Extracted from [ultrahand](https://github.com/kevinli96/ultrahand)'s
`util/gmail.py` — specifically the generic subset with no booking-platform
coupling. It does **not** include ultrahand's `SharedGmailPoller` (a
multi-tenant, tee-time-matching dispatch poller) — that's tightly coupled
to one specific email format and wasn't generalized speculatively for a
single second consumer.

## Install

```bash
pip install git+https://github.com/kevinli96/gmail-oauth-lite.git
```

## Usage

```python
from gmail_oauth_lite import build_credentials, service_from_credentials, fetch_recent_message_bodies

creds = build_credentials(client_id, client_secret, refresh_token)
service = service_from_credentials(creds)
messages = fetch_recent_message_bodies(service, "from:someone@example.com", hours=1)
```

For a latency-critical path (e.g. racing a scheduled release), prewarm the
OAuth refresh ahead of time:

```python
from gmail_oauth_lite import prewarm_credentials, service_from_credentials

creds = prewarm_credentials(client_id, client_secret, refresh_token)  # pays the refresh cost now
# ... later, on the hot path ...
service = service_from_credentials(creds)  # cheap, no network call
```

## API

- `build_credentials(client_id, client_secret, refresh_token) -> Credentials`
- `prewarm_credentials(client_id, client_secret, refresh_token) -> Credentials` — force-refreshes immediately
- `service_from_credentials(credentials) -> Service`
- `get_message_html(payload) -> str`
- `fetch_recent_message_bodies(service, query, hours=24, max_results=10) -> list[dict]`
- `resolve_inbox_address(service) -> str | None`
- `resolve_delivered_to_alias(delivered_to_value, inbox) -> str | None | NOT_THIS_INBOX`
