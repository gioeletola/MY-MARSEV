"""
RSS/Atom feed connector — aggregates entries from a configurable list of feeds.
No auth required; feed URLs stored in config.
"""
from __future__ import annotations

import logging
from typing import Any

from sovereign.integrations.connectors.connector_base import (
    ConnectorBase,
    ConnectorHealth,
    ConnectorStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)


class RSSConnector(ConnectorBase):
    connector_id = "rss"
    connector_name = "RSS/Atom Feeds"
    connector_description = "Aggregates entries from RSS and Atom feeds into the knowledge base."
    connector_status = ConnectorStatus.CONNECTED  # no auth needed
    requires_oauth = False

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._feed_urls: list[str] = self._config.get("feed_urls", [])
        self._entries: list[dict] = []

    async def connect(self) -> bool:
        if not self._feed_urls:
            self._logger.warning("RSSConnector: no feed_urls configured")
        self.connector_status = ConnectorStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self._entries = []
        self.connector_status = ConnectorStatus.DISCONNECTED

    async def sync(self) -> SyncResult:
        if not self._feed_urls:
            return SyncResult(
                connector_id=self.connector_id,
                success=False,
                errors=["No feed_urls configured"],
            )
        try:
            import httpx
            self.connector_status = ConnectorStatus.SYNCING
            entries: list[dict] = []

            async with httpx.AsyncClient(timeout=15.0) as client:
                for url in self._feed_urls:
                    try:
                        resp = await client.get(url, follow_redirects=True)
                        if resp.status_code == 200:
                            parsed = self._parse_feed(resp.text, url)
                            entries.extend(parsed)
                        else:
                            self._logger.warning("RSSConnector: %s returned %d", url, resp.status_code)
                    except Exception as exc:
                        self._logger.warning("RSSConnector: error fetching %s: %s", url, exc)

            self._entries = entries
            self.connector_status = ConnectorStatus.CONNECTED
            result = SyncResult(
                connector_id=self.connector_id,
                success=True,
                records_synced=len(entries),
            )
            self._mark_sync(result)
            return result
        except Exception as exc:
            self.connector_status = ConnectorStatus.ERROR
            return SyncResult(connector_id=self.connector_id, success=False, errors=[str(exc)])

    def _parse_feed(self, xml_text: str, source_url: str) -> list[dict]:
        import xml.etree.ElementTree as ET
        entries: list[dict] = []
        try:
            root = ET.fromstring(xml_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            # Atom feed
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                link_el = entry.find("atom:link", ns)
                published_el = entry.find("atom:published", ns) or entry.find("atom:updated", ns)
                summary_el = entry.find("atom:summary", ns) or entry.find("atom:content", ns)
                entries.append({
                    "title": title_el.text if title_el is not None else "",
                    "url": link_el.get("href", "") if link_el is not None else "",
                    "published": published_el.text if published_el is not None else "",
                    "summary": (summary_el.text or "")[:500] if summary_el is not None else "",
                    "source": source_url,
                    "feed_type": "atom",
                })

            # RSS 2.0
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                desc_el = item.find("description")
                entries.append({
                    "title": title_el.text if title_el is not None else "",
                    "url": link_el.text if link_el is not None else "",
                    "published": pub_el.text if pub_el is not None else "",
                    "summary": (desc_el.text or "")[:500] if desc_el is not None else "",
                    "source": source_url,
                    "feed_type": "rss",
                })
        except ET.ParseError as exc:
            self._logger.warning("RSSConnector: XML parse error for %s: %s", source_url, exc)
        return entries

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            connector_id=self.connector_id,
            status=self.connector_status,
            last_sync=self._last_sync,
            last_error=self._last_error,
            records_synced=len(self._entries),
            metadata={"feed_count": len(self._feed_urls)},
        )

    def get_entries(self) -> list[dict]:
        return self._entries

    def add_feed(self, url: str) -> None:
        if url not in self._feed_urls:
            self._feed_urls.append(url)
