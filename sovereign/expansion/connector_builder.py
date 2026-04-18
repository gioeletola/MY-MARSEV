"""Connector builder — generates BaseIntegration subclass code from an APIBlueprint."""
from __future__ import annotations

import logging
import pathlib
import textwrap
from typing import Any

logger = logging.getLogger(__name__)

_CONNECTOR_TEMPLATE = '''\
"""Auto-generated connector: {title} v{version}."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from sovereign.integrations.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)

logger = logging.getLogger(__name__)


class {class_name}(BaseIntegration):
    """
    {title} connector (auto-generated).
    Base URL: {base_url}
    Auth: {auth_type}
    """

    integration_id = "{integration_id}"
    name = "{title}"

    def __init__(self) -> None:
        super().__init__()
        self._client: httpx.AsyncClient | None = None
        self._base_url = "{base_url}"
        self._auth_header = "{auth_header}"
        self._token = ""

    # ------------------------------------------------------------------
    # BaseIntegration interface
    # ------------------------------------------------------------------

    def connect(self, config: IntegrationConfig) -> bool:
        creds = config.credentials or {{}}
        self._token = creds.get("token", creds.get("api_key", ""))
        self._base_url = creds.get("base_url", self._base_url)
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={{"{auth_header}": f"Bearer {{self._token}}"}} if self._token else {{}},
            timeout=15.0,
        )
        self._status = IntegrationStatus.CONNECTED
        logger.info("{class_name}.connect: OK")
        return True

    def disconnect(self) -> bool:
        if self._client:
            import asyncio
            try:
                asyncio.get_event_loop().run_until_complete(self._client.aclose())
            except Exception:
                pass
            self._client = None
        self._status = IntegrationStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        return self._status == IntegrationStatus.CONNECTED and bool(self._token)

    def fetch(self, resource: str, params: dict) -> dict:
        return {{}}

    def push(self, resource: str, data: dict) -> dict:
        return {{}}

    # ------------------------------------------------------------------
    # Generated endpoint methods
    # ------------------------------------------------------------------
{methods}
'''

_METHOD_TEMPLATE = '''\
    async def {method_name}(self, **kwargs: Any) -> dict:
        """{summary}"""
        assert self._client, "Not connected"
        resp = await self._client.{http_method}("{path}", **{{k: v for k, v in kwargs.items() if v}})
        resp.raise_for_status()
        return resp.json()
'''


class ConnectorBuilder:
    """
    Generates Python source code for a BaseIntegration subclass
    from an APIBlueprint produced by APISpecParser.
    """

    def __init__(self, output_dir: str = "sovereign/integrations/generated") -> None:
        self._output_dir = pathlib.Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate_code(self, blueprint: "APIBlueprint") -> str:  # type: ignore[name-defined]
        class_name = _to_class_name(blueprint.title) + "Integration"
        integration_id = _to_snake(blueprint.title)
        methods = "\n".join(
            _METHOD_TEMPLATE.format(
                method_name=_to_snake(ep.operation_id),
                summary=ep.summary or ep.description or ep.operation_id,
                http_method=ep.method.lower(),
                path=ep.path,
            )
            for ep in blueprint.endpoints[:30]  # cap at 30 methods
        )
        return _CONNECTOR_TEMPLATE.format(
            title=blueprint.title,
            version=blueprint.version,
            class_name=class_name,
            integration_id=integration_id,
            base_url=blueprint.base_url,
            auth_type=blueprint.auth_type,
            auth_header=blueprint.auth_header or "Authorization",
            methods=methods or "    pass\n",
        )

    def build(self, blueprint: "APIBlueprint", write: bool = True) -> str:  # type: ignore[name-defined]
        code = self.generate_code(blueprint)
        if write:
            filename = _to_snake(blueprint.title) + "_integration.py"
            path = self._output_dir / filename
            path.write_text(code, encoding="utf-8")
            logger.info("ConnectorBuilder: wrote %s", path)
        return code


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _to_class_name(s: str) -> str:
    return "".join(w.capitalize() for w in s.replace("-", " ").replace("_", " ").split())


def _to_snake(s: str) -> str:
    import re
    s = re.sub(r"[^a-zA-Z0-9]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.lower().strip("_")
