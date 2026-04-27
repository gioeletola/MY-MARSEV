# Connectors — SOVEREIGN AI OS v0.3.0

Connectors integrate external services into SOVEREIGN's context. Each connector syncs data into the memory system and makes it available to agents and skills. There are **41 connectors** across 8 categories.

**Status key:**
- `connected` — stable, production-ready
- `beta` — functional but API surface may change
- `stub` — skeleton only, not yet implemented

---

## Finance & Trading

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `binance` | Binance | connected | API key | `BINANCE_API_KEY`, `BINANCE_API_SECRET` |
| `coingecko` | CoinGecko | connected | Optional | `COINGECKO_API_KEY` (free tier works without) |
| `revolut` | Revolut | connected | API key | `REVOLUT_API_KEY` |
| `stripe` | Stripe | connected | API key | `STRIPE_SECRET_KEY` |
| `etoro` | eToro | beta | API key | `ETORO_API_KEY` |
| `metatrader` | MetaTrader | beta | Bridge URL | `METATRADER_BRIDGE_URL` |

- `binance` — spot balances, price feeds, order history
- `coingecko` — coin prices, market cap, portfolio value
- `revolut` — balances, transactions, currency exposures, spend analytics
- `stripe` — payments, subscriptions, customers, invoices, revenue
- `etoro` — portfolio positions, CopyTrader allocation, open trades, P&L
- `metatrader` — MT4/MT5 equity, open positions, trade history, margin

---

## Communication

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `telegram` | Telegram Bot | connected | Bot token | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| `slack` | Slack | connected | OAuth | `SLACK_BOT_TOKEN` |
| `discord` | Discord | connected | Bot token | `DISCORD_BOT_TOKEN` |
| `whatsapp` | WhatsApp Business | beta | OAuth | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` |
| `gmail` | Gmail | beta | OAuth | `GMAIL_ACCESS_TOKEN` (OAuth2) |

- `telegram` — bot messages and commands; supports sending replies and media
- `slack` — unread mentions and DMs; supports posting messages and files
- `discord` — guilds, channels, messages, webhooks
- `whatsapp` — messages, templates, media, delivery status
- `gmail` — recent emails, labels, threads

---

## Social Media

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `x` | X (Twitter) | connected | OAuth | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` |
| `linkedin` | LinkedIn | beta | OAuth | `LINKEDIN_ACCESS_TOKEN` |
| `instagram` | Instagram | beta | OAuth | `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID` |
| `facebook` | Facebook | beta | OAuth | `FACEBOOK_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID` |

- `x` — mentions, DMs, bookmarks, follower analytics, trending topics
- `linkedin` — notifications, messages, connection requests, job engagement
- `instagram` — profile, feed posts, stories, reels, insights, DM threads
- `facebook` — pages, posts, ads performance, events, audience analytics

---

## Productivity & Organisation

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `github` | GitHub | connected | PAT | `GITHUB_TOKEN` |
| `notion` | Notion | beta | API key | `NOTION_TOKEN` |
| `linear` | Linear | connected | API key | `LINEAR_API_KEY` |
| `airtable` | Airtable | connected | API key | `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` |
| `calendar` | Calendar | beta | OAuth / CalDAV | `CALENDAR_CALDAV_URL`, `GOOGLE_CALENDAR_ID` |
| `calendly` | Calendly | connected | API key | `CALENDLY_API_KEY` |
| `typeform` | Typeform | connected | API key | `TYPEFORM_API_KEY` |
| `mailchimp` | Mailchimp | connected | API key | `MAILCHIMP_API_KEY` |
| `rss` | RSS / Atom Feeds | connected | None | configured in `config/sovereign.yaml` |
| `hackernews` | Hacker News | connected | None | none |
| `contacts` | Google Contacts | beta | OAuth | `GOOGLE_CONTACTS_TOKEN` |

- `github` — unread notifications, PR reviews, mentions
- `notion` — pages and databases (read/write)
- `linear` — assigned issues, active cycles
- `airtable` — bases, tables, records, views
- `calendar` — events via CalDAV or Google Calendar API
- `calendly` — event types, scheduled events, availability
- `typeform` — forms, responses, completion rates
- `mailchimp` — email lists, campaigns, automations, analytics
- `rss` — aggregates RSS/Atom feed entries into the knowledge base
- `hackernews` — top stories, job posts, Ask HN threads
- `contacts` — Google Contacts, groups, birthday reminders

---

## E-Commerce & Shopping

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `shopify` | Shopify | beta | API key | `SHOPIFY_STORE_DOMAIN`, `SHOPIFY_ACCESS_TOKEN` |
| `amazon` | Amazon | beta | OAuth | `AMAZON_LWA_CLIENT_ID`, `AMAZON_LWA_CLIENT_SECRET`, `AMAZON_REFRESH_TOKEN`, `AMAZON_MARKETPLACE_ID` |
| `deliveroo` | Deliveroo | beta | Session token | `DELIVEROO_SESSION_TOKEN` |
| `farfetch` | Farfetch | stub | Session cookie | — |
| `oopbuy` | Oopbuy | stub | API key | — |
| `sisal` | Sisal | stub | — | — |

- `shopify` — products, orders, inventory, analytics
- `amazon` — order history, spending by category; SP-API for sellers
- `deliveroo` — order history, spending by restaurant/category, favourites
- `farfetch` — wishlist, order history, price drops (stub)
- `oopbuy` — purchasing agent orders, warehouse arrival, shipping tracking (stub)
- `sisal` — lottery results, ticket checking, account balance (stub)

---

## Health, Fitness & Lifestyle

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `strava` | Strava | connected | OAuth | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN` |
| `spotify` | Spotify | connected | OAuth | `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REFRESH_TOKEN` |

- `strava` — activities, weekly stats, goals, fitness trends
- `spotify` — playback, playlists, top tracks, listening stats

---

## Travel

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `skyscanner` | Skyscanner | connected | RapidAPI | `SKYSCANNER_RAPIDAPI_KEY` |
| `airbnb` | Airbnb | beta | OAuth | `AIRBNB_ACCESS_TOKEN` |
| `uber` | Uber | beta | OAuth | `UBER_ACCESS_TOKEN`, `UBER_CLIENT_ID`, `UBER_CLIENT_SECRET` |

- `skyscanner` — flight/hotel/car search, price alerts, cheapest dates
- `airbnb` — listing performance, reservations, guest reviews, payouts
- `uber` — trip history, spend analytics, ride scheduling

---

## Learning & Other

| ID | Name | Status | Auth | Env Vars |
|---|---|---|---|---|
| `edx` | EdX | connected | OAuth | `EDX_CLIENT_ID`, `EDX_CLIENT_SECRET` |
| `notebooklm` | NotebookLM | beta | OAuth | `NOTEBOOKLM_GOOGLE_TOKEN` |
| `weather` | Weather | connected | None | `OPENWEATHER_API_KEY` (optional) |
| `bambulab` | Bambu Lab | beta | API key + MQTT | `BAMBULAB_TOKEN` |

- `edx` — enrolled courses, completion, grades, certificates, learning time
- `notebooklm` — notebooks and AI notes via Google Drive
- `weather` — current weather and 7-day forecast via Open-Meteo (free, no key)
- `bambulab` — 3D printer status, print jobs, filament inventory via Bambu Cloud + MQTT

---

## CLI Commands

```bash
# List all 41 connectors with status
python main.py connector list

# Trigger an immediate sync
python main.py connector sync github
python main.py connector sync binance

# Health check all connectors
python main.py connector health
```

---

## Sync Engine (Python API)

```python
from sovereign.integrations.connectors import get_sync_engine

engine = get_sync_engine()

# Sync one connector
result = await engine.sync_one("github")
print(result.records_synced, result.errors)

# Sync all registered connectors
results = await engine.sync_all()
```

---

## Adding a Custom Connector

See [docs/development/adding-connectors.md](../development/adding-connectors.md) for the full guide. Quick summary:

```python
# sovereign/integrations/connectors/my_connector.py
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

class MyConnector(ConnectorBase):
    connector_id = "my_service"
    connector_name = "My Service"
    connector_description = "Syncs data from My Service."
    connector_status = ConnectorStatus.BETA
    requires_oauth = False

    async def connect(self) -> bool:
        api_key = self._env("MY_SERVICE_API_KEY")
        if not api_key:
            self.connector_status = ConnectorStatus.DISCONNECTED
            return False
        self.connector_status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        try:
            # fetch and process data
            return SyncResult(connector_id=self.connector_id, success=True, records_synced=42)
        except Exception as exc:
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(connector_id=self.connector_id, status=self.connector_status)
```

Then register in `sovereign/integrations/connectors/__init__.py`:

```python
from sovereign.integrations.connectors.my_connector import MyConnector

__all__ = [..., "MyConnector"]
```
