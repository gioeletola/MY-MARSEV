"""API spec parser — parses OpenAPI 3.0 / Swagger 2.0 specs into connector blueprints."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EndpointSpec:
    path: str
    method: str          # GET / POST / PUT / PATCH / DELETE
    operation_id: str
    summary: str
    description: str
    parameters: list[dict]
    request_body: dict | None
    response_schema: dict | None
    tags: list[str] = field(default_factory=list)
    requires_auth: bool = True


@dataclass
class APIBlueprint:
    title: str
    version: str
    base_url: str
    auth_type: str       # bearer / apikey / basic / none
    auth_header: str     # e.g. "Authorization", "X-API-Key"
    endpoints: list[EndpointSpec] = field(default_factory=list)
    servers: list[str]   = field(default_factory=list)
    tags: list[str]      = field(default_factory=list)


class APISpecParser:
    """
    Parses OpenAPI 3.0 (or Swagger 2.0) spec dicts into an APIBlueprint.

    Usage::
        spec = json.loads(Path("openapi.json").read_text())
        blueprint = APISpecParser().parse(spec)
    """

    def parse(self, spec: dict[str, Any]) -> APIBlueprint:
        if "openapi" in spec:
            return self._parse_openapi3(spec)
        if "swagger" in spec:
            return self._parse_swagger2(spec)
        raise ValueError("Unrecognised spec format (need 'openapi' or 'swagger' key)")

    def parse_json(self, json_str: str) -> APIBlueprint:
        return self.parse(json.loads(json_str))

    # ------------------------------------------------------------------
    # OpenAPI 3.0
    # ------------------------------------------------------------------

    def _parse_openapi3(self, spec: dict) -> APIBlueprint:
        info = spec.get("info", {})
        servers = [s.get("url", "") for s in spec.get("servers", [])]
        base_url = servers[0] if servers else ""

        auth_type, auth_header = self._detect_auth_openapi3(spec)

        endpoints: list[EndpointSpec] = []
        for path, path_item in spec.get("paths", {}).items():
            for method, op in path_item.items():
                if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                    continue
                if not isinstance(op, dict):
                    continue
                endpoints.append(EndpointSpec(
                    path=path,
                    method=method.upper(),
                    operation_id=op.get("operationId", f"{method}_{path.replace('/','_')}"),
                    summary=op.get("summary", ""),
                    description=op.get("description", ""),
                    parameters=op.get("parameters", []),
                    request_body=op.get("requestBody"),
                    response_schema=self._extract_response_schema(op.get("responses", {})),
                    tags=op.get("tags", []),
                    requires_auth=bool(op.get("security") or spec.get("security")),
                ))

        return APIBlueprint(
            title=info.get("title", "Unknown API"),
            version=info.get("version", "1.0"),
            base_url=base_url,
            auth_type=auth_type,
            auth_header=auth_header,
            endpoints=endpoints,
            servers=servers,
            tags=list({t for ep in endpoints for t in ep.tags}),
        )

    def _detect_auth_openapi3(self, spec: dict) -> tuple[str, str]:
        schemes = spec.get("components", {}).get("securitySchemes", {})
        for name, scheme in schemes.items():
            t = scheme.get("type", "")
            if t == "http" and scheme.get("scheme") == "bearer":
                return "bearer", "Authorization"
            if t == "apiKey":
                return "apikey", scheme.get("name", "X-API-Key")
            if t == "http" and scheme.get("scheme") == "basic":
                return "basic", "Authorization"
        return "none", ""

    # ------------------------------------------------------------------
    # Swagger 2.0
    # ------------------------------------------------------------------

    def _parse_swagger2(self, spec: dict) -> APIBlueprint:
        info = spec.get("info", {})
        host = spec.get("host", "")
        base_path = spec.get("basePath", "/")
        scheme = (spec.get("schemes") or ["https"])[0]
        base_url = f"{scheme}://{host}{base_path}" if host else ""

        auth_type, auth_header = "none", ""
        for name, defn in spec.get("securityDefinitions", {}).items():
            if defn.get("type") == "apiKey":
                auth_type, auth_header = "apikey", defn.get("name", "X-API-Key")
            elif defn.get("type") == "basic":
                auth_type, auth_header = "basic", "Authorization"

        endpoints: list[EndpointSpec] = []
        for path, path_item in spec.get("paths", {}).items():
            for method, op in path_item.items():
                if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    continue
                endpoints.append(EndpointSpec(
                    path=path, method=method.upper(),
                    operation_id=op.get("operationId", f"{method}_{path}"),
                    summary=op.get("summary", ""),
                    description=op.get("description", ""),
                    parameters=op.get("parameters", []),
                    request_body=None,
                    response_schema=None,
                    tags=op.get("tags", []),
                    requires_auth=bool(op.get("security")),
                ))

        return APIBlueprint(
            title=info.get("title", "Unknown API"),
            version=info.get("version", "1.0"),
            base_url=base_url,
            auth_type=auth_type,
            auth_header=auth_header,
            endpoints=endpoints,
        )

    @staticmethod
    def _extract_response_schema(responses: dict) -> dict | None:
        for code in ("200", "201", "default"):
            resp = responses.get(code, {})
            content = resp.get("content", {})
            for media_type, media in content.items():
                if "schema" in media:
                    return media["schema"]
        return None

    def summary(self, blueprint: APIBlueprint) -> str:
        return (
            f"{blueprint.title} v{blueprint.version} — {blueprint.base_url}\n"
            f"Auth: {blueprint.auth_type} | Endpoints: {len(blueprint.endpoints)}\n"
            + "\n".join(f"  {ep.method:6} {ep.path}  ({ep.summary})" for ep in blueprint.endpoints[:20])
            + (f"\n  ... and {len(blueprint.endpoints)-20} more" if len(blueprint.endpoints) > 20 else "")
        )
