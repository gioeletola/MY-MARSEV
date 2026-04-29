"""XML Tool — parse, query, transform, and validate XML (stdlib only)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from sovereign.tools.base_tool import BaseTool, ToolSchema


def _elem_to_dict(elem: ET.Element) -> dict:
    d: dict[str, Any] = {"tag": elem.tag, "text": (elem.text or "").strip() or None, "attrs": dict(elem.attrib)}
    children = [_elem_to_dict(c) for c in elem]
    if children:
        d["children"] = children
    return d


class XmlTool(BaseTool):
    """Parse, query, build, and validate XML documents without external dependencies."""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="xml_tool",
            description="Parse XML to dict, query with XPath-like find, extract text/attrs, build XML, count elements, validate structure.",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["parse", "find", "find_all", "get_text", "get_attrs",
                                 "to_dict", "count", "validate", "build", "strip_namespaces"],
                        "description": "parse|find|find_all|get_text|get_attrs|to_dict|count|validate|build|strip_namespaces",
                    },
                    "xml": {"type": "string", "description": "XML string to process"},
                    "path": {"type": "string", "description": "XPath-style path for find/find_all/count"},
                    "tag": {"type": "string", "description": "Element tag name for build"},
                    "text": {"type": "string", "description": "Element text for build"},
                    "attrs": {"type": "object", "description": "Element attributes for build"},
                    "children": {"type": "array", "description": "Child element dicts for build"},
                },
                "required": ["action"],
            },
        )

    async def execute(
        self, action: str, xml: str = "", path: str = ".",
        tag: str = "root", text: str = "", attrs: dict | None = None,
        children: list | None = None, **_: Any,
    ) -> Any:
        try:
            if action == "build":
                return self._build(tag, text, attrs or {}, children or [])
            if action == "validate":
                return self._validate(xml)

            root = ET.fromstring(xml)

            if action == "parse":
                return {"result": _elem_to_dict(root), "tag": root.tag, "error": None}
            if action == "to_dict":
                return {"result": _elem_to_dict(root), "error": None}
            if action == "find":
                elem = root.find(path)
                if elem is None:
                    return {"result": None, "error": f"Path not found: {path}"}
                return {"result": _elem_to_dict(elem), "error": None}
            if action == "find_all":
                elems = root.findall(path)
                return {"result": [_elem_to_dict(e) for e in elems], "count": len(elems), "error": None}
            if action == "get_text":
                elem = root.find(path) if path and path != "." else root
                text_val = (elem.text or "").strip() if elem is not None else None
                return {"result": text_val, "error": None if elem is not None else f"Path not found: {path}"}
            if action == "get_attrs":
                elem = root.find(path) if path and path != "." else root
                if elem is None:
                    return {"result": None, "error": f"Path not found: {path}"}
                return {"result": dict(elem.attrib), "tag": elem.tag, "error": None}
            if action == "count":
                elems = root.findall(path)
                return {"result": len(elems), "path": path, "error": None}
            if action == "strip_namespaces":
                clean = self._strip_ns(xml)
                return {"result": clean, "error": None}
            return {"result": None, "error": f"Unknown action: {action}"}
        except ET.ParseError as exc:
            return {"result": None, "error": f"XML parse error: {exc}"}
        except Exception as exc:
            return {"result": None, "error": str(exc)}

    def _validate(self, xml_str: str) -> dict:
        try:
            ET.fromstring(xml_str)
            return {"result": True, "error": None}
        except ET.ParseError as exc:
            return {"result": False, "error": str(exc)}

    def _build(self, tag: str, text: str, attrs: dict, children: list) -> dict:
        elem = ET.Element(tag, attrib={str(k): str(v) for k, v in attrs.items()})
        if text:
            elem.text = text
        for child_spec in children:
            if isinstance(child_spec, dict):
                child_tag = child_spec.get("tag", "item")
                child_text = child_spec.get("text", "")
                child_attrs = {str(k): str(v) for k, v in child_spec.get("attrs", {}).items()}
                child_elem = ET.SubElement(elem, child_tag, attrib=child_attrs)
                if child_text:
                    child_elem.text = str(child_text)
        xml_str = ET.tostring(elem, encoding="unicode", xml_declaration=False)
        return {"result": xml_str, "tag": tag, "error": None}

    def _strip_ns(self, xml_str: str) -> str:
        import re
        xml_str = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', "", xml_str)
        xml_str = re.sub(r"<(\w+):\s*", "<", xml_str)
        xml_str = re.sub(r"\{[^}]+\}", "", xml_str)
        return xml_str
