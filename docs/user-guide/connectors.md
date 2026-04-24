# Connectors

Connectors integrate external services into SOVEREIGN's context.
Each connector syncs data into the memory system and makes it available
to agents and skills.

## Available Connectors

| Connector | Auth | Status | Data Synced |
|---|---|---|---|
| GitHub | `GITHUB_TOKEN` (PAT) | Stable | Notifications, repos |
| Weather | None (free API) | Stable | Current + 7-day forecast |
| Notion | `NOTION_TOKEN` | Beta | Pages, databases |
| Gmail | OAuth2 | Beta | Recent inbox messages |

## Setup

### GitHub

```bash
# Set your Personal Access Token
echo "GITHUB_TOKEN=ghp_xxx" >> .env

# Sync
python main.py connector sync github
```

### Notion

```bash
# Create an integration at https://www.notion.so/my-integrations
echo "NOTION_TOKEN=secret_xxx" >> .env
python main.py connector sync notion
```

### Gmail

Gmail requires OAuth2. Follow the setup in `docs/getting-started/oauth.md`
to obtain an access token, then:
```bash
echo "GMAIL_ACCESS_TOKEN=ya29.xxx" >> .env
python main.py connector sync gmail
```

### Weather

No configuration needed — uses the free Open-Meteo API.
Set your default location in `config/sovereign.yaml`:

```yaml
connectors:
  weather:
    location: "Milan"
```

## Sync Engine

The sync engine (`sovereign/integrations/connectors/sync_engine.py`) runs
connectors on a schedule with automatic retry and exponential backoff.

```python
from sovereign.integrations.connectors import get_sync_engine

engine = get_sync_engine()
result = await engine.sync_one("github")
all_results = await engine.sync_all()
```

## Writing a Custom Connector

```python
from sovereign.integrations.connectors.connector_base import (
    ConnectorBase, ConnectorHealth, ConnectorStatus, SyncResult,
)

class MyConnector(ConnectorBase):
    connector_id = "my_service"
    connector_name = "My Service"
    connector_description = "Syncs data from My Service."
    requires_oauth = False

    async def connect(self) -> bool:
        # Validate credentials
        return True

    async def disconnect(self) -> None:
        pass

    async def sync(self) -> SyncResult:
        # Fetch data and store in self._data
        return SyncResult(connector_id=self.connector_id, success=True, records_synced=42)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
        )
```

Register it in `sovereign/integrations/connectors/__init__.py`.
