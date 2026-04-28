"""Helpers de normalização de payload de câmera (GAT-12)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def sanitize_plugins(plugins: Optional[List[str]]) -> List[str]:
    values = plugins or []
    return [item for item in values if str(item).strip().lower() != "yolo"]


def normalize_stream_node(node: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(node, dict):
        return None
    return {
        "stream_name": node.get("stream_name"),
        "source_url": node.get("source_url", ""),
    }


def is_fakepath(value: str) -> bool:
    return value.strip().lower().startswith("c:\\fakepath")


def payload_has_fakepath(streams: Dict[str, Any], source_url: str) -> bool:
    if source_url and is_fakepath(source_url):
        return True

    for modality in ("visible", "thermal"):
        group = streams.get(modality) or {}
        for profile in ("main", "sub"):
            node = group.get(profile)
            if isinstance(node, dict):
                url = str(node.get("source_url", ""))
                if url and is_fakepath(url):
                    return True
    return False
